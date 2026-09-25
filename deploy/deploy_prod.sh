#!/usr/bin/env bash
# =============================================================================
# deploy_prod.sh — Aplica `main` en el servidor de producción por SSH.
#
# Flujo (ver docs/specs/14-flujo-despliegue-dev-prod.md):
#   1. `git pull --ff-only origin main` en producción.
#   2. Gate de sintaxis (php -l / py_compile) sobre lo cambiado.
#   3. Si cambian units -> reinstala systemd; si cambia requirements -> pip install;
#      si cambia deploy/apache -> reinstala el vhost del panel.
#   4. Reinicia SOLO los servicios afectados por el diff (o todos con --all).
#   5. Verifica salud y reporta.
#
# Configuración en `.env` del proyecto (NUNCA versionado):
#   RF_PROD_HOST=194.233.67.64
#   RF_PROD_SSH_USER=root
#   RF_PROD_SSH_PASS=...
#   RF_PROD_SSH_PORT=22                        (opcional)
#   RF_PROD_PATH=/root/reconocimientoFacial    (opcional)
#
# Uso:
#   bash deploy/deploy_prod.sh [--all] [--no-restart] [--dry-run]
#                              [--host H] [--path P]
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROYECTO="$(cd "${SCRIPT_DIR}/.." && pwd)"

# --- flags -------------------------------------------------------------------
ALL=0; NO_RESTART=0; DRY_RUN=0
HOST_OVERRIDE=""; PATH_OVERRIDE=""
while [ $# -gt 0 ]; do
    case "$1" in
        --all) ALL=1 ;;
        --no-restart|--pull-only) NO_RESTART=1 ;;
        --dry-run) DRY_RUN=1 ;;
        --host) HOST_OVERRIDE="${2:-}"; shift ;;
        --path) PATH_OVERRIDE="${2:-}"; shift ;;
        -h|--help) sed -n '2,28p' "$0"; exit 0 ;;
        *) echo "Flag desconocida: $1" >&2; exit 2 ;;
    esac
    shift
done

# --- configuración (.env o entorno) -----------------------------------------
ENV_FILE="${PROYECTO}/.env"
env_get() {
    local k="$1" d="${2:-}" v=""
    v="${!k:-}"
    if [ -z "$v" ] && [ -f "$ENV_FILE" ]; then
        v="$(grep -m1 "^${k}=" "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
    fi
    printf '%s' "${v:-$d}"
}
PROD_HOST="${HOST_OVERRIDE:-$(env_get RF_PROD_HOST)}"
PROD_USER="$(env_get RF_PROD_SSH_USER root)"
PROD_PASS="$(env_get RF_PROD_SSH_PASS)"
PROD_PORT="$(env_get RF_PROD_SSH_PORT 22)"
PROD_PATH="${PATH_OVERRIDE:-$(env_get RF_PROD_PATH /root/reconocimientoFacial)}"

if [ -z "$PROD_HOST" ]; then
    echo "ERROR: RF_PROD_HOST no configurado. Añádelo a ${ENV_FILE}:" >&2
    echo "       RF_PROD_HOST=194.233.67.64" >&2
    echo "       RF_PROD_SSH_USER=root" >&2
    echo "       RF_PROD_SSH_PASS=..." >&2
    exit 2
fi

SSH_BASE=(ssh -p "$PROD_PORT" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=20 "${PROD_USER}@${PROD_HOST}")
if [ -n "$PROD_PASS" ]; then
    if ! command -v sshpass >/dev/null 2>&1; then
        echo "ERROR: sshpass no instalado y RF_PROD_SSH_PASS definido." >&2
        exit 2
    fi
    SSH=("sshpass" "-p" "$PROD_PASS" "${SSH_BASE[@]}")
else
    SSH=("${SSH_BASE[@]}")
fi

# --- script remoto -----------------------------------------------------------
REMOTE_SCRIPT="$(cat <<'REMOTE'
set -euo pipefail
cd "__PROD_PATH__"
ALL=__ALL__; NO_RESTART=__NO_RESTART__
ALL_SERVICES="rf-capturador rf-detector rf-clasificador rf-panel-control rf-live rf-conciliador rf-vinculador rf-alarmador rf-photo"

OLD=$(git rev-parse HEAD)
echo "[deploy] HEAD antes:  ${OLD:0:7}"
git fetch --quiet origin main
git pull --ff-only origin main
NEW=$(git rev-parse HEAD)
echo "[deploy] HEAD despues: ${NEW:0:7}"
if [ "$OLD" = "$NEW" ]; then
    echo "[deploy] sin cambios en produccion ($NEW)."
    exit 0
fi
CHANGED="$(git diff --name-only "$OLD" "$NEW")"
echo "[deploy] ficheros cambiados: $(printf '%s\n' "$CHANGED" | grep -c .)"

# Prerrequisitos de runtime (no versionados).
mkdir -p aux motor/logs libs/threads_files_aux admin/caras_procesadas && chmod 777 libs/threads_files_aux
if [ -f .env ]; then
    chown root:www-data .env 2>/dev/null || true
    chmod 640 .env 2>/dev/null || true
fi

# Units systemd / instalador (drop-ins de memoria, dirs runtime, .env perms).
if printf '%s\n' "$CHANGED" | grep -qE '^(deploy/systemd/|deploy/install_services\.sh$)'; then
    echo "[deploy] units/instalador cambiados -> reinstalando systemd"
    bash deploy/install_services.sh >/dev/null
    systemctl daemon-reload
fi

# Vhost Apache del panel.
if printf '%s\n' "$CHANGED" | grep -qE '^deploy/apache/'; then
    echo "[deploy] vhost cambiado -> reinstalando Apache"
    bash deploy/install_apache.sh
fi

# Dependencias Python.
if printf '%s\n' "$CHANGED" | grep -qE '^motor/requirements\.txt$'; then
    echo "[deploy] requirements.txt cambiado -> pip install"
    motor/venv/bin/pip install -r motor/requirements.txt
fi

# Gate de sintaxis antes de tocar servicios.
FAIL=0
while IFS= read -r f; do
    [ -z "$f" ] && continue
    [ -f "$f" ] || continue
    case "$f" in
        *.php) php -l "$f" >/dev/null 2>&1 || { echo "[deploy] SYNTAX ERROR PHP: $f"; FAIL=1; } ;;
        *.py)  motor/venv/bin/python -m py_compile "$f" >/dev/null 2>&1 || { echo "[deploy] SYNTAX ERROR PY:  $f"; FAIL=1; } ;;
    esac
done <<< "$CHANGED"

# Timers de one-shots (calibración / vigilancia de deriva).
if printf '%s\n' "$CHANGED" | grep -qE '^motor/(calibrar|vigilar_deriva)\.py$'; then
    echo "[deploy] one-shots cambiados -> rearmando timers"
    systemctl restart rf-calibra.timer rf-vigilar-deriva.timer 2>/dev/null || true
fi

# Migraciones SQL pendientes: SOLO los ficheros NUEVOS (--diff-filter=A).
# Los sql/ históricos no son re-ejecutables (p. ej. CREATE TRIGGER exige SUPER
# con binary logging); una migración nueva debe ser idempotente.
ADDED_SQL="$(git diff --diff-filter=A --name-only "$OLD" "$NEW" | grep -E '^sql/.*\.sql$' || true)"
if [ -n "$ADDED_SQL" ]; then
    echo "[deploy] migraciones SQL nuevas -> aplicando"
    set -a; [ -f .env ] && . ./.env; set +a
    DBNAME="${RF_DB_NAME:-reconocimientofacial}"
    while IFS= read -r f; do
        [ -n "$f" ] || continue
        [ -f "$f" ] || continue
        echo "[deploy]   mysql < $f"
        if [ -n "${RF_DB_PASS:-}" ]; then
            mysql -u"${RF_DB_USER:-root}" -p"$RF_DB_PASS" -h"${RF_DB_HOST:-localhost}" "$DBNAME" < "$f" \
                || { echo "[deploy] SQL ERROR: $f"; FAIL=1; }
        else
            mysql -u"${RF_DB_USER:-root}" -h"${RF_DB_HOST:-localhost}" "$DBNAME" < "$f" \
                || { echo "[deploy] SQL ERROR: $f"; FAIL=1; }
        fi
    done <<< "$ADDED_SQL"
fi

if [ "$NO_RESTART" = 1 ]; then
    echo "[deploy] --no-restart: codigo aplicado sin reiniciar servicios."
    exit 0
fi
if [ "$FAIL" = 1 ]; then
    echo "[deploy] ABORTADO: errores de sintaxis; NO se reinician servicios."
    exit 3
fi

# Mapa diff -> servicios.
SVC=""
want() { if printf '%s\n' "$CHANGED" | grep -qE "$1"; then SVC="$SVC $2"; fi; }
want '^(capturador\.php|motor/guarda_movimientosV3\.py)$' 'rf-capturador'
want '^(detector\.php|motor/procesa_video\.py|motor/archiva_video\.py|motor/cruces\.py|motor/clasificador\.py)$' 'rf-detector'
want '^clasificadorV2\.php$' 'rf-clasificador'
want '^(conciliador\.php|libs/conciliador\.php)$' 'rf-conciliador'
want '^(vinculador\.php|libs/vinculos\.php)$' 'rf-vinculador'
want '^(alarmador\.php|libs/alarmas\.php)$' 'rf-alarmador'
want '^(procesos_panel_control\.php|motor/pose\.py)$' 'rf-panel-control'
want '^live/' 'rf-live'
want '^motor/photo_worker\.py$' 'rf-photo'
# Cambios transversales -> todos los daemons (core compartido, db, config, units, apache, deps).
if printf '%s\n' "$CHANGED" | grep -qE '^(motor/core/|libs/db\.php|config/config\.php|deploy/systemd/|deploy/apache/|deploy/install_services\.sh$|motor/requirements\.txt)'; then
    SVC=" $ALL_SERVICES"
fi
if [ "$ALL" = 1 ]; then
    SVC=" $ALL_SERVICES"
fi
SVC="$(for s in $SVC; do echo "$s"; done | sort -u | tr '\n' ' ' | sed 's/ *$//')"

if [ -z "$SVC" ]; then
    echo "[deploy] cambios sin impacto en daemons (solo web/docs). Pull aplicado."
    exit 0
fi

echo "[deploy] reiniciando:$SVC"
systemctl restart $SVC
sleep 3
FAILSV=0
for s in $SVC; do
    st=$(systemctl is-active "$s" 2>/dev/null || true)
    printf '  %-22s %s\n' "$s" "$st"
    [ "$st" = "active" ] || FAILSV=1
done
if [ "$FAILSV" = 0 ]; then
    echo "[deploy] OK — produccion actualizada y servicios en verde."
else
    echo "[deploy] ALERTA: algun servicio no esta active (revisar journalctl)."
    exit 4
fi
REMOTE
)"

REMOTE_SCRIPT="${REMOTE_SCRIPT//__PROD_PATH__/$PROD_PATH}"
REMOTE_SCRIPT="${REMOTE_SCRIPT//__ALL__/$ALL}"
REMOTE_SCRIPT="${REMOTE_SCRIPT//__NO_RESTART__/$NO_RESTART}"

if [ "$DRY_RUN" = 1 ]; then
    echo "===== dry-run: comandos que se ejecutarían en ${PROD_USER}@${PROD_HOST} ====="
    printf '%s\n' "$REMOTE_SCRIPT"
    exit 0
fi

echo "==> Desplegando en ${PROD_USER}@${PROD_HOST} (${PROD_PATH})"
printf '%s' "$REMOTE_SCRIPT" | "${SSH[@]}" "bash -s"
