#!/usr/bin/env bash
# =============================================================================
# distribute_runtime.sh — prepara un nodo para ejecutar procesos del motor
# reconocimientoFacial en el pool de SuperServer (M4).
#
# Ejecutar desde un host que tenga la imagen construida (`deploy/docker/build.sh`)
# y acceso SSH a los nodos. Para cada nodo hace, en este orden:
#   1. `docker save rfacerec:1 | ssh <nodo> docker load` (imagen portable).
#   2. Copia el modelo insightface `buffalo_l` desde la casa (mail) al nodo.
#   3. Escribe `.env.worker` (sin secretos) y el marcador `.runtime-image`.
#   4. Smoke test: arranca la imagen y comprueba las importaciones.
#
# Uso:
#   bash deploy/docker/distribute_runtime.sh <casa> <nodo1> [nodo2 ...]
#   bash deploy/docker/distribute_runtime.sh root@100.106.48.118 root@100.117.92.74
#
# Requisitos: docker en origen y destino, ssh sin password, rsync.
# =============================================================================
set -euo pipefail

IMG="${RF_IMAGE:-rfacerec:1}"
RF_ROOT="${RF_ROOT:-/opt/taildeck/reconocimientoFacial}"
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=20)

[ $# -ge 2 ] || { echo "uso: $0 <casa> <nodo1> [nodo2 ...]" >&2; exit 2; }
CASA="$1"; shift

for NODE in "$@"; do
    echo "==> $NODE"
    echo "  1/4 imagen $IMG"
    docker save "$IMG" | ssh "${SSH_OPTS[@]}" "$NODE" 'docker load'
    echo "  2/4 buffalo_l"
    ssh "${SSH_OPTS[@]}" "$NODE" "mkdir -p $RF_ROOT/.insightface/models"
    # Casa -> (este host) -> nodo: el host que lanza la distribución hace de puente.
    ssh "${SSH_OPTS[@]}" "$CASA" "tar cf - -C /root/.insightface/models buffalo_l" \
        | ssh "${SSH_OPTS[@]}" "$NODE" "tar xf - -C $RF_ROOT/.insightface/models"
    echo "  3/4 .env.worker + marcador"
    # El worker debe replicar la CONFIG DE PIPELINE de la casa (umbrales SR/matching,
    # det_size, etc.), no solo unas pocas vars: si faltan, el contenedor usa los
    # defaults y el resultado diverge (p. ej. SR-before-embedding desactivado por
    # RF_SR_EMBED_MIN_FACE). Se toman todas las RF_* del .env de la casa EXCEPTO
    # secretos y rutas/URLs locales. NUNCA viajan credenciales.
    ENV_FILTER='
import re,sys
EXC=re.compile(r"(PASS|KEY|SECRET|TOKEN|LLM|OPENAI|DB_|FTP_|AUTOLOGIN|RF_URL|RF_RUTA|RF_PYTHON|VLM_BASE_URL|VLM_MODEL|VLM_NUM|VLM_TIMEOUT|VLM_KEEP_ALIVE|VLM_MAX_PENDING|VLM_RAM)", re.I)
keep=[]
for line in sys.stdin:
    line=line.strip()
    if not line.startswith("RF_"): continue
    if EXC.search(line): continue
    if line.startswith(("RF_VLM_ENABLED=","RF_OPENAI_ENABLED=")): continue
    keep.append(line)
keep += ["RF_VLM_ENABLED=0","RF_OPENAI_ENABLED=0"]
print("\n".join(keep))
'
    ssh "${SSH_OPTS[@]}" "$CASA" "cat /root/reconocimientoFacial/.env 2>/dev/null" \
        | python3 -c "$ENV_FILTER" \
        | ssh "${SSH_OPTS[@]}" "$NODE" "cat > $RF_ROOT/.env.worker && date -Is > $RF_ROOT/.runtime-image"
    echo "     .env.worker: $(ssh "${SSH_OPTS[@]}" "$NODE" "wc -l < $RF_ROOT/.env.worker") vars"
    echo "  4/4 smoke test"
    ssh "${SSH_OPTS[@]}" "$NODE" "docker run --rm --network=none $IMG python -c 'import numpy,cv2,scipy,skimage,insightface,onnxruntime; print(\"OK\", onnxruntime.__version__)'"
    echo "  LISTO $NODE"
done
