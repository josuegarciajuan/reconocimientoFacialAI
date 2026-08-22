#!/usr/bin/env bash
#
# Control de encendido/apagado del motor de reconocimiento facial.
# Uso: sudo deploy/rf_power.sh [off|on|status]
#
#   off    -> detiene timers + servicios (captura, detector, clasificador, live,
#             panel-control, conciliador, vinculador, alarmador) y libera la RAM
#             de los hijos Python/Node del motor. El panel web (Apache + php-fpm)
#             NO se toca, así el operador puede volver a encender.
#   on     -> rearranca servicios + timers (funcionamiento normal).
#   status -> imprime "on" si rf-capturador está activo, si no "off".
#
# Los servicios son Type=simple con KillMode=control-group (default), por lo que
# `systemctl stop` mata también a los hijos lanzados con `&` desde el orquestador
# PHP. La red de seguridad con pkill cubre hijos que hayan escapado del cgroup
# (p.ej. procesos en estado D o lanzados con setsid), igual que hace rf-reap.
#
# El estado NO persiste entre reinicios: tras un reboot, los servicios `enabled`
# vuelven a arrancar (comportamiento deseado: un reinicio = funcionamiento normal).

set -u

SERVICES=(rf-capturador rf-detector rf-clasificador rf-live rf-panel-control rf-conciliador rf-vinculador rf-alarmador)
TIMERS=(rf-calibra.timer rf-reap.timer rf-vigilar-deriva.timer)

# Procesos hijos del motor (visión/streaming) a purgar para liberar RAM residual.
VISION_PATTERNS=(
  "guarda_movimientosV3.py"
  "procesa_video.py"
  "archiva_video.py"
  "clasificador.py"
  "pose.py"
  "mjpeg-stream.js"
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
  for s in "${SERVICES[@]}"; do
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
  for s in "${SERVICES[@]}"; do
    systemctl start "$s" 2>/dev/null || true
  done
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
