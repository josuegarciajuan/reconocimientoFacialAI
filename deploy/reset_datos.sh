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
#                            fotos_lineas/, videos_lineas/, photo_queue/,
#                            dedup/, audit_queue/
#
# Qué CONSERVA:
#   BD (config):             camaras, locales, lineas, lineas_plano, nodos,
#                            senderos, senderos_puntos, dispositivos_autologin,
#                            alarmas_telefonos
#
# USO:  sudo bash deploy/reset_datos.sh
#   El script: (A) detiene los servicios, (A2) MATA TODOS los procesos RF
#   (incluidos huérfanos/hijos que systemd no cubre), (B) vacía la BD,
#   (C) borra la galería/media/markers del motor y (D) REARCA los servicios y
#   rearma los timers. Robusto por SSH: mata por PID sin matarse a sí mismo.
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
  # Dedup persistente y cola de auditoría del clasificador (P1/A1, 2026-09-02):
  # datos runtime de identidad del último merge; sin borrarlos el reset NO sería
  # limpio (el dedup suprime caras ya vistas y audit_queue re-ingesta sidecars).
  "motor/dedup"
  "motor/audit_queue"
  # Registro de retratos por identidad (Fase 2, 2026-09-02): fotos de referencia
  # para VLM/OpenAI/silueta; debe vaciarse con el reset para empezar de cero.
  "motor/portraits/${LOCAL_ID}"
  # Cola de consolidación al nacer (Fase 5/M6, 2026-09-02).
  "motor/pending/${LOCAL_ID}"
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

# Patrones de procesos RF (se matan con -9; hijos/daemons que systemd no captura).
# Se matan SIEMPRE por PID recogido con pgrep, excluyendo el árbol de este script
# (su propio shell y la sesión SSH que lo invoca), para que FASE A2 jamás se
# suicide ni corte el reset a mitad (lección 2026-09-02: pkill -f con la ruta del
# proyecto mataba el wrapper ssh y el script moría en FASE A2 sin llegar a B/C/D).
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
  "vigilar_deriva.py"
  "capturador.php"
  "detector.php"
  "clasificadorV2.php"
  "conciliador.php"
  "vinculador.php"
  "alarmador.php"
  "procesos_panel_control.php"
  "mjpeg-stream.js"
)

# PIDs de la sesión actual (este script + su shell + ancestros SSH): NUNCA matar.
_arbol_no_tocar() {
  local p=$$ out=""
  while [[ "$p" =~ ^[0-9]+$ ]] && [[ "$p" -gt 1 ]]; do
    out="$out $p"
    p=$(awk '{print $4}' "/proc/${p}/stat" 2>/dev/null) || break
  done
  printf '%s' "$out"
}

matar_procesos() { # mata por PID los procesos RF vivos, esperando a que terminen
  local no_tocar no_tocar_regex pat base pids pid seen="" targets=()
  no_tocar="$(_arbol_no_tocar)"
  # regex "^(p1|p2|...)$" para filtrar esos PIDs del conteo final
  no_tocar_regex=$(printf '%s\n' "$no_tocar" | tr ' ' '\n' | sed '/^$/d' | paste -sd'|' -)

  # 1) Recoger candidatos por patrón + rutas del proyecto
  pids=""
  for pat in "${PATRONES_KILL[@]}"; do
    pids="$pids $(pgrep -f -- "${pat}" 2>/dev/null || true)"
  done
  pids="$pids $(pgrep -f -- "${PROYECTO}/motor" 2>/dev/null || true)"
  for base in capturador.php detector.php clasificadorV2.php conciliador.php \
              vinculador.php alarmador.php procesos_panel_control.php; do
    pids="$pids $(pgrep -f -- "${PROYECTO}/${base}" 2>/dev/null || true)"
  done

  # 2) PIDs únicos excluyendo la sesión actual (nunca matarse a sí mismo)
  for pid in $pids; do
    case " $no_tocar " in
      *" ${pid} "*) continue ;;        # sesión/ssh actual: se ignora
    esac
    case " $seen " in
      *" ${pid} "*) ;;                 # duplicado
      *) seen="$seen $pid"; targets+=("$pid") ;;
    esac
  done

  if [[ ${#targets[@]} -eq 0 ]]; then
    log "  ningún proceso RF vivo que matar"
    return 0
  fi

  log "  matando PIDs: ${targets[*]}"
  kill -9 "${targets[@]}" 2>/dev/null || true

  # 3) Esperar hasta 20 s a que no queden procesos RF (fuera de la sesión actual)
  local i=0 restantes=999
  while (( i < 20 )); do
    restantes=$( { for pat in "${PATRONES_KILL[@]}"; do pgrep -f -- "$pat"; done
                   pgrep -f -- "${PROYECTO}/motor"; } 2>/dev/null \
                 | grep -vE "^(${no_tocar_regex})$" | wc -l ) || restantes=0
    (( restantes == 0 )) && break
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
# FASE D — rearrancar servicios y timers (encendido total desde cero)
# =============================================================================
log "FASE D: rearrancando servicios y timers..."
for svc in "${SERVICIOS[@]}"; do
  cmd "Arrancar ${svc}" systemctl restart "${svc}" 2>/dev/null || true
done
# Rearmar los timers de one-shots (rf-calibra, rf-vigilar-deriva): se lanzan en
# su horario; restart del timer lo fuerza a reprogramarse tras el reset limpio.
for t in rf-calibra.timer rf-vigilar-deriva.timer; do
  if systemctl list-unit-files "${t}" >/dev/null 2>&1; then
    cmd "Rearmar ${t}" systemctl restart "${t}" 2>/dev/null || true
  fi
done

log "Reset completado. Verificar con: systemctl status rf-* y el panel web."
[[ ${DRY_RUN} -eq 1 ]] && log "DRY-RUN: nada se ha modificado."
