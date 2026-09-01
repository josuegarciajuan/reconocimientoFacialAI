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

# Servicios que escriben datos (se detienen durante el reset y se rearrancan)
SERVICIOS=(rf-capturador rf-detector rf-clasificador rf-conciliador \
           rf-vinculador rf-alarmador rf-photo rf-panel-control)

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

# =============================================================================
# FASE B — vaciar BD (tablas de datos)
# =============================================================================
log "FASE B: vaciando tablas de datos en BD ${BD_NAME}..."
MYSQL=(mysql -u"${BD_USER}")
[[ -n "${BD_PASS}" ]] && MYSQL+=( -p"${BD_PASS}" )

if [[ ${DRY_RUN} -eq 1 ]]; then
  for t in "${TABLAS_DATOS[@]}"; do log "  (dry-run) TRUNCATE ${t}"; done
else
  # Construye cada TRUNCATE como sentencia propia terminada en ';'
  truncs=()
  for t in "${TABLAS_DATOS[@]}"; do truncs+=( "TRUNCATE TABLE ${t};" ); done
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

# =============================================================================
# FASE D — rearrancar servicios
# =============================================================================
log "FASE D: rearrancando servicios..."
for svc in "${SERVICIOS[@]}"; do
  cmd "Arrancar ${svc}" systemctl restart "${svc}" 2>/dev/null || true
done

log "Reset completado. Verificar con: systemctl status rf-* y el panel web."
[[ ${DRY_RUN} -eq 1 ]] && log "DRY-RUN: nada se ha modificado."
