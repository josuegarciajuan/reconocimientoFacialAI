#!/usr/bin/env bash
# Reap procesos del motor rf que quedan en estado D (uninterruptible sleep)
# durante más de 1 hora. Un proceso en D >1h suele estar atascado por thrash de
# swap o por throttling del cgroup (memory.high); matarlo libera su RAM y el
# orquestador (detector.php) relanza el clasificador o reintenta el vídeo
# (los procesa_video.py son one-shot y se reintentan vía markers en aux/).
#
# Se ejecuta desde rf-reap.timer (systemd) cada 10 min.
set -u

LOG="/var/log/rf-reap.log"
THRESHOLD_SEC=3600

pids=$(ps -eo pid,stat,etimes,args \
    | grep -E "[c]lasificador\.py|[p]rocesa_video\.py" \
    | awk -v t="$THRESHOLD_SEC" '$2 ~ /^D/ && $3 > t {print $1}')

if [ -z "$pids" ]; then
    exit 0
fi

for pid in $pids; do
    # doble verificación justo antes de matar: no matar si acaba de salir de D
    if ps -o stat= -p "$pid" 2>/dev/null | grep -q '^D'; then
        echo "$(date -Is) reap rf worker pid=$pid" >> "$LOG"
        kill -9 "$pid" 2>/dev/null
    fi
done
