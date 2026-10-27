#!/usr/bin/env bash
# =============================================================================
# rf_stop.sh — parada segura y project-scoped del motor de reconocimiento.
#
# Hace, en este host y SOLO para su RF_SUPERSERVER_PROJECT:
#   1. modo `local` (guarda el anterior para poder restaurarlo con rf_power on),
#   2. para timers y servicios del motor (incluye rf-pipeline y rf-reprocesa),
#   3. mata bridges/huérfanos/ffmpeg que systemd no haya arrastrado,
#   4. cancela en SuperServer los jobs activos de ESTE proyecto,
#   5. opcional: limpia colas (y media) locales,
#   6. deja siempre rf-live activo.
#
# Uso:
#   bash deploy/rf_stop.sh [--dry-run] [--project ID] [--no-cancel] [--no-disable]
#                         [--purge-queues] [--purge-media] [--strict-cancel]
# =============================================================================
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROYECTO="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROYECTO}/.env"

DRY_RUN=0
NO_CANCEL=0
NO_DISABLE=0
PURGE_QUEUES=0
PURGE_MEDIA=0
STRICT_CANCEL=0
PROJECT=""

while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --project) PROJECT="${2:-}"; shift ;;
    --project=*) PROJECT="${1#--project=}" ;;
    --no-cancel) NO_CANCEL=1 ;;
    --no-disable) NO_DISABLE=1 ;;
    --purge-queues) PURGE_QUEUES=1 ;;
    --purge-media) PURGE_MEDIA=1 ;;
    --strict-cancel) STRICT_CANCEL=1 ;;
    -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
    *) echo "flag desconocida: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ -z "$PROJECT" ]; then
  PROJECT="${RF_SUPERSERVER_PROJECT:-}"
fi
if [ -z "$PROJECT" ] && [ -f "$ENV_FILE" ]; then
  PROJECT="$(grep -m1 '^RF_SUPERSERVER_PROJECT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d ' \t"' || true)"
fi
if [ -z "$PROJECT" ]; then
  echo "ERROR: RF_SUPERSERVER_PROJECT vacío; abortado para no tocar otra instancia" >&2
  exit 2
fi

if [ "$(id -u)" -ne 0 ] && [ "$DRY_RUN" -eq 0 ]; then
  echo "ERROR: ejecutar como root" >&2
  exit 2
fi

run() {
  if [ "$DRY_RUN" -eq 1 ]; then echo "  (dry-run) $*"; else "$@"; fi
}

echo "[rf-stop] host=$(hostname) proyecto=${PROJECT} dry_run=${DRY_RUN}"

# 1) Modo local + respaldo del modo anterior (para rf_power on).
MODE_DIR="${RF_MODE_DIR:-/var/lib/taildeck/projects}"
MODE_FILE="${MODE_DIR}/${PROJECT}.mode"
PREV_FILE="${MODE_FILE}.rf-prev"
if [ -d "$MODE_DIR" ]; then
  CUR="$(cat "$MODE_FILE" 2>/dev/null | tr -d ' \t\r\n' || true)"
  if [ "$CUR" != "local" ] && [ -n "$CUR" ]; then
    run sh -c "printf '%s\n' '$CUR' > '$PREV_FILE'"
    echo "[rf-stop] modo anterior guardado: ${CUR}"
  fi
  run sh -c "printf '%s\n' local > '$MODE_FILE'"
  echo "[rf-stop] modo local en ${MODE_FILE}"
else
  echo "[rf-stop] AVISO: no existe ${MODE_DIR}; no se cambia el modo"
fi

# 2) Timers primero y después servicios. rf-live NO se toca.
TIMERS=(rf-calibra.timer rf-vigilar-deriva.timer rf-reprocesa.timer)
SERVICES=(rf-capturador rf-detector rf-clasificador rf-clasificador-serve rf-panel-control
          rf-conciliador rf-vinculador rf-alarmador rf-photo rf-pipeline rf-reprocesa)
for t in "${TIMERS[@]}"; do run systemctl stop "$t" 2>/dev/null || true; done
for s in "${SERVICES[@]}"; do run systemctl stop "$s" 2>/dev/null || true; done
if [ "$NO_DISABLE" -eq 0 ]; then
  for t in "${TIMERS[@]}"; do run systemctl disable "$t" 2>/dev/null || true; done
  for s in "${SERVICES[@]}"; do run systemctl disable "$s" 2>/dev/null || true; done
fi
run systemctl reset-failed rf-reprocesa 2>/dev/null || true
echo "[rf-stop] timers y servicios de motor detenidos (rf-live intacto)"

# 3) Procesos que hayan escapado del cgroup.
PATTERNS=(
  "pool_bridge.py" "clasificador_bridge.py" "archiva_video_bridge.py"
  "reprocesar_bridge.py" "photo_worker_pool.py" "video_orchestrator.py"
  "reprocesar.py" "pipeline_service.py" "procesa_video.py" "procesa_video_pool.py"
  "clasificador.py" "photo_worker.py" "guarda_movimientosV3.py" "pose.py"
  "cruces.py" "enrolamiento.py" "calibrador.py" "vigilar_deriva.py"
  "capturador.php" "detector.php" "clasificadorV2.php" "conciliador.php"
  "vinculador.php" "alarmador.php" "procesos_panel_control.php"
)
tree_nopids() {
  local p=$$ out=""
  while [ "${p:-0}" -gt 1 ] 2>/dev/null; do
    out="$out $p"
    p=$(awk '{print $4}' "/proc/${p}/stat" 2>/dev/null) || break
    [ -n "$p" ] || break
  done
  printf '%s' "$out"
}
ffmpeg_project_pids() {
  local pid cwd
  for pid in $(pgrep -x ffmpeg 2>/dev/null || true); do
    cwd=$(readlink "/proc/${pid}/cwd" 2>/dev/null || true)
    case "$cwd" in "$PROYECTO"|"$PROYECTO"/*) printf '%s\n' "$pid" ;; esac
  done
}
collect_pids() {
  local pat
  for pat in "${PATTERNS[@]}"; do pgrep -f -- "$pat" 2>/dev/null || true; done
  pgrep -f -- "${PROYECTO}/motor" 2>/dev/null || true
  ffmpeg_project_pids
}
kill_round() {
  local notouch pids seen="" targets=() pid
  notouch="$(tree_nopids)"
  pids="$(collect_pids | sort -u)"
  for pid in $pids; do
    case " $notouch " in *" $pid "*) continue ;; esac
    case " $seen " in *" $pid "*) continue ;; esac
    seen="$seen $pid"; targets+=("$pid")
  done
  if [ ${#targets[@]} -eq 0 ]; then echo "[rf-stop] sin procesos RF vivos"; return 0; fi
  if [ "$DRY_RUN" -eq 1 ]; then echo "  (dry-run) mataría PIDs: ${targets[*]}"; return 0; fi
  echo "[rf-stop] matando PIDs: ${targets[*]}"
  kill -9 "${targets[@]}" 2>/dev/null || true
}
kill_round
if [ "$DRY_RUN" -eq 0 ]; then
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    REST=$(collect_pids | sort -u | grep -vxF -f <(tree_nopids | tr ' ' '\n' | sed '/^$/d') | wc -l)
    [ "$REST" -eq 0 ] && break
    sleep 1
  done
  if [ "${REST:-0}" -ne 0 ]; then kill_round; sleep 2; fi
fi

# 4) Cancelar la cola de ESTE proyecto en SuperServer.
CANCEL_RC=0
if [ "$NO_CANCEL" -eq 0 ]; then
  CANCEL_ARGS=(--project "$PROJECT")
  [ "$DRY_RUN" -eq 1 ] && CANCEL_ARGS+=(--dry-run)
  bash "${SCRIPT_DIR}/td_cancel.sh" "${CANCEL_ARGS[@]}" || CANCEL_RC=$?
  if [ "$CANCEL_RC" -ne 0 ]; then
    echo "[rf-stop] AVISO: no se pudo cancelar la cola de ${PROJECT} (rc=${CANCEL_RC})" >&2
  fi
fi

# 5) Limpiezas opcionales (nunca por defecto desde el botón Apagar).
purge_path() {
  local p="$1"
  case "$p" in "$PROYECTO"/*) : ;; *) echo "  rechazado fuera del proyecto: $p" >&2; return 1 ;; esac
  [ -e "$p" ] || return 0
  if [ "$DRY_RUN" -eq 1 ]; then echo "  (dry-run) borraría $p"; else rm -rf -- "$p"; echo "  borrado $p"; fi
}
purge_spool_project() {
  local dir="${RF_SPOOL_DIR:-/var/lib/taildeck/spool}"
  [ -d "$dir" ] || return 0
  python3 - "$dir" "$PROJECT" "$DRY_RUN" <<'PY'
import json, os, sys
d, proj, dry = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
n = 0
for name in os.listdir(d):
    if not name.endswith(".json"):
        continue
    p = os.path.join(d, name)
    try:
        obj = json.load(open(p, encoding="utf-8"))
    except Exception:
        continue
    if obj.get("project") != proj:
        continue
    n += 1
    if dry:
        print(f"  (dry-run) borraría petición {p}")
    else:
        os.unlink(p)
        print(f"  borrada petición {p}")
print(f"[rf-stop] peticiones de spool: {n}")
PY
}
if [ "$PURGE_QUEUES" -eq 1 ]; then
  echo "[rf-stop] limpiando colas locales de ${PROJECT}"
  purge_spool_project
  RET="/var/lib/taildeck/returns/${PROJECT}"
  if [ -d "$RET" ]; then
    if [ "$DRY_RUN" -eq 1 ]; then echo "  (dry-run) borraría $RET"; else rm -rf -- "$RET"; echo "  borrado $RET"; fi
  fi
  purge_path "${PROYECTO}/motor/jobs"
  purge_path "${PROYECTO}/motor/pending"
  purge_path "${PROYECTO}/motor/photo_queue"
  purge_path "${PROYECTO}/motor/clasificador_daemon"
  purge_path "${PROYECTO}/motor/audit_queue"
  purge_path "${PROYECTO}/motor/dedup"
  purge_path "${PROYECTO}/motor/reprocesado"
  if [ -d "${PROYECTO}/aux" ]; then
    for f in "${PROYECTO}/aux"/*; do [ -e "$f" ] && purge_path "$f"; done
  fi
  for f in "${PROYECTO}/motor/logs"/pipeline_*; do [ -e "$f" ] && purge_path "$f"; done
fi

if [ "$PURGE_MEDIA" -eq 1 ]; then
  echo "[rf-stop] limpiando media pendiente de ${PROJECT}"
  LOCAL_ID="${RF_LOCAL_ID:-1}"
  purge_path "${PROYECTO}/motor/videos/${LOCAL_ID}"
  purge_path "${PROYECTO}/motor/videos_archivo/${LOCAL_ID}"
  purge_path "${PROYECTO}/motor/caras"
  purge_path "${PROYECTO}/motor/fotos_lineas"
  purge_path "${PROYECTO}/motor/videos_lineas"
  purge_path "${PROYECTO}/motor/portraits/${LOCAL_ID}"
  purge_path "${PROYECTO}/motor/llm_cache"
  purge_path "${PROYECTO}/motor/photo_evidence"
  purge_path "${PROYECTO}/motor/alinear_caras"
  purge_path "${PROYECTO}/admin/caras_procesadas"
  purge_path "${PROYECTO}/admin/fotos_originales"
  purge_path "${PROYECTO}/admin/fotos_camara"
  for f in "${PROYECTO}/admin/files"/videos_registro*; do [ -e "$f" ] && purge_path "$f"; done
fi

# 6) rf-live siempre disponible.
run systemctl start rf-live 2>/dev/null || true

# 7) Verificación.
if [ "$DRY_RUN" -eq 0 ]; then
  echo "[rf-stop] --- estado ---"
  for s in "${SERVICES[@]}" rf-live; do
    printf '  %-26s %s\n' "$s" "$(systemctl is-active "$s" 2>/dev/null || true)"
  done
  REST=$(collect_pids | sort -u | grep -vxF -f <(tree_nopids | tr ' ' '\n' | sed '/^$/d') | wc -l)
  echo "[rf-stop] procesos RF restantes: ${REST}"
  if [ "${REST:-0}" -ne 0 ]; then
    collect_pids | sort -u | while read -r p; do
      [ -n "$p" ] && printf '  PID %s: %s\n' "$p" "$(tr '\0' ' ' < "/proc/$p/cmdline" 2>/dev/null)"
    done
    exit 1
  fi
fi

if [ "$STRICT_CANCEL" -eq 1 ] && [ "$CANCEL_RC" -ne 0 ]; then
  exit "$CANCEL_RC"
fi
if [ "$CANCEL_RC" -eq 0 ]; then
  echo "[rf-stop] OK: ${PROJECT} detenido, rf-live activo, cola cancelada"
else
  echo "[rf-stop] OK: ${PROJECT} detenido y rf-live activo (cola NO confirmada, rc=${CANCEL_RC})"
fi
