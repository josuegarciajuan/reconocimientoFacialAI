#!/usr/bin/env bash
# =============================================================================
# reset_all.sh — Reset total coordinado de las dos instancias.
#
#   ojos (personal, local, liveyourdre2)  -> BD reconocimientofacial_ojos
#   mail (laboral, remoto, RF_PROD_HOST)  -> su propia BD y .env
#
# Conserva cámaras, locales, líneas, planos, usuarios, auto-login, alarmas y
# calibraciones. Borra identidad, movimiento, colas, vídeos, fotos, cruces,
# fichajes, estancias, alarmas históricas y estado del pipeline.
#
# Por defecto deja el motor APAGADO (--no-start) para el arranque controlado.
#
# Uso:
#   bash deploy/reset_all.sh [--instance ojos|mail|all] [--dry-run] [--yes]
#                            [--hold N] [--start] [--no-pull]
#
# --dry-run  : inventario y plan, sin borrar.
# --yes      : no pide confirmación interactiva.
# --start    : rearranca servicios al final (por defecto quedan apagados).
# --no-pull  : en mail, no hace git pull antes del reset.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROYECTO="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROYECTO}/.env"

INSTANCES="all"
DRY_RUN=0
YES=0
HOLD=0
START=0
NO_PULL=0
while [ $# -gt 0 ]; do
  case "$1" in
    --instance) INSTANCES="${2:-}"; shift ;;
    --instance=*) INSTANCES="${1#--instance=}" ;;
    --dry-run) DRY_RUN=1 ;;
    --yes|-y) YES=1 ;;
    --hold) HOLD="${2:-0}"; shift ;;
    --hold=*) HOLD="${1#--hold=}" ;;
    --start) START=1 ;;
    --no-pull) NO_PULL=1 ;;
    -h|--help) sed -n '2,30p' "$0"; exit 0 ;;
    *) echo "Flag desconocida: $1" >&2; exit 2 ;;
  esac
  shift
done

case "${INSTANCES}" in all|ojos|mail) ;; *)
  echo "ERROR: --instance debe ser ojos, mail o all" >&2; exit 2 ;;
esac

env_get() {
  local k="$1" d="${2:-}" v=""
  v="${!k:-}"
  if [ -z "$v" ] && [ -f "$ENV_FILE" ]; then
    v="$(grep -m1 "^${k}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
  fi
  printf '%s' "${v:-$d}"
}

[ "$(id -u)" -eq 0 ] || { echo "ERROR: ejecutar como root" >&2; exit 2; }

# --- Argumentos comunes de reset_datos.sh -----------------------------------
COMMON=(--no-autoenroll-guard)
[ "$DRY_RUN" = 1 ] && COMMON+=(--dry-run)
[ "$HOLD" != "0" ] && COMMON+=(--hold "$HOLD")
[ "$START" = 1 ] || COMMON+=(--no-start)

# --- Mail (remoto) -----------------------------------------------------------
PROD_HOST="$(env_get RF_PROD_HOST)"
PROD_USER="$(env_get RF_PROD_SSH_USER root)"
PROD_PASS="$(env_get RF_PROD_SSH_PASS)"
PROD_PORT="$(env_get RF_PROD_SSH_PORT 22)"
PROD_PATH="$(env_get RF_PROD_PATH /root/reconocimientoFacial)"

SSH_BASE=(ssh -p "$PROD_PORT" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 "${PROD_USER}@${PROD_HOST}")
if [ -n "$PROD_PASS" ]; then
  command -v sshpass >/dev/null 2>&1 || { echo "ERROR: falta sshpass" >&2; exit 2; }
  SSH=(sshpass -p "$PROD_PASS" "${SSH_BASE[@]}")
else
  SSH=("${SSH_BASE[@]}")
fi

# --- Plan --------------------------------------------------------------------
LOCAL_DB="$(env_get RF_DB_NAME)"
LOCAL_PRJ="$(env_get RF_SUPERSERVER_PROJECT)"
echo "================ RESET TOTAL ================"
if [ "$INSTANCES" = "all" ] || [ "$INSTANCES" = "ojos" ]; then
  echo " ojos (local) host=$(hostname) db=${LOCAL_DB} project=${LOCAL_PRJ}"
fi
if [ "$INSTANCES" = "all" ] || [ "$INSTANCES" = "mail" ]; then
  echo " mail (remoto) ${PROD_USER}@${PROD_HOST}:${PROD_PORT} path=${PROD_PATH}"
fi
echo " flags: ${COMMON[*]}"
echo " conserva: camaras, locales, lineas, planos, nodos, senderos,"
echo "           usuarios/auto-login, alarmas, calibraciones."
echo " borra:    personas, fotos, videos, cruces, fichajes, estancias, alarmas"
echo "           históricas, galería, colas, .units, motor/jobs, motor/artifacts,"
echo "           peticiones/retornos pendientes de esta instancia."
echo "============================================="

if [ "$DRY_RUN" = 0 ] && [ "$YES" = 0 ]; then
  if [ ! -t 0 ]; then
    echo "ERROR: sin TTY y sin --yes; abortado." >&2
    exit 2
  fi
  printf "Escribe RESET para ejecutar el borrado: "
  read -r ANSWER
  [ "$ANSWER" = "RESET" ] || { echo "Abortado."; exit 1; }
fi

# --- Ojos (local) ------------------------------------------------------------
run_ojos() {
  local host; host="$(hostname)"
  if [ "$host" != "liveyourdre2" ]; then
    echo "[reset-all] ERROR: ojos debe ejecutarse en liveyourdre2 (host actual: $host)" >&2
    return 1
  fi
  if [ -z "$LOCAL_DB" ]; then
    echo "[reset-all] ERROR: RF_DB_NAME no configurado para ojos" >&2
    return 1
  fi
  echo; echo "==> [ojos] reset local (db=${LOCAL_DB})"
  ( cd "$PROYECTO" && bash deploy/reset_datos.sh "${COMMON[@]}" --expect-host liveyourdre2 )
}

# --- Mail (remoto) -----------------------------------------------------------
run_mail() {
  if [ -z "$PROD_HOST" ]; then
    echo "[reset-all] ERROR: RF_PROD_HOST no configurado" >&2
    return 1
  fi
  local remote_args remote_cmd
  remote_args="$(printf '%q ' "${COMMON[@]}")"
  remote_cmd="set -euo pipefail; cd $(printf '%q' "$PROD_PATH"); "
  if [ "$NO_PULL" = 0 ]; then
    remote_cmd+="echo '[reset-all] mail: git pull'; git fetch --quiet origin main; git pull --ff-only origin main; "
  fi
  # Verificación de instancia remota (no debe ser 'ojos'). Si el .env no define
  # el proyecto, se asume el laboral (igual que project_id()).
  remote_cmd+="prj=\$(grep -m1 '^RF_SUPERSERVER_PROJECT=' .env 2>/dev/null | cut -d= -f2- | tr -d ' \\t\"' || true); "
  remote_cmd+="prj=\${prj:-reconocimientoFacial}; "
  remote_cmd+="if [ \"\$prj\" = \"ojos\" ]; then echo '[reset-all] ERROR: mail apunta a ojos' >&2; exit 9; fi; "
  remote_cmd+="echo \"[reset-all] mail project=\${prj:-?}\"; "
  remote_cmd+="bash deploy/reset_datos.sh ${remote_args}"
  echo; echo "==> [mail] reset remoto en ${PROD_USER}@${PROD_HOST}"
  "${SSH[@]}" "$remote_cmd"
}

RC=0
if [ "$INSTANCES" = "all" ] || [ "$INSTANCES" = "ojos" ]; then
  run_ojos || RC=1
fi
if [ "$INSTANCES" = "all" ] || [ "$INSTANCES" = "mail" ]; then
  run_mail || RC=1
fi

if [ "$RC" -ne 0 ]; then
  echo "[reset-all] ALGUN RESET FALLÓ (rc=$RC). Revisar salida anterior." >&2
  exit "$RC"
fi
echo
echo "[reset-all] Reset completado. Motor APAGADO (salvo --start)."
echo "[reset-all] Siguiente paso: Fase 10 (puesta en marcha controlada)."
