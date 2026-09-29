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
#                            fichajes, alarmas, foto_audits, foto_audit_events,
#                            personas_avatar
#   Galería (motor):         motor/bbdd_reconocimiento/*/face_enc_v2
#   Media / colas (motor):   caras/, videos/, videos_archivo/, feedback/,
#                            revision/, removidas/, inicial/, alinear_caras/,
#                            fotos_lineas/, videos_lineas/, photo_queue/,
#                            dedup/, audit_queue/, llm_cache/
#   Estado runtime (motor):  logs/, backups/ (incl. .bak de face_enc_v2),
#                            revision_cuerpos/, calibrador/deriva/ y la cola de
#                            marcadores aux/ (markers, .intentos, procesar_*.txt)
#   Fotos publicadas (panel): admin/caras_procesadas/ (jpg + avatares/) y los
#                            uploads de registro (admin/files/videos_registro*)
#
# Qué CONSERVA:
#   BD (config):             camaras, locales, lineas, lineas_plano, nodos,
#                            senderos, senderos_puntos, dispositivos_autologin,
#                            alarmas_telefonos
#   BD (calibración):        calibraciones (journal de parámetros de análisis
#                            por cámara; NO es identidad)
#   Runtime (motor):         models/, venv/
#
# USO:  sudo bash deploy/reset_datos.sh [--hold N] [--dry-run]
#   El script: (A) detiene los servicios, (A2) MATA TODOS los procesos RF
#   (incluidos huérfanos/hijos/ffmpeg que systemd no cubre) y VERIFICA que no
#   queda ninguno vivo, (B) vacía la BD, (C) borra galería/media/estado runtime
#   y (D) REARCA los servicios y rearma los timers. Robusto por SSH: mata por
#   PID sin matarse a sí mismo.
#   --hold N : tras parar, espera N segundos y re-verifica que todo sigue caído
#              antes de rearrancar (evidencia visible de parada total).
#   --dry-run: lista lo que se va a borrar sin tocar nada.
#
# GUARDA ANTI-TRAMPA (2026-09-29): tras vaciar la galería, un clasificador con
#   RF_AUTOENROLL_NEW inactivo no puede producir ningún `match` y no crearía
#   identidades nunca (todo a revisión; panel de Visitantes vacío). La FASE D
#   asegura RF_AUTOENROLL_NEW=1 en `.env` (con copia .bak) antes de rearrancar.
#   Además el motor fuerza el alta cuando la galería está vacía (bootstrap en
#   `debe_crear_identidad`), por si el flag se desactivara de nuevo.
# =============================================================================
set -euo pipefail

DRY_RUN=0
HOLD=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --hold) HOLD="${2:-0}"; shift ;;
    --hold=*) HOLD="${1#--hold=}" ;;
    -h|--help) sed -n '2,42p' "$0"; exit 0 ;;
    *) printf '[reset] ERROR: flag desconocida: %s\n' "$1" >&2; exit 2 ;;
  esac
  shift
done
[[ "${HOLD}" =~ ^[0-9]+$ ]] || { printf '[reset] ERROR: --hold requiere un entero\n' >&2; exit 2; }

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
              alarmas foto_audits foto_audit_events personas_avatar)

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
  # Fotos publicadas y avatares del panel (2026-09-25): al truncar `fotos` y
  # `personas` los AUTO_INCREMENT se reinician y los IDs se reutilizan; sin
  # borrar los ficheros viejos se asignarían a identidades nuevas.
  "admin/caras_procesadas"
  # Cache de clasificación VLM/OpenAI por hash de imagen (identidad derivada).
  "motor/llm_cache"
  # Salidas/derivados de identidad y de evaluación.
  "motor/reagrupar_out"
  "motor/eval/data"
  "motor/cosas_en_la_cara"
  "motor/laterales_test"
  # Uploads de registro de personas (enrolamiento).
  "admin/files/videos_registro"
  "admin/files/videos_registro_videos"
  "admin/files/videos_registro_videos_partidos"
  "admin/files/videos_registro_posiciones"
  "admin/files/videos_registro_pruebas"
  "admin/files/videos_registro_resultados"
  # Estado runtime de identidad que antes SOBREVIVÍA al reset (lección 2026-09-28):
  # logs del pipeline, backups de face_enc_v2 (identidad antigua), estado de deriva
  # del calibrador y la bandeja de revisión de cuerpos. Se conservan solo models/ y
  # venv/.
  "motor/logs"
  "motor/backups"
  "motor/revision_cuerpos"
  "motor/calibrador/deriva"
  # Cola de marcadores del detector (markers .mp4.txt/.avi.txt, contadores
  # .intentos, logs procesar_*.txt y archiva_*). Borrarla entera garantiza que el
  # pipeline no arrastre historial de intentos ni parezca retomar vídeos previos.
  "aux"
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

# PIDs de ffmpeg cuyo cwd es el proyecto (los lanzadores usan rutas RELATIVAS
# `motor/videos/...`, así que pgrep -f no los vería). Evita matar ffmpeg ajenos.
pids_ffmpeg_proyecto() {
  local pid cwd
  for pid in $(pgrep -x ffmpeg 2>/dev/null || true); do
    cwd=$(readlink "/proc/${pid}/cwd" 2>/dev/null || true)
    case "${cwd}" in
      "${PROYECTO}"|"${PROYECTO}"/*) printf '%s\n' "${pid}" ;;
    esac
  done
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
  pids="$pids $(pids_ffmpeg_proyecto)"
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
                   pgrep -f -- "${PROYECTO}/motor"
                   pids_ffmpeg_proyecto; } 2>/dev/null \
                 | grep -vE "^(${no_tocar_regex})$" | wc -l ) || restantes=0
    (( restantes == 0 )) && break
    sleep 1; i=$((i+1))
  done
  log "  procesos RF restantes tras matar: ${restantes}"
}

# Verificación visible: lista servicios parados y procesos RF vivos (excluye la
# sesión SSH actual). Devuelve 0 si no queda ninguno.
vivos_rf() {
  local no_tocar_regex pat
  no_tocar_regex=$(printf '%s\n' "$(_arbol_no_tocar)" | tr ' ' '\n' | sed '/^$/d' | paste -sd'|' -)
  { for pat in "${PATRONES_KILL[@]}"; do pgrep -f -- "$pat"; done
    pgrep -f -- "${PROYECTO}/motor"
    pids_ffmpeg_proyecto; } 2>/dev/null | grep -vE "^(${no_tocar_regex})$" | sort -u
}

verificar_parada() {
  local titulo="$1" svc vivos
  log "${titulo}"
  for svc in "${SERVICIOS[@]}"; do
    printf '[reset]   %-20s %s\n' "${svc}" "$(systemctl is-active "${svc}" 2>/dev/null || true)"
  done
  vivos="$(vivos_rf)"
  if [[ -n "${vivos}" ]]; then
    log "  ATENCIÓN: procesos RF aún vivos:"
    for p in ${vivos}; do printf '[reset]   PID %s: %s\n' "${p}" "$(tr '\0' ' ' < "/proc/${p}/cmdline" 2>/dev/null)"; done
    return 1
  fi
  log "  0 procesos RF vivos. Parada total confirmada."
  return 0
}

# Guarda anti-trampa (2026-09-29): el reset vacía la galería (face_enc_v2) y las
# tablas. Si RF_AUTOENROLL_NEW queda inactivo, ningún verdict puede ser un
# `match` confirmado y el clasificador no crearía NUNCA identidades: el panel de
# Visitantes quedaría vacío para siempre. Se asegura el flag activo en `.env`
# ANTES de rearrancar los servicios (copia de seguridad del `.env` incluida).
asegurar_autoenroll() {
  local envf="${PROYECTO}/.env" actual tmp bak
  if [[ ! -f "${envf}" ]]; then
    log "  AVISO: ${envf} no existe; no se puede asegurar RF_AUTOENROLL_NEW"
    return 0
  fi
  actual="$(grep -E '^RF_AUTOENROLL_NEW=' "${envf}" 2>/dev/null | tail -1 \
            | cut -d= -f2- | tr -d " \t\"'")"
  case "${actual,,}" in
    1|true|yes|on|si|sí) log "  RF_AUTOENROLL_NEW ya activo (=${actual})"; return 0 ;;
  esac
  if [[ ${DRY_RUN} -eq 1 ]]; then
    log "  (dry-run) activaría RF_AUTOENROLL_NEW=1 en ${envf}"
    return 0
  fi
  bak="${envf}.bak-$(date +%Y%m%d%H%M%S)"
  cp -p "${envf}" "${bak}"
  tmp="$(mktemp)"
  if grep -qE '^RF_AUTOENROLL_NEW=' "${envf}"; then
    sed -E 's/^RF_AUTOENROLL_NEW=.*/RF_AUTOENROLL_NEW=1/' "${envf}" > "${tmp}"
  else
    cp "${envf}" "${tmp}"
    printf '\nRF_AUTOENROLL_NEW=1\n' >> "${tmp}"
  fi
  chown --reference="${envf}" "${tmp}" 2>/dev/null || true
  chmod --reference="${envf}" "${tmp}" 2>/dev/null || true
  mv "${tmp}" "${envf}"
  log "  RF_AUTOENROLL_NEW activado (=1); copia previa en ${bak}"
}

# Verificación de que el flag efectivo queda activo tras la guarda (lee el .env
# con el MISMO parser que el motor, vía motor.core.env).
verificar_autoenroll() {
  local val
  val="$(cd "${PROYECTO}" && motor/venv/bin/python -c \
      'from motor.core.env import get_bool; print(1 if get_bool(".", "RF_AUTOENROLL_NEW", False) else 0)' \
      2>/dev/null || true)"
  if [[ "${val}" == "1" ]]; then
    log "  verificación: RF_AUTOENROLL_NEW efectivo = 1 (el clasificador sí enrolará)"
  else
    log "  AVISO: RF_AUTOENROLL_NEW efectivo = '${val:-?}' (revisar ${PROYECTO}/.env)"
  fi
}

# =============================================================================
# FASE A2 — matar TODOS los procesos RF (hijos/huérfanos/ffmpeg que systemd no cubre)
# =============================================================================
log "FASE A2: matando todos los procesos RF del proyecto..."
cmd "Matar procesos RF" matar_procesos

if [[ ${DRY_RUN} -eq 0 ]]; then
  # Evidencia visible de que TODO quedó parado (no solo los servicios systemd).
  if ! verificar_parada "FASE A2b: verificación de parada total"; then
    log "  reintentando matar procesos residuales..."
    cmd "Re-matar procesos RF" matar_procesos
    verificar_parada "FASE A2b: re-verificación de parada total" \
      || die "quedan procesos RF vivos; abortado antes de tocar datos"
  fi

  # --hold N: pausa con re-verificación (prueba de que nada se autola en solitario).
  if (( HOLD > 0 )); then
    log "FASE A2c: --hold ${HOLD}s — se re-verificará que todo sigue caído..."
    while (( HOLD > 0 )); do
      printf '[reset]   esperando... %ss\r' "${HOLD}"
      sleep 1; HOLD=$((HOLD-1))
    done
    printf '\n'
    verificar_parada "FASE A2c: verificación tras la pausa" \
      || die "algo se levantó durante --hold; abortado antes de tocar datos"
  fi
fi

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
# Fotos publicadas del panel: el clasificador la autocrea, pero la dejamos lista
# para que Apache sirva el directorio aunque aún no haya capturas.
cmd "Recrear ${PROYECTO}/admin/caras_procesadas" mkdir -p "${PROYECTO}/admin/caras_procesadas"
# Cola de marcadores del detector: vacía y con permisos de escritura (php-fpm).
cmd "Recrear ${PROYECTO}/aux" mkdir -p "${PROYECTO}/aux"
cmd "Permisos ${PROYECTO}/aux" chmod 777 "${PROYECTO}/aux"
# Logs del pipeline: directorio limpio (lo usan ffmpeg/procesa_video para >>).
cmd "Recrear ${PROYECTO}/motor/logs" mkdir -p "${PROYECTO}/motor/logs"

# aux/ ya se ha borrado entero en FASE C (markers, contadores .intentos y logs
# procesar_*.txt), así que no quedan slot-markers huérfanos que saturarían
# CONFIG_LIMITE_VIDEOS/CONFIG_LIMITE_ARCHIVA. La recreamos vacía arriba.

# =============================================================================
# FASE D — rearrancar servicios y timers (encendido total desde cero)
# =============================================================================
log "FASE D: asegurando RF_AUTOENROLL_NEW (guarda anti-trampa)..."
asegurar_autoenroll
verificar_autoenroll

log "FASE D: rearrancando servicios y timers..."
for svc in "${SERVICIOS[@]}"; do
  cmd "Arrancar ${svc}" systemctl restart "${svc}" 2>/dev/null || true
done
# Rearmar los timers de one-shots (rf-calibra, rf-vigilar-deriva, rf-reprocesa):
# se lanzan en su horario; restart del timer lo fuerza a reprogramarse tras el
# reset limpio. rf-reprocesa también: antes quedaba inactive/dead tras un reset.
for t in rf-calibra.timer rf-vigilar-deriva.timer rf-reprocesa.timer; do
  if systemctl list-unit-files "${t}" >/dev/null 2>&1; then
    cmd "Rearmar ${t}" systemctl enable --now "${t}" 2>/dev/null || true
  fi
done

# Evidencia del arranque limpio: PID y hora de arranque de cada servicio.
if [[ ${DRY_RUN} -eq 0 ]]; then
  log "FASE D2: estado de los servicios rearrancados:"
  for svc in "${SERVICIOS[@]}"; do
    printf '[reset]   %-20s %-8s pid=%-8s since=%s\n' "${svc}" \
      "$(systemctl is-active "${svc}" 2>/dev/null || true)" \
      "$(systemctl show "${svc}" -p MainPID --value 2>/dev/null || true)" \
      "$(systemctl show "${svc}" -p ActiveEnterTimestamp --value 2>/dev/null || true)"
  done
fi

log "Reset completado. Verificar con: systemctl status rf-* y el panel web."
[[ ${DRY_RUN} -eq 1 ]] && log "DRY-RUN: nada se ha modificado."
