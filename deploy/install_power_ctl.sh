#!/usr/bin/env bash
# Instala el control de encendido/apagado del motor (rf_power) para el panel web.
# Uso: sudo bash deploy/install_power_ctl.sh
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Haciendo ejecutable $DIR/deploy/rf_power.sh"
chmod 0750 "$DIR/deploy/rf_power.sh"
chown root:root "$DIR/deploy/rf_power.sh"

echo "==> Instalando regla sudoers para www-data"
RULE="/etc/sudoers.d/rf-power"
sed "s|/root/reconocimientoFacial|$DIR|g" "$DIR/deploy/sudoers/rf-power" > "$RULE"
chmod 0440 "$RULE"
chown root:root "$RULE"

echo "==> Validando sudoers"
visudo -c

echo "==> Comprobando acceso de www-data"
if sudo -u www-data sudo -n "$DIR/deploy/rf_power.sh" status >/dev/null 2>&1; then
    echo "==> OK: www-data puede controlar el motor"
else
    echo "==> AVISO: www-data no ha podido ejecutar el control; revisa la regla sudoers" >&2
fi

echo "==> Listo. Probar manualmente:"
echo "    sudo -u www-data sudo -n $DIR/deploy/rf_power.sh status"
echo "    sudo -u www-data sudo -n $DIR/deploy/rf_power.sh off"
echo "    sudo -u www-data sudo -n $DIR/deploy/rf_power.sh on"
