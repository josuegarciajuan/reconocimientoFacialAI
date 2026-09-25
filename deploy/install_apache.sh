#!/usr/bin/env bash
# Instala el vhost del panel (:8090) detectando el socket php-fpm disponible.
# Uso: sudo bash deploy/install_apache.sh
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEMPLATE="$DIR/deploy/apache/rf-panel.conf"

if [ ! -f "$TEMPLATE" ]; then
    echo "ERROR: falta $TEMPLATE" >&2
    exit 1
fi

# Socket php-fpm más reciente disponible (php8.4 en prod, php8.3 en dev).
SOCK="$(ls -1 /run/php/php*-fpm.sock 2>/dev/null | sort -V | tail -1 || true)"
if [ -z "$SOCK" ]; then
    echo "ERROR: no se encontró ningún socket php-fpm en /run/php" >&2
    exit 1
fi
echo "==> Usando socket php-fpm: $SOCK"

echo "==> Instalando vhost rf-panel (8090)"
sed "s|__PHP_FPM_SOCK__|$SOCK|g" "$TEMPLATE" > /etc/apache2/sites-available/rf-panel.conf

echo "==> Enlazando $DIR en /var/www/html/reconocimientoFacial"
ln -sfn "$DIR" /var/www/html/reconocimientoFacial

echo "==> Habilitando módulos y sitio"
a2enmod proxy proxy_http proxy_fcgi >/dev/null 2>&1 || true
a2ensite rf-panel >/dev/null 2>&1 || true

echo "==> Validando y recargando Apache"
apache2ctl configtest
systemctl reload apache2

echo "==> Listo. Panel: http://<host>:8090/reconocimientoFacial/admin"
