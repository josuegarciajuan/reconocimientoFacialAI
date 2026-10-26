#!/usr/bin/env bash
# =============================================================================
# start_pipeline.sh — Puesta en marcha ordenada del pipeline en tiempo real.
#
# Orden:
#   1. Verifica configuración/BD y la unit rf-pipeline.
#   2. Habilita y arranca rf-pipeline.
#   3. Espera y muestra el estado (--status).
#   4. Opcional: arranca rf-live (panel) siempre que esté instalado.
#   5. La captura SOLO se arranca con --enable-capture y RF_PIPELINE_CAPTURE_READY=1
#      (guarda para no capturar hasta que el sink/apply esté conectado).
#
# Uso:
#   bash deploy/start_pipeline.sh [--instance ojos|mail|all] [--dry-run]
#                                 [--enable-capture]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROYECTO="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROYECTO}/.env"

INSTANCES="ojos"
DRY_RUN=0
ENABLE_CAPTURE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --instance) INSTANCES="${2:-}"; shift ;;
    --instance=*) INSTANCES="${1#--instance=}" ;;
    --dry-run) DRY_RUN=1 ;;
    --enable-capture) ENABLE_CAPTURE=1 ;;
    -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
    *) echo "Flag desconocida: $1" >&2; exit 2 ;;
  esac
  shift
done
case "$INSTANCES" in all|ojos|mail) ;; *)
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

PROD_HOST="$(env_get RF_PROD_HOST)"
PROD_USER="$(env_get RF_PROD_SSH_USER root)"
PROD_PASS="$(env_get RF_PROD_SSH_PASS)"
PROD_PORT="$(env_get RF_PROD_SSH_PORT 22)"
PROD_PATH="$(env_get RF_PROD_PATH /root/reconocimientoFacial)"
CAPTURE_READY="$(env_get RF_PIPELINE_CAPTURE_READY 0)"

if [ "$ENABLE_CAPTURE" = 1 ] && [ "$CAPTURE_READY" != "1" ]; then
  echo "ERROR: --enable-capture requiere RF_PIPELINE_CAPTURE_READY=1 en .env." >&2
  echo "       (la captura real espera a que el sink/apply esté conectado)" >&2
  exit 2
fi

run_local() {
  echo "[start] ojos: verificando configuración"
  [ -f "$ENV_FILE" ] || { echo "ERROR: falta $ENV_FILE" >&2; return 1; }
  local db; db="$(env_get RF_DB_NAME)"
  [ -n "$db" ] || { echo "ERROR: RF_DB_NAME vacío" >&2; return 1; }
  echo "[start] ojos: db=$db project=$(env_get RF_SUPERSERVER_PROJECT ojos)"
  if ! systemctl cat rf-pipeline >/dev/null 2>&1; then
    echo "ERROR: rf-pipeline.service no instalada en este host." >&2
    echo "       Ejecuta: bash deploy/install_services.sh" >&2
    return 1
  fi
  if [ "$DRY_RUN" = 1 ]; then
    echo "[start] (dry-run) systemctl enable --now rf-pipeline"
    echo "[start] (dry-run) systemctl enable --now rf-live"
    [ "$ENABLE_CAPTURE" = 1 ] && echo "[start] (dry-run) systemctl enable --now rf-capturador"
    return 0
  fi
  systemctl enable --now rf-pipeline
  sleep 2
  "$PROYECTO/motor/venv/bin/python" "$PROYECTO/motor/pipeline_service.py" --status \
    --ruta "$PROYECTO" || true
  if systemctl list-unit-files rf-live.service >/dev/null 2>&1; then
    systemctl enable --now rf-live 2>/dev/null || true
  fi
  if [ "$ENABLE_CAPTURE" = 1 ]; then
    echo "[start] ojos: arrancando captura"
    systemctl enable --now rf-capturador
  else
    echo "[start] ojos: captura NO arrancada (usa --enable-capture cuando proceda)"
  fi
}

run_remote() {
  [ -n "$PROD_HOST" ] || { echo "ERROR: RF_PROD_HOST no configurado" >&2; return 1; }
  local ssh_base=(ssh -p "$PROD_PORT" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 "${PROD_USER}@${PROD_HOST}")
  local ssh_cmd=("${ssh_base[@]}")
  if [ -n "$PROD_PASS" ]; then
    command -v sshpass >/dev/null 2>&1 || { echo "ERROR: falta sshpass" >&2; return 1; }
    ssh_cmd=(sshpass -p "$PROD_PASS" "${ssh_base[@]}")
  fi
  local capture=0; [ "$ENABLE_CAPTURE" = 1 ] && capture=1
  local   remote_cmd="set -euo pipefail; cd $(printf '%q' "$PROD_PATH"); "
  remote_cmd+="git fetch --quiet origin main; git pull --ff-only origin main; "
  remote_cmd+="systemctl cat rf-pipeline >/dev/null 2>&1 || { echo '[start] ERROR: falta rf-pipeline.service' >&2; exit 7; }; "
  if [ "$DRY_RUN" = 1 ]; then
    remote_cmd+="echo '[start] (dry-run) mail: rf-pipeline + rf-live'; "
    [ "$capture" = 1 ] && remote_cmd+="echo '[start] (dry-run) mail: rf-capturador'; "
    remote_cmd+="echo '[start] (dry-run) completo'"
  else
    remote_cmd+="systemctl enable --now rf-pipeline; sleep 2; "
    remote_cmd+="motor/venv/bin/python motor/pipeline_service.py --status --ruta \"\$PWD\" || true; "
    remote_cmd+="systemctl list-unit-files rf-live.service >/dev/null 2>&1 && systemctl enable --now rf-live 2>/dev/null || true; "
    if [ "$capture" = 1 ]; then
      remote_cmd+="systemctl enable --now rf-capturador; "
    else
      remote_cmd+="echo '[start] mail: captura NO arrancada'; "
    fi
    remote_cmd+="echo '[start] mail: OK'"
  fi
  echo "[start] mail: ${PROD_USER}@${PROD_HOST}"
  "${ssh_cmd[@]}" "$remote_cmd"
}

RC=0
if [ "$INSTANCES" = "all" ] || [ "$INSTANCES" = "ojos" ]; then
  run_local || RC=1
fi
if [ "$INSTANCES" = "all" ] || [ "$INSTANCES" = "mail" ]; then
  run_remote || RC=1
fi
exit "$RC"
