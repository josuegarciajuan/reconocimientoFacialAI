#!/usr/bin/env bash
# Instala los servicios systemd del motor de reconocimiento facial.
# Uso: sudo bash deploy/install_services.sh [start]
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICES=(rf-capturador rf-detector rf-clasificador rf-panel-control rf-live rf-conciliador rf-vinculador rf-alarmador)

echo "==> Copiando unidades systemd desde $DIR/deploy/systemd"
for s in "${SERVICES[@]}"; do
    if [ ! -f "$DIR/deploy/systemd/$s.service" ]; then
        echo "ERROR: falta $s.service"; exit 1
    fi
    sed "s|/root/reconocimientoFacial|$DIR|g" "$DIR/deploy/systemd/$s.service" > "/etc/systemd/system/$s.service"
done

systemctl daemon-reload

if [ "${1:-}" = "start" ]; then
    for s in "${SERVICES[@]}"; do
        systemctl enable --now "$s.service"
        echo "==> $s activado"
    done
    systemctl status rf-detector --no-pager -l | head -8
fi

echo "==> Listo. Comandos útiles:"
echo "    systemctl status rf-{capturador,detector,clasificador,panel-control,live,conciliador,vinculador,alarmador}"
echo "    journalctl -u rf-live -f"
echo "    journalctl -u rf-conciliador -f"
echo "    journalctl -u rf-vinculador -f"
echo "    journalctl -u rf-alarmador -f"
