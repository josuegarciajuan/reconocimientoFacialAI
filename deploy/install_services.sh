#!/usr/bin/env bash
# Instala los servicios systemd del motor de reconocimiento facial.
# Uso: sudo bash deploy/install_services.sh [start]
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICES=(rf-capturador rf-detector rf-clasificador rf-panel-control rf-live rf-conciliador rf-vinculador rf-alarmador rf-vigilar-deriva rf-calibra rf-photo)
TIMERS=(rf-calibra rf-vigilar-deriva)

echo "==> Copiando unidades systemd desde $DIR/deploy/systemd"
for s in "${SERVICES[@]}"; do
    if [ ! -f "$DIR/deploy/systemd/$s.service" ]; then
        echo "ERROR: falta $s.service"; exit 1
    fi
    sed "s|/root/reconocimientoFacial|$DIR|g" "$DIR/deploy/systemd/$s.service" > "/etc/systemd/system/$s.service"
done
for t in "${TIMERS[@]}"; do
    if [ ! -f "$DIR/deploy/systemd/$t.timer" ]; then
        echo "ERROR: falta $t.timer"; exit 1
    fi
    sed "s|/root/reconocimientoFacial|$DIR|g" "$DIR/deploy/systemd/$t.timer" > "/etc/systemd/system/$t.timer"
done

systemctl daemon-reload

# Prerrequisitos de runtime (no versionados): el orquestador PHP escribe ahí
# (markers aux/, tracking de hilos) y el panel (php-fpm/www-data) necesita leer
# .env para conectar a la BD.
mkdir -p "$DIR/aux" "$DIR/motor/logs" "$DIR/libs/threads_files_aux" "$DIR/admin/caras_procesadas"
chmod 777 "$DIR/libs/threads_files_aux"
if [ -f "$DIR/.env" ]; then
    chown root:www-data "$DIR/.env" 2>/dev/null || true
    chmod 640 "$DIR/.env" 2>/dev/null || true
fi

# --- Límites de memoria por servicio (drop-ins) ---
# El motor es el dueño de la máquina de producción: se le asigna el 88% de la
# RAM total (dejando ~12% para SO/Apache/MySQL/Ollama/UI) repartido 55/30/15
# entre detector, capturador y foto HQ. El cálculo parte de MemTotal, así que
# un server con más RAM sube los topes automáticamente (portable dev/prod).
MEM_TOTAL_MB="$(awk '/MemTotal/ {printf "%d", ($2/1024)}' /proc/meminfo)"
BUDGET_MB=$(( MEM_TOTAL_MB * 88 / 100 ))
DET_MB=$(( BUDGET_MB * 55 / 100 ))
CAP_MB=$(( BUDGET_MB * 30 / 100 ))
PHO_MB=$(( BUDGET_MB * 15 / 100 ))
set_mem() { # set_mem <servicio> <MB>
    local svc="$1" mb="$2"
    mkdir -p "/etc/systemd/system/${svc}.service.d"
    cat > "/etc/systemd/system/${svc}.service.d/memory.conf" <<EOF
[Service]
# Generado por deploy/install_services.sh a partir de ${MEM_TOTAL_MB} MB de RAM.
# MemoryMax del cgroup: evita el OOM del motor sin ahogar al resto de la máquina.
MemoryMax=${mb}M
EOF
    echo "==> $svc: MemoryMax=${mb}M"
}
set_mem rf-detector "$DET_MB"
set_mem rf-capturador "$CAP_MB"
set_mem rf-photo "$PHO_MB"
systemctl daemon-reload

if [ "${1:-}" = "start" ]; then
    for s in "${SERVICES[@]}"; do
        systemctl enable --now "$s.service"
        echo "==> $s activado"
    done
    for t in "${TIMERS[@]}"; do
        systemctl enable --now "$t.timer"
        echo "==> $t (timer) activado"
    done
    systemctl status rf-detector --no-pager -l | head -8
fi

echo "==> Listo. Comandos útiles:"
echo "    systemctl status rf-{capturador,detector,clasificador,panel-control,live,conciliador,vinculador,alarmador,vigilar-deriva}"
echo "    systemctl list-timers rf-vigilar-deriva"
echo "    journalctl -u rf-live -f"
echo "    journalctl -u rf-conciliador -f"
echo "    journalctl -u rf-vinculador -f"
echo "    journalctl -u rf-alarmador -f"
echo "    journalctl -u rf-vigilar-deriva -f"
