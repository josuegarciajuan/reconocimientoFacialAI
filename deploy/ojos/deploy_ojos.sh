#!/usr/bin/env bash
# =============================================================================
# deploy_ojos.sh — aplica `main` en la instancia personal (liveyourdre2).
#
# No usa SSH: el código de `ojos` vive en el mismo checkout que se despliega.
# Hace pull fast-forward, gate de sintaxis, migraciones SQL nuevas, recarga de
# PHP-FPM/Apache y reinicio de los servicios del motor personal. Si el motor
# está en standby (rf-capturador disabled+inactive) NO reactiva las unidades
# apagadas a mano: solo reinicia las que siguen enabled/active (p. ej. rf-live).
#
# Uso (root): bash deploy/ojos/deploy_ojos.sh [--no-pull] [--no-restart]
# =============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$DIR/.env"
SECRETS_DIR="/root/onx-secrets/ojos"
APPLIED="$SECRETS_DIR/applied_sql.txt"
NO_PULL=0; NO_RESTART=0
for arg in "$@"; do
    case "$arg" in
        --no-pull) NO_PULL=1 ;;
        --no-restart) NO_RESTART=1 ;;
        *) echo "flag desconocida: $arg" >&2; exit 2 ;;
    esac
done

[ "$(id -u)" -eq 0 ] || { echo "ERROR: ejecuta como root" >&2; exit 2; }
mkdir -p "$SECRETS_DIR"; chmod 700 "$SECRETS_DIR"

OLD="$(git -C "$DIR" rev-parse HEAD)"
if [ "$NO_PULL" = 0 ]; then
    git -C "$DIR" fetch --quiet origin main
    git -C "$DIR" pull --ff-only origin main
fi
NEW="$(git -C "$DIR" rev-parse HEAD)"
CHANGED="$(git -C "$DIR" diff --name-only "$OLD" "$NEW")"
if [ "$OLD" = "$NEW" ]; then
    echo "[ojos] sin cambios de código ($NEW)."
else
    echo "[ojos] $OLD -> $NEW"
fi

# Gate de sintaxis de lo cambiado.
FAIL=0
while IFS= read -r f; do
    [ -n "$f" ] || continue
    [ -f "$DIR/$f" ] || continue
    case "$f" in
        *.php) php -l "$DIR/$f" >/dev/null 2>&1 || { echo "[ojos] SYNTAX ERROR PHP: $f"; FAIL=1; } ;;
        *.py)  "$DIR/motor/venv/bin/python" -m py_compile "$DIR/$f" >/dev/null 2>&1 || { echo "[ojos] SYNTAX ERROR PY: $f"; FAIL=1; } ;;
    esac
done <<< "$CHANGED"
if [ "$FAIL" = 1 ]; then
    echo "[ojos] ABORTADO por errores de sintaxis" >&2
    exit 3
fi

# Units systemd: instalarlas si cambiaron (sin arrancarlas; el arranque es
# controlado con deploy/start_pipeline.sh o rf_power.sh).
if printf '%s\n' "$CHANGED" | grep -qE '^(deploy/systemd/|deploy/install_services\.sh$)'; then
    echo "[ojos] units/instalador cambiados -> instalando systemd"
    bash "$DIR/deploy/install_services.sh" >/dev/null
fi

# Migraciones SQL nuevas (las históricas ya están en applied_sql.txt).
set -a; . "$ENV_FILE"; set +a
DB_NAME="${RF_DB_NAME:?}"
touch "$APPLIED"
if [ -d "$DIR/sql" ]; then
    while IFS= read -r f; do
        base="$(basename "$f")"
        grep -qxF "$base" "$APPLIED" && continue
        echo "[ojos] aplicando migración $base"
        MYSQL_PWD="${RF_DB_PASS:-}" mysql -u"${RF_DB_USER:-root}" -h"${RF_DB_HOST:-localhost}" "$DB_NAME" < "$f" \
            || { echo "[ojos] SQL ERROR: $base" >&2; exit 4; }
        echo "$base" >> "$APPLIED"
    done < <(find "$DIR/sql" -maxdepth 1 -name '*.sql' | sort)
fi

# Recargar PHP-FPM/Apache (configs de la instancia).
SOCK="$(ls -1 /run/php/php[0-9]*-fpm.sock 2>/dev/null | sort -V | tail -1 || true)"
if [ -n "$SOCK" ]; then
    PHPVER="$(basename "$SOCK" | sed -E 's/^php([0-9.]+)-fpm\.sock$/\1/')"
    systemctl reload "php$PHPVER-fpm" 2>/dev/null || true
fi
apache2ctl configtest >/dev/null 2>&1 && systemctl reload apache2 2>/dev/null || true

if [ "$NO_RESTART" = 1 ]; then
    echo "[ojos] --no-restart: código aplicado."
    exit 0
fi

SERVICES="rf-capturador rf-detector rf-clasificador rf-clasificador-serve rf-panel-control rf-live rf-conciliador rf-vinculador rf-alarmador rf-photo"

# ¿Motor deliberadamente en standby? (capturador disabled + inactive).
# Mismo criterio que deploy_prod.sh: un despliegue no debe reactivar el motor
# que se apagó a mano. En ojos el standby replica el estado de laboral:
# motor apagado y rf-live activo.
STANDBY=0
if ! systemctl is-enabled --quiet rf-capturador 2>/dev/null && ! systemctl is-active --quiet rf-capturador 2>/dev/null; then
    STANDBY=1
    echo "[ojos] rf-capturador disabled+inactive -> motor en standby"
fi
if [ "$STANDBY" = 1 ]; then
    # Respetar unidades apagadas a mano: `systemctl restart` las arrancaría.
    ACTIVOS=""
    for s in $SERVICES; do
        if systemctl is-enabled --quiet "$s" 2>/dev/null || systemctl is-active --quiet "$s" 2>/dev/null; then
            ACTIVOS="$ACTIVOS $s"
        else
            echo "[ojos] $s disabled+inactive: se mantiene apagado"
        fi
    done
    SERVICES="$ACTIVOS"
fi

if [ -z "${SERVICES// /}" ]; then
    echo "[ojos] standby: no hay servicios activos que reiniciar."
    exit 0
fi

echo "[ojos] reiniciando servicios personales"
systemctl restart $SERVICES
sleep 4
FAILSV=0
for s in $SERVICES; do
    st="$(systemctl is-active "$s" 2>/dev/null || true)"
    printf '  %-24s %s\n' "$s" "$st"
    [ "$st" = "active" ] || FAILSV=1
done
if [ "$FAILSV" = 1 ]; then
    echo "[ojos] AVISO: algún servicio no está active; revisa journalctl" >&2
    exit 5
fi
echo "[ojos] deploy OK"
