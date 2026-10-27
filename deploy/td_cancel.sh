#!/usr/bin/env bash
# =============================================================================
# td_cancel.sh — cancela los jobs de UN proyecto en SuperServer.
#
# Detecta si el control plane está en este host (API loopback) o en otro
# (`RF_SUPERSERVER_CTL_HOST`, por defecto liveyourdre2) y ejecuta allí
# `taildeck_cancel.py`. Nunca toca otros proyectos ni para taildeck.service.
#
# Uso: bash deploy/td_cancel.sh <proyecto> [--dry-run] [--purge-returns]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROYECTO="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROYECTO}/.env"

DRY_RUN=0
PURGE=0
PROJECT=""
while [ $# -gt 0 ]; do
  arg="$1"
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --purge-returns) PURGE=1 ;;
    --project) PROJECT="${2:-}"; shift ;;
    --project=*) PROJECT="${arg#--project=}" ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    -*) echo "flag desconocida: $arg" >&2; exit 2 ;;
    *) [ -z "$PROJECT" ] && PROJECT="$arg" || { echo "proyecto duplicado" >&2; exit 2; } ;;
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
  echo "ERROR: RF_SUPERSERVER_PROJECT vacío; no se toca ninguna cola" >&2
  exit 2
fi

CTL_HOST="${RF_SUPERSERVER_CTL_HOST:-}"
if [ -z "$CTL_HOST" ] && [ -f "$ENV_FILE" ]; then
  CTL_HOST="$(grep -m1 '^RF_SUPERSERVER_CTL_HOST=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d ' \t"' || true)"
fi
CTL_HOST="${CTL_HOST:-liveyourdre2}"
API="${RF_SUPERSERVER_API:-http://127.0.0.1:8110/superserver}"

ARGS=("$PROJECT")
[ "$DRY_RUN" -eq 1 ] && ARGS+=(--dry-run)
[ "$PURGE" -eq 1 ] && ARGS+=(--purge-returns)

# ¿Control plane local? La API solo responde con el sello del gate.
if command -v curl >/dev/null 2>&1 && curl -fsS --max-time 2 -H 'X-Panel-Gate: 1' "${API}/api/health" >/dev/null 2>&1; then
  echo "[td-cancel] control plane local (${API}) proyecto=${PROJECT}"
  exec python3 "${SCRIPT_DIR}/taildeck_cancel.py" "${ARGS[@]}"
fi

if ! command -v ssh >/dev/null 2>&1; then
  echo "ERROR: control plane no local y ssh no disponible" >&2
  exit 3
fi
echo "[td-cancel] control plane remoto ${CTL_HOST} proyecto=${PROJECT}"
ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 \
    "root@${CTL_HOST}" "python3 - $(printf '%q ' "${ARGS[@]}")" \
    < "${SCRIPT_DIR}/taildeck_cancel.py"
