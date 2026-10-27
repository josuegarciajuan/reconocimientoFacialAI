#!/usr/bin/env bash
#
# Control de encendido/apagado del motor de reconocimiento facial.
# Uso: sudo deploy/rf_power.sh [off|on|status]
#
#   off    -> delega en deploy/rf_stop.sh: modo local, parada total de servicios,
#             timers y procesos huérfanos, y cancelación de los jobs de ESTE
#             proyecto en SuperServer. rf-live se mantiene activo.
#   on     -> rehabilita y arranca servicios + timers, restaura el modo anterior
#             (si `off` lo guardó) y asegura rf-live.
#   status -> imprime "on" si algún servicio del motor está activo; si no "off".
#
# Importante: `off` NO toca taildeck.service ni la cola de otros proyectos.
# Los servicios se deshabilitan para que un reboot o un deploy no los
# reactiven; `on` vuelve a habilitarlos.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROYECTO="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${PROYECTO}/.env"

# Servicios del motor (todos menos rf-live, que es el "En Directo").
SERVICES=(rf-capturador rf-detector rf-clasificador rf-clasificador-serve rf-panel-control
          rf-conciliador rf-vinculador rf-alarmador rf-photo rf-pipeline)
# rf-reprocesa es un oneshot: se para, pero no se habilita ni arranca directamente.
ONESHOT=(rf-reprocesa)
LIVE_SERVICE=rf-live
AUX_SERVICES=(ollama)
TIMERS=(rf-calibra.timer rf-vigilar-deriva.timer rf-reprocesa.timer rf-reten-backups.timer)

project_id() {
  local p="${RF_SUPERSERVER_PROJECT:-}"
  if [ -z "$p" ] && [ -f "$ENV_FILE" ]; then
    p="$(grep -m1 '^RF_SUPERSERVER_PROJECT=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- | tr -d ' \t"' || true)"
  fi
  printf '%s' "$p"
}

cmd_off() {
  exec bash "${SCRIPT_DIR}/rf_stop.sh"
}

cmd_on() {
  local pid modefile prevfile cur prev
  pid="$(project_id)"
  # Restaurar el modo que había antes del `off`, solo si sigue en `local`.
  if [ -n "$pid" ]; then
    modefile="/var/lib/taildeck/projects/${pid}.mode"
    prevfile="${modefile}.rf-prev"
    if [ -f "$prevfile" ]; then
      cur="$(cat "$modefile" 2>/dev/null | tr -d ' \t\r\n' || true)"
      prev="$(cat "$prevfile" 2>/dev/null | tr -d ' \t\r\n' || true)"
      if [ "$cur" = "local" ] && { [ "$prev" = "superserver" ] || [ "$prev" = "local" ]; }; then
        printf '%s\n' "$prev" > "$modefile"
        echo "modo restaurado: ${prev}"
      fi
      rm -f "$prevfile"
    fi
  fi

  for s in "${AUX_SERVICES[@]}"; do systemctl enable --now "$s" 2>/dev/null || true; done
  for s in "${SERVICES[@]}"; do
    systemctl enable "$s" 2>/dev/null || true
    systemctl start "$s" 2>/dev/null || true
  done
  # rf-reprocesa es oneshot: lo dispara su timer, nunca se arranca a mano.
  for s in "${ONESHOT[@]}"; do systemctl reset-failed "$s" 2>/dev/null || true; done
  systemctl enable --now "$LIVE_SERVICE" 2>/dev/null || true
  for t in "${TIMERS[@]}"; do systemctl enable --now "$t" 2>/dev/null || true; done
  echo "ON ok · motor rearrancado"
}

cmd_status() {
  local s
  for s in rf-capturador rf-detector rf-pipeline rf-clasificador rf-reprocesa; do
    if [ "$(systemctl is-active "$s" 2>/dev/null)" = "active" ]; then
      echo "on"
      return 0
    fi
  done
  echo "off"
}

case "${1:-}" in
  off)    cmd_off ;;
  on)     cmd_on ;;
  status) cmd_status ;;
  *)      echo "Uso: $0 [off|on|status]" >&2; exit 1 ;;
esac
