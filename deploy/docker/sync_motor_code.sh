#!/usr/bin/env bash
# =============================================================================
# sync_motor_code.sh — sincroniza el CÓDIGO del motor a los workers del pool.
#
# El contenedor `rfacerec:1` monta `/opt/taildeck/reconocimientoFacial:/app:ro`.
# `distribute_runtime.sh` provisiona imagen + buffalo_l + `.env.worker`, pero NO
# el código Python del proyecto: si cambia `motor/**/*.py`, los workers seguirían
# ejecutando la versión antigua (p. ej. `procesa_video_pool.py` sin `--from/--to`
# en la definición distribuida `rf-video-segments` -> ARTIFACT_RESULT_JSON_MISSING).
#
# Este script copia TODOS los `*.py` de `motor/` (sin venv/models/__pycache__) a
# `/opt/taildeck/reconocimientoFacial/motor/` de cada nodo por tar+ssh (sin
# dependencias; rsync opcional no necesario).
#
# Uso:
#   bash deploy/docker/sync_motor_code.sh <ip1> [ip2 ...]
#   bash deploy/docker/sync_motor_code.sh 100.77.212.12 100.117.92.74
#
# Ejecutar desde un host con acceso SSH (BatchMode) a los nodos. Idempotente.
# =============================================================================
set -euo pipefail

RF_ROOT="${RF_ROOT:-/opt/taildeck/reconocimientoFacial}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROYECTO="$(cd "${SCRIPT_DIR}/../.." && pwd)"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=20 -o StrictHostKeyChecking=accept-new)

[ $# -ge 1 ] || { echo "uso: $0 <ip1> [ip2 ...]" >&2; exit 2; }

# Lista de ficheros .py del motor (sin venv ni bytecode).
LIST="$(mktemp)"
trap 'rm -f "$LIST"' EXIT
( cd "$PROYECTO" && find motor -name '*.py' -not -path 'motor/venv/*' -not -path '*/__pycache__/*' | sort > "$LIST" )
N=$(wc -l < "$LIST")
echo "[sync] $N ficheros .py de $PROYECTO/motor"

FAIL=0
for IP in "$@"; do
  echo "==> $IP"
  if ( cd "$PROYECTO" && tar cf - -T "$LIST" ) | ssh "${SSH_OPTS[@]}" "root@$IP" \
       "mkdir -p '$RF_ROOT' && tar xf - -C '$RF_ROOT'"; then
    echo "  OK"
  else
    echo "  FALLO"
    FAIL=1
  fi
done
exit "$FAIL"
