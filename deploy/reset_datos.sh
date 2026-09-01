#!/usr/bin/env bash
# =============================================================================
# reset_datos.sh — Reinicio del sistema de reconocimiento facial.
#
# Vuelve a cero los datos de identidad y movimiento para que el sistema
# empiece a capturar y aprender caras NUEVAS desde cero, conservando toda la
# configuración (cámaras, líneas, plano, local, usuarios, auto-login).
#
# Qué BORRA:
#   BD (tablas de datos):    personas, estancias, fotos, videos, cruces_lineas,
#                            fichajes, alarmas, calibraciones, foto_audits,
#                            foto_audit_events
#   Galería (motor):         motor/bbdd_reconocimiento/*/face_enc_v2
#   Media / colas (motor):   caras/, videos/, videos_archivo/, feedback/,
#                            revision/, removidas/, inicial/, alinear_caras/,
#                            fotos_lineas/, videos_lineas/, photo_queue/
#
# Qué CONSERVA:
#   BD (config):             camaras, locales, lineas, lineas_plano, nodos,
#                            senderos, senderos_puntos, dispositivos_autologin,
#                            alarmas_telefonos
#
# USO:  sudo bash deploy/reset_datos.sh
#   El script detiene los servicios que escriben datos, borra, y rearranca.
#   Pasa --dry-run para listar lo que se va a borrar sin tocar nada.
# =============================================================================
set -euo pipefail

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

# --- Localización del proyecto -----------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROYECTO="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOCAL_ID=1   # local activo (directorios bajo motor/.../<local_id>)

# Credenciales BD desde .env del proyecto (misma fuente que libs/db.php)
ENV_FILE="${PROYECTO}/.env"
BD_NAME="reconocimientofacial"
BD_USER=""
BD_PASS=""
if [[ -f "${ENV_FILE}" ]]; then
  while IFS='=' read -r k v; do
    k="${k// /}"; v="${v// /}"
    case "${k}" in
      RF_DB_NAME) BD_NAME="${v}" ;;
      RF_DB_USER) BD_USER="${v}" ;;
      RF_DB_PASS) BD_PASS="${v}" ;;
    esac
  done < <(grep -E '^RF_DB_' "${ENV_FILE}" || true)
fi

# Servicios que escriben datos (se detienen durante el reset y se rearrancan).
# Incluye rf-live (streaming MJPEG): aunque no escribe BD, es un daemon del
# proyecto y debe rearrancarse para un reset 100% limpio (lección 2026-09-01:
# quedó corriendo desde antes del reset). rf-calibra y rf-vigilar-deriva NO
# van aquí: son one-shots lanzados por sus timers (rf-calibra.timer, rf-
# vigilar-deriva.timer) y se relanzan solos en su horario.
SERVICIOS=(rf-capturador rf-detector rf-clasificador rf-conciliador \
           rf-vinculador rf-alarmador rf-photo rf-panel-control rf-live)

# Tablas de DATOS (se vacían) vs CONFIG (se conservan)
TABLAS_DATOS=(personas estancias fotos videos cruces_lineas fichajes \
              alarmas calibraciones foto_audits foto_audit_events)

# Directorios de datos del motor que se borran
RUTAS_BORRAR=(
  "motor/bbdd_reconocimiento/${LOCAL_ID}/face_enc_v2"
  "motor/bbdd_reconocimiento/${LOCAL_ID}/face_enc_v2.lock"
  "motor/caras/${LOCAL_ID}"
  "motor/caras/sinclasificar"
  "motor/videos/${LOCAL_ID}"
  "motor/videos_archivo/${LOCAL_ID}"
  "motor/feedback/${LOCAL_ID}"
  "motor/revision/${LOCAL_ID}"
  "motor/removidas"
  "motor/inicial"
  "motor/alinear_caras"
  "motor/fotos_lineas"
  "motor/videos_lineas"
  "motor/photo_queue"
)

# =============================================================================
log()  { printf '[reset] %s\n' "$*"; }
die()  { printf '[reset] ERROR: %s\n' "$*" >&2; exit 1; }

cmd() { # cmd <desc> <comando...>
  local desc="$1"; shift
  log "${desc}"
  [[ ${DRY_RUN} -eq 1 ]] && { log "  (dry-run) ${*}"; return 0; }
  "$@"
}

[[ ${DRY_RUN} -eq 1 ]] && log "MODO DRY-RUN: no se ejecutará nada, solo se muestra el plan."

[[ -z "${BD_USER}" ]] && BD_USER="${RF_DB_USER:-}"   # fallback a entorno
[[ -z "${BD_PASS}" ]] && BD_PASS="${RF_DB_PASS:-}"
[[ -z "${BD_USER}" ]] && die "No se pudo leer RF_DB_USER de ${ENV_FILE} ni del entorno"
[[ ${EUID} -eq 0 ]] || [[ ${DRY_RUN} -eq 1 ]] || die "Ejecutar como root: sudo bash ${0}"

# =============================================================================
# FASE A — detener servicios
# =============================================================================
log "FASE A: deteniendo servicios que escriben datos..."
for svc in "${SERVICIOS[@]}"; do
  if systemctl is-active --quiet "${svc}" 2>/dev/null; then
    cmd "Detener ${svc}" systemctl stop "${svc}"
  else
    log "  ${svc}: ya estaba detenido"
  fi
done

# Patrones de procesos RF (se matan con -9; hijos/daemons que systemd no captura)
PATRONES_KILL=(
  "clasificador.py"
  "procesa_video.py"
  "archiva_video.py"
  "guarda_movimientosV3.py"
  "pose.py"
  "photo_worker.py"
  "cruces.py"
  "reprocesar.py"
  "enrolamiento.py"
  "juntar_personas"
  "separar_personas.py"
  "detectar_mezclados.py"
  "calibrador.py"
  "capturador.php"
  "detector.php"
  "clasificadorV2.php"
  "conciliador.php"
  "vinculador.php"
  "alarmador.php"
  "procesos_panel_control.php"
  "mjpeg-stream.js"
)

matar_procesos() { # mata procesos RF vivos y espera a que terminen (con timeout)
  local pat pid self_pid
  self_pid="$$"
  for pat in "${PATRONES_KILL[@]}"; do
    # -f casa sobre la línea de comando; excluye este script y su propio shell
    pkill -9 -f "${pat}" 2>/dev/null || true
  done
  # Barrido extra: cualquier python/php cuyo args contenga la ruta del proyecto
  pkill -9 -f "${PROYECTO}/motor" 2>/dev/null || true
  pkill -9 -f "${PROYECTO}/capturador.php" 2>/dev/null || true
  pkill -9 -f "${PROYECTO}/detector.php" 2>/dev/null || true
  pkill -9 -f "${PROYECTO}/clasificadorV2.php" 2>/dev/null || true
  pkill -9 -f "${PROYECTO}/conciliador.php" 2>/dev/null || true
  pkill -9 -f "${PROYECTO}/vinculador.php" 2>/dev/null || true
  pkill -9 -f "${PROYECTO}/alarmador.php" 2>/dev/null || true
  # Esperar hasta 15 s a que no quede ninguno
  local i=0
  while (( i < 15 )); do
    local restantes
    restantes=$(ps -eo args | grep -F "${PROYECTO}" | grep -v grep | grep -v "reset_datos.sh" | grep -v "bash" | wc -l)
    (( restantes <= 1 )) && break
    sleep 1; i=$((i+1))
  done
  log "  procesos RF restantes tras matar: ${restantes}"
}

# =============================================================================
# FASE A2 — matar TODOS los procesos RF (hijos/huérfanos que systemd no cubre)
# =============================================================================
log "FASE A2: matando todos los procesos RF del proyecto..."
cmd "Matar procesos RF" matar_procesos

# =============================================================================
# FASE B — vaciar BD (tablas de datos)
# =============================================================================
log "FASE B: vaciando tablas de datos en BD ${BD_NAME}..."
MYSQL=(mysql -u"${BD_USER}")
[[ -n "${BD_PASS}" ]] && MYSQL+=( -p"${BD_PASS}" )

if [[ ${DRY_RUN} -eq 1 ]]; then
  for t in "${TABLAS_DATOS[@]}"; do log "  (dry-run) TRUNCATE ${t}"; done
else
  # Solo trunca las tablas que EXISTAN (esquemas más viejos pueden no tener
  # foto_audits/foto_audit_events, etc. — no debe abortar el reset)
  inlist=""
  for t in "${TABLAS_DATOS[@]}"; do inlist+="'${t}',"; done
  inlist="${inlist%,}"
  existentes=$("${MYSQL[@]}" -N -e \
    "SELECT TABLE_NAME FROM information_schema.TABLES
     WHERE TABLE_SCHEMA='${BD_NAME}'
       AND TABLE_NAME IN (${inlist});" 2>/dev/null)
  # Construye cada TRUNCATE como sentencia propia terminada en ';'
  truncs=()
  for t in "${TABLAS_DATOS[@]}"; do
    if grep -qx "${t}" <<< "${existentes}"; then
      truncs+=( "TRUNCATE TABLE ${t};" )
    else
      log "  (tabla no existe, omitida) ${t}"
    fi
  done
  printf '%s\n' "SET FOREIGN_KEY_CHECKS=0;" \
    "${truncs[@]}" \
    "SET FOREIGN_KEY_CHECKS=1;" \
    | "${MYSQL[@]}" "${BD_NAME}" \
    || die "fallo vaciando BD"
  # Verificación
  verificacion=$("${MYSQL[@]}" -N -e \
    "SELECT CONCAT(t.tab,'=',t.c) FROM (
       SELECT 'personas' tab,COUNT(*) c FROM ${BD_NAME}.personas
       UNION ALL SELECT 'videos',COUNT(*) FROM ${BD_NAME}.videos
       UNION ALL SELECT 'fotos',COUNT(*) FROM ${BD_NAME}.fotos
       UNION ALL SELECT 'estancias',COUNT(*) FROM ${BD_NAME}.estancias
       UNION ALL SELECT 'cruces_lineas',COUNT(*) FROM ${BD_NAME}.cruces_lineas
     ) t;" 2>/dev/null)
  log "  verificación: ${verificacion}"
fi

# =============================================================================
# FASE C — borrar la memoria/caras del motor
# =============================================================================
log "FASE C: borrando galería y datos del motor..."
for r in "${RUTAS_BORRAR[@]}"; do
  ruta="${PROYECTO}/${r}"
  if [[ -e "${ruta}" ]]; then
    cmd "Borrar ${r}" rm -rf "${ruta}"
  else
    log "  (no existe) ${r}"
  fi
done
# Recrear directorios base que el motor espera como raíz de local
cmd "Recrear ${PROYECTO}/motor/caras/${LOCAL_ID}"  mkdir -p "${PROYECTO}/motor/caras/${LOCAL_ID}"
cmd "Recrear ${PROYECTO}/motor/videos/${LOCAL_ID}" mkdir -p "${PROYECTO}/motor/videos/${LOCAL_ID}"
cmd "Recrear ${PROYECTO}/motor/videos_archivo/${LOCAL_ID}" mkdir -p "${PROYECTO}/motor/videos_archivo/${LOCAL_ID}"

# Limpiar markers de procesado/archivado de aux/ (detector.php cuenta estos
# markers como slots de CONFIG_LIMITE_VIDEOS/CONFIG_LIMITE_ARCHIVA). Un marker
# huérfano de un vídeo ya borrado por el reset saturaría el slot y bloquearía
# procesa_video.py (lección 2026-09-01). Se borran los markers .mp4.txt/.avi.txt
# de procesa y los archiva_*.txt; se conservan los contadores .intentos.
for m in "${PROYECTO}"/aux/*.mp4.txt "${PROYECTO}"/aux/*.avi.txt "${PROYECTO}"/aux/archiva_*.txt; do
  if [[ -f "${m}" ]]; then
    cmd "Borrar marker ${m}" rm -f "${m}"
  fi
done

# =============================================================================
# FASE D — rearrancar servicios
# =============================================================================
log "FASE D: rearrancando servicios..."
for svc in "${SERVICIOS[@]}"; do
  cmd "Arrancar ${svc}" systemctl restart "${svc}" 2>/dev/null || true
done

log "Reset completado. Verificar con: systemctl status rf-* y el panel web."
[[ ${DRY_RUN} -eq 1 ]] && log "DRY-RUN: nada se ha modificado."
