#!/usr/bin/env bash
# =============================================================================
# init_ojos.sh — provisión única de la instancia personal `ojos` en liveyourdre2.
#
# Crea BD/usuario propios, importa un esquema SIN DATOS, archiva los datos de
# desarrollo existentes (nunca los borra), siembra el local y las 5 cámaras,
# instala PHP-FPM/Apache/gate y arranca los servicios con el .env de `ojos`.
#
# Uso (root):  bash deploy/ojos/init_ojos.sh
# Requisitos: hostname liveyourdre2, MariaDB local, PHP 8.3, Apache, bridge de
# cámaras en 127.0.0.1:8111 y SuperServer en 127.0.0.1:8110.
# =============================================================================
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="$DIR/.env"
SECRETS_DIR="/root/onx-secrets/ojos"
CRED_FILE="$SECRETS_DIR/credentials.env"
BACKUP_DIR="/root/onx-backups/ojos-preinit-$(date +%Y%m%dT%H%M%SZ)"

[ "$(id -u)" -eq 0 ] || { echo "ERROR: ejecuta como root" >&2; exit 2; }
[ "$(hostname)" = "liveyourdre2" ] || echo "AVISO: hostname $(hostname), se esperaba liveyourdre2"

mkdir -p "$SECRETS_DIR" && chmod 700 "$SECRETS_DIR"
if [ -f "$CRED_FILE" ]; then
    # shellcheck disable=SC1090
    . "$CRED_FILE"
fi
DB_NAME="${DB_NAME:-reconocimientofacial_ojos}"
DB_USER="${DB_USER:-rf_ojos}"
DB_PASS="${DB_PASS:-$(openssl rand -hex 24)}"
ADMIN_USER="${ADMIN_USER:-ojos}"
ADMIN_PASS="${ADMIN_PASS:-$(openssl rand -hex 12)}"
LIVE_TOKEN="${LIVE_TOKEN:-$(openssl rand -hex 32)}"
umask 077
cat > "$CRED_FILE" <<CREDS
DB_NAME=$DB_NAME
DB_USER=$DB_USER
DB_PASS=$DB_PASS
ADMIN_USER=$ADMIN_USER
ADMIN_PASS=$ADMIN_PASS
LIVE_TOKEN=$LIVE_TOKEN
CREDS
chmod 600 "$CRED_FILE"

# Backup del .env actual la primera vez.
if [ ! -f "$SECRETS_DIR/env.pre-ojos" ] && [ -f "$ENV_FILE" ]; then
    cp -a "$ENV_FILE" "$SECRETS_DIR/env.pre-ojos"
    chmod 600 "$SECRETS_DIR/env.pre-ojos"
fi

# --- 1. Archivar datos runtime de desarrollo (no borrar) --------------------
if [ ! -f "$SECRETS_DIR/initialized-data" ]; then
    mkdir -p "$BACKUP_DIR"
    archive_dir() {
        local rel="$1" src="$DIR/$rel"
        if [ -d "$src" ] && [ -n "$(find "$src" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]; then
            mkdir -p "$BACKUP_DIR/$(dirname "$rel")"
            mv "$src" "$BACKUP_DIR/$rel"
            echo "[ojos] archivado $rel"
        fi
        mkdir -p "$src"
    }
    for rel in \
        aux motor/logs motor/caras motor/removidas motor/bbdd_reconocimiento \
        motor/fotos_lineas motor/videos motor/videos_archivo motor/alinear_caras \
        motor/laterales_test motor/cosas_en_la_cara motor/eval/data motor/feedback \
        motor/revision motor/revision_cuerpos motor/backups motor/calib motor/llm_cache \
        motor/calibrador motor/reagrupar_out motor/quality_probe motor/photo_queue \
        motor/photo_evidence motor/reprocesado motor/pending motor/portraits \
        motor/audit motor/audit_queue motor/dedup \
        admin/caras_procesadas admin/fotos_originales admin/fotos_camara \
        admin/files/videos_registro admin/files/videos_registro_posiciones \
        admin/files/videos_registro_pruebas admin/files/videos_registro_resultados \
        admin/files/videos_registro_videos admin/files/videos_registro_videos_partidos \
        admin/pages/config/planos libs/threads_files_aux; do
        archive_dir "$rel"
    done
    echo "$BACKUP_DIR" > "$SECRETS_DIR/last-data-backup"
    touch "$SECRETS_DIR/initialized-data"
else
    echo "[ojos] datos ya inicializados; no se archiva de nuevo"
fi

# --- 2. BD y usuario propios ------------------------------------------------
mysql -uroot -e "CREATE DATABASE IF NOT EXISTS \`$DB_NAME\` CHARACTER SET latin1 COLLATE latin1_swedish_ci;"
mysql -uroot -e "CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';"
mysql -uroot -e "ALTER USER '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';"
mysql -uroot -e "GRANT ALL PRIVILEGES ON \`$DB_NAME\`.* TO '$DB_USER'@'localhost'; FLUSH PRIVILEGES;"

TABLES="$(mysql -N -uroot "$DB_NAME" -e 'SHOW TABLES' | wc -l | tr -d ' ')"
if [ "$TABLES" = "0" ]; then
    echo "[ojos] importando esquema limpio (sin datos)"
    mysql -uroot "$DB_NAME" < "$DIR/deploy/ojos/schema.sql"
else
    echo "[ojos] la BD ya tiene $TABLES tablas; no se reimporta"
fi

# Marcar como aplicadas las migraciones históricas ya incluidas en el esquema.
ls -1 "$DIR"/sql/*.sql 2>/dev/null | xargs -r -n1 basename | sort > "$SECRETS_DIR/applied_sql.txt"

# --- 3. Local y 5 cámaras (solo si están vacíos) ----------------------------
mysql -uroot "$DB_NAME" <<SQL
INSERT INTO locales (id, nombre, aforo_max, aforo_actual, usuario, passw, created)
VALUES (1, 'Ojos', 0, 0, '', '', NOW())
ON DUPLICATE KEY UPDATE nombre = VALUES(nombre), aforo_max = VALUES(aforo_max), aforo_actual = VALUES(aforo_actual);
SQL

CAMS="$(mysql -N -uroot "$DB_NAME" -e 'SELECT COUNT(*) FROM camaras')"
if [ "$CAMS" = "0" ]; then
    echo "[ojos] sembrando 5 cámaras"
    mysql -uroot "$DB_NAME" <<'SQL'
INSERT INTO camaras
 (id, local_id, descripcion, directorio, url_conexion, sistema, x, y, puerta, salida, encendida,
  ipcamlive_alias, segundos_analizar, porcentaje_mov, dontCare, fps, maximo_videos,
  redimesionframe, sensibilidad, url_desdeserver, orden, threshold, blur, dilate,
  seg_antes, seg_despues, alarma_heredar, alarma_24h)
VALUES
 (1,1,'ESP32 oficina',NULL,'http://127.0.0.1:8111/camaraip/stream?camera=esp32-oficina',0,0,0,0,0,1,'-',2,35,120,14,60,60,1,'http://127.0.0.1:8111/camaraip/stream?camera=esp32-oficina',1,15,15,2,4,4,1,0),
 (2,1,'Webcam oficina',NULL,'http://127.0.0.1:8111/camaraip/stream?camera=cam-oficina',0,0,0,0,0,1,'-',2,35,120,14,60,60,1,'http://127.0.0.1:8111/camaraip/stream?camera=cam-oficina',2,15,15,2,4,4,1,0),
 (3,1,'ONX josue',NULL,'http://127.0.0.1:8111/camaraip/stream?camera=onx-josue',0,0,0,0,0,1,'-',2,35,120,14,60,60,1,'http://127.0.0.1:8111/camaraip/stream?camera=onx-josue',3,15,15,2,4,4,1,0),
 (4,1,'Cam portatil',NULL,'http://127.0.0.1:8111/camaraip/stream?camera=cam-portatil',0,0,0,0,0,1,'-',2,35,120,14,60,60,1,'http://127.0.0.1:8111/camaraip/stream?camera=cam-portatil',4,15,15,2,4,4,1,0),
 (5,1,'ESP32 josue',NULL,'http://127.0.0.1:8111/camaraip/stream?camera=esp32-josue',0,0,0,0,0,1,'-',2,35,120,14,60,60,1,'http://127.0.0.1:8111/camaraip/stream?camera=esp32-josue',5,15,15,2,4,4,1,0);
SQL
else
    echo "[ojos] la tabla camaras ya tiene $CAMS filas; no se siembra"
fi

# --- 4. .env de la instancia (sin imprimir secretos) ------------------------
OJOS_DB_NAME="$DB_NAME" OJOS_DB_USER="$DB_USER" OJOS_DB_PASS="$DB_PASS" \
OJOS_ADMIN_USER="$ADMIN_USER" OJOS_ADMIN_PASS="$ADMIN_PASS" OJOS_LIVE_TOKEN="$LIVE_TOKEN" \
python3 - "$ENV_FILE" <<'PY'
import os
import shlex
import sys
from pathlib import Path

path = Path(sys.argv[1])
desired = {
    "RF_DB_NAME": os.environ["OJOS_DB_NAME"],
    "RF_DB_USER": os.environ["OJOS_DB_USER"],
    "RF_DB_PASS": os.environ["OJOS_DB_PASS"],
    "RF_DB_HOST": "localhost",
    "RF_INSTANCE": "ojos",
    "RF_BASE_PATH": "/ojos/",
    "RF_SUPERSERVER_PROJECT": "ojos",
    "RF_URL": "https://josue.ink/ojos/",
    "RF_URL_INTERNAL": "http://127.0.0.1:8086/ojos/",
    "RF_WS_URL": "http://127.0.0.1:8086/ojos/ws.php",
    "RF_RUTA": "/root/reconocimientoFacial/",
    "RF_PYTHON": "/root/reconocimientoFacial/motor/venv/bin/python",
    "RF_LIVE_TOKEN": os.environ["OJOS_LIVE_TOKEN"],
    "RF_ADMIN_USER": os.environ["OJOS_ADMIN_USER"],
    "RF_ADMIN_PASS": os.environ["OJOS_ADMIN_PASS"],
    "RF_AUTOLOGIN_ENABLED": "0",
    "RF_AUTOLOGIN_COOKIE": "rf_autologin_ojos",
    "RF_BRAND_NAME": "Ojos · Vigilancia personal",
    "RF_BRAND_SHORT": "Ojos",
    "RF_BRAND_TOPBAR": "Ojos",
    "RF_BRAND_SUB": "El ojo que todo lo ve",
    "RF_BRAND_SUB_PRO": "Reconocimiento facial · uso personal",
    "RF_BRAND_DESC": "Ojos · Vigilancia personal con reconocimiento facial.",
    "RF_BRAND_THEME_COLOR": "#16121a",
    "RF_BRAND_BG_COLOR": "#0b0a0e",
    "RF_BRAND_ICON_DIR": "files/branding",
    "RF_BRAND_ICON_192": "ojos-icon-192.png",
    "RF_BRAND_ICON_512": "ojos-icon-512.png",
    "RF_BRAND_ICON_MASKABLE": "ojos-icon-512.png",
    "RF_BRAND_LOGIN_LOGO": "./files/branding/ojos-logo.png",
    "RF_BRAND_PWA_EMOJI": "👁️",
    "RF_BRAND_INSTALL_TITLE": "Instalar Ojos",
    "RF_BRAND_INSTALL_SUB": "Tu ojo personal, como una app: sin barra del navegador y siempre a mano.",
    "RF_CAMERA_STATUS_URL": "http://127.0.0.1:8111/camaraip/status",
    "RF_SNAP_WIDTH": "640",
    "RF_FTP_USER": "",
    "RF_FTP_PASS": "",
    "RF_LLM_API_KEY": "",
    "RF_OPENAI_ENABLED": "0",
    "RF_VLM_ENABLED": "0",
}
drop = {"RF_ADMIN_PASS_HASH"}
def fmt(key, value):
    return f"{key}={shlex.quote(str(value))}" if str(value) != "" else f"{key}="

lines = path.read_text().splitlines() if path.exists() else []
out, seen = [], set()
for line in lines:
    key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
    if key in drop:
        continue
    if key in desired:
        out.append(fmt(key, desired[key]))
        seen.add(key)
    else:
        out.append(line)
for key, value in desired.items():
    if key not in seen:
        out.append(fmt(key, value))
path.write_text("\n".join(out) + "\n")
PY
chown root:www-data "$ENV_FILE" 2>/dev/null || true
chmod 640 "$ENV_FILE"

# --- 5. Permisos de datos ---------------------------------------------------
for d in aux motor/logs motor/caras motor/bbdd_reconocimiento motor/videos \
         motor/videos_archivo motor/fotos_lineas motor/photo_queue motor/photo_evidence \
         motor/backups motor/calibrador motor/revision motor/revision_cuerpos \
         admin/caras_procesadas admin/fotos_originales admin/fotos_camara \
         admin/files/videos_registro admin/files/videos_registro_posiciones \
         admin/files/videos_registro_pruebas admin/files/videos_registro_resultados \
         admin/files/videos_registro_videos admin/files/videos_registro_videos_partidos \
         admin/pages/config/planos libs/threads_files_aux; do
    mkdir -p "$DIR/$d"
done
chmod 777 "$DIR/libs/threads_files_aux" "$DIR/admin/caras_procesadas" \
    "$DIR/admin/fotos_originales" "$DIR/admin/fotos_camara" \
    "$DIR/admin/files/videos_registro" "$DIR/admin/files/videos_registro_posiciones" \
    "$DIR/admin/files/videos_registro_resultados" "$DIR/admin/files/videos_registro_videos" \
    "$DIR/admin/pages/config/planos" 2>/dev/null || true

# --- 6. PHP-FPM + Apache + panel-gate --------------------------------------
mkdir -p /var/lib/php/sessions-ojos
chown www-data:www-data /var/lib/php/sessions-ojos
chmod 700 /var/lib/php/sessions-ojos

SOCK="$(ls -1 /run/php/php*-fpm.sock 2>/dev/null | sort -V | tail -1 || true)"
[ -n "$SOCK" ] || { echo "ERROR: no hay socket php-fpm" >&2; exit 1; }
PHPVER="$(basename "$SOCK" | sed -E 's/php([0-9.]+)-fpm.sock/\1/')"
cp "$DIR/deploy/ojos/ojos-fpm.conf" "/etc/php/$PHPVER/fpm/pool.d/ojos.conf"
/usr/sbin/php-fpm"$PHPVER" -t
systemctl restart "php$PHPVER-fpm"

python3 "$DIR/deploy/ojos/patch_apache.py"
python3 "$DIR/deploy/ojos/patch_panel_gate.py"
apache2ctl configtest
systemctl reload apache2
systemctl restart panel-gate

# --- 7. Servicios del motor (instancia personal) ---------------------------
bash "$DIR/deploy/install_services.sh" >/dev/null
systemctl daemon-reload
systemctl enable --now \
    rf-capturador rf-detector rf-clasificador rf-clasificador-serve \
    rf-panel-control rf-live rf-conciliador rf-vinculador rf-alarmador rf-photo
systemctl enable --now rf-calibra.timer rf-vigilar-deriva.timer rf-reprocesa.timer rf-reten-backups.timer 2>/dev/null || true

# Modo inicial local; se sube a superserver tras verificar el pipeline.
mkdir -p /var/lib/taildeck/projects
if [ ! -f /var/lib/taildeck/projects/ojos.mode ]; then
    echo local > /var/lib/taildeck/projects/ojos.mode
fi

echo "[ojos] init completado"
echo "  BD: $DB_NAME (usuario $DB_USER)"
echo "  Credenciales: $CRED_FILE (0600)"
echo "  Datos dev archivados en: $(cat "$SECRETS_DIR/last-data-backup" 2>/dev/null || echo 'n/a')"
echo "  Panel: https://josue.ink/ojos/admin/"
echo "  Modo SuperServer: /var/lib/taildeck/projects/ojos.mode (ahora $(cat /var/lib/taildeck/projects/ojos.mode 2>/dev/null || echo local))"
