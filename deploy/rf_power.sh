#!/usr/bin/env bash
#
# Control de encendido/apagado del motor de reconocimiento facial.
# Uso: sudo deploy/rf_power.sh [off|on|status]
#
#   off    -> detiene timers + servicios del motor (captura, detector, clasificador,
#             clasificador-serve, panel-control, conciliador, vinculador,
#             alarmador, photo) y el servicio auxiliar Ollama (modelos VLM en RAM).
#             Después libera la RAM de los hijos Python/Node que hayan escapado del
#             cgroup. El panel web (Apache + php-fpm) NO se toca, así el operador
#             puede volver a encender.
#             NO se detiene rf-live: el "En Directo" del panel debe seguir siendo
#             visible con el motor apagado (solo consume al haber espectadores).
#   on     -> rearranca servicios + timers (funcionamiento normal) y asegura rf-live.
#   status -> imprime "on" si rf-capturador está activo, si no "off".
#
# Los servicios son Type=simple con KillMode=control-group (default), por lo que
# `systemctl stop` mata también a los hijos lanzados con `&` desde el orquestador
# PHP. La red de seguridad con pkill cubre hijos que hayan escapado del cgroup
# (p.ej. procesos en estado D o lanzados con setsid, o el runner de Ollama).
#
# El estado NO persiste entre reinicios: tras un reboot, los servicios `enabled`
# vuelven a arrancar (comportamiento deseado: un reinicio = funcionamiento normal).

set -u

# Daemons del motor (deben cubrir TODO lo que consume CPU/RAM de visión).
# rf-live NO está aquí: es el "En Directo" y debe seguir activo con el motor apagado.
SERVICES=(rf-capturador rf-detector rf-clasificador rf-clasificador-serve rf-panel-control rf-conciliador rf-vinculador rf-alarmador rf-photo)
# Servicio de streaming en directo: se mantiene SIEMPRE activo (independiente del
# apagado del motor). Se arranca en ON por robustez, pero OFF no lo detiene.
LIVE_SERVICE=rf-live
# Servicios auxiliares compartidos: Ollama mantiene los modelos VLM cargados en
# RAM. Se para en OFF para liberar memoria y se rearranca en ON.
AUX_SERVICES=(ollama)
# Timers reales de deploy/systemd/. Se detienen para que no disparen en OFF.
TIMERS=(rf-calibra.timer rf-vigilar-deriva.timer rf-reprocesa.timer rf-reten-backups.timer)

# Procesos hijos del motor (visión) a purgar para liberar RAM residual.
# No se incluye mjpeg-stream.js: pertenece a rf-live, que permanece activo.
VISION_PATTERNS=(
  "guarda_movimientosV3.py"
  "procesa_video.py"
  "archiva_video.py"
  "clasificador.py"
  "photo_worker.py"
  "pose.py"
  "ollama_llama_server"
)

free_mb() {
  awk '/MemAvailable/ {printf "%d", $2/1024}' /proc/meminfo
}

cmd_off() {
  local antes despues
  antes=$(free_mb)

  # 1. Detener timers para que no disparen mientras el motor está apagado.
  for t in "${TIMERS[@]}"; do
    systemctl stop "$t" 2>/dev/null || true
  done

  # 2. Detener servicios (el cgroup arrastra a los hijos).
  for s in "${SERVICES[@]}" "${AUX_SERVICES[@]}"; do
    systemctl stop "$s" 2>/dev/null || true
  done

  # 3. Red de seguridad: purgar hijos que hayan escapado del cgroup.
  for p in "${VISION_PATTERNS[@]}"; do
    pkill -9 -f "$p" 2>/dev/null || true
  done

  # Dar un respiro al kernel para que reclame las páginas.
  sleep 1

  despues=$(free_mb)
  echo "OFF ok · RAM libre: ${antes} MB -> ${despues} MB (liberados $((despues - antes)) MB)"
}

cmd_on() {
  # Arrancar primero el auxiliar (Ollama) para que el clasificador lo encuentre listo.
  for s in "${AUX_SERVICES[@]}"; do
    systemctl start "$s" 2>/dev/null || true
  done
  for s in "${SERVICES[@]}"; do
    systemctl start "$s" 2>/dev/null || true
  done
  # El directo debe estar siempre disponible (aunque el motor estuviera apagado).
  systemctl start "$LIVE_SERVICE" 2>/dev/null || true
  for t in "${TIMERS[@]}"; do
    systemctl start "$t" 2>/dev/null || true
  done
  echo "ON ok · motor rearrancado"
}

cmd_status() {
  if [ "$(systemctl is-active rf-capturador 2>/dev/null)" = "active" ]; then
    echo "on"
  else
    echo "off"
  fi
}

case "${1:-}" in
  off)    cmd_off ;;
  on)     cmd_on ;;
  status) cmd_status ;;
  *)      echo "Uso: $0 [off|on|status]" >&2; exit 1 ;;
esac
