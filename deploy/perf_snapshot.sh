#!/usr/bin/env bash
# =============================================================================
# perf_snapshot.sh — Foto de rendimiento del motor de reconocimiento facial.
#
# SOLO LECTURA: no arranca, para ni modifica ningún servicio/proceso. Sirve para
# medir el antes/después de cada fase de optimización (ver docs/specs/16).
#
# Uso:
#   bash deploy/perf_snapshot.sh                 # imprime la foto por stdout
#   bash deploy/perf_snapshot.sh --out fichero   # además la guarda en fichero
#   bash deploy/perf_snapshot.sh --quick         # sin vmstat (1 s)
#
# En producción:
#   ssh <prod> 'bash /root/reconocimientoFacial/deploy/perf_snapshot.sh'
# =============================================================================
set -uo pipefail

OUT=""
QUICK=0
while [ $# -gt 0 ]; do
    case "$1" in
        --out) OUT="${2:-}"; shift ;;
        --quick) QUICK=1 ;;
        -h|--help) sed -n '2,20p' "$0"; exit 0 ;;
        *) echo "Flag desconocida: $1" >&2; exit 2 ;;
    esac
    shift
done

SNAP() {
    local T
    T=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    echo "==================================================================="
    echo "RF perf_snapshot  $T  host=$(hostname)"
    echo "==================================================================="

    echo "### HARDWARE"
    echo "cores=$(nproc)  mem_total=$(awk '/MemTotal/{printf "%.1f GB", $2/1024/1024}' /proc/meminfo 2>/dev/null)"
    awk '/MemAvailable/{printf "mem_available=%.1f GB\n", $2/1024/1024}' /proc/meminfo 2>/dev/null
    echo "uptime: $(uptime 2>/dev/null)"
    echo

    echo "### CARGA / CPU"
    echo "loadavg: $(cat /proc/loadavg 2>/dev/null)"
    free -h 2>/dev/null
    if [ "$QUICK" = 0 ] && command -v vmstat >/dev/null 2>&1; then
        # r = runqueue, cs = cambios de contexto/s, us/sy/id = reparto de CPU
        echo "-- vmstat 1 3 (r=runqueue, cs=ctx-switch/s, us/sy/id) --"
        vmstat 1 3 2>/dev/null
    fi
    echo

    echo "### TOP CPU (procesos)"
    ps -eo pid,ppid,pcpu,pmem,nlwp,rss,etime,comm,args --sort=-pcpu 2>/dev/null | head -20
    echo

    echo "### HILOS POR PROCESO DEL MOTOR"
    for p in $(pgrep -f 'motor/(clasificador|procesa_video|guarda_movimientosV3|photo_worker|pose)\.py' 2>/dev/null); do
        local th cpu cmd
        th=$(awk '/Threads/{print $2}' "/proc/$p/status" 2>/dev/null)
        cpu=$(ps -o pcpu= -p "$p" 2>/dev/null | tr -d ' ')
        cmd=$(tr '\0' ' ' <"/proc/$p/cmdline" 2>/dev/null | cut -c1-100)
        printf 'pid=%-8s threads=%-4s cpu=%-6s %s\n' "$p" "${th:-?}" "${cpu:-?}" "$cmd"
    done
    echo "total_hilos_sistema=$(ps -eLf 2>/dev/null | wc -l)  procesos=$(ps -e --no-headers 2>/dev/null | wc -l)"
    echo

    echo "### PROCESOS POR TIPO"
    cnt() { local n; n=$(pgrep -c -f "$1" 2>/dev/null); echo "${n:-0}"; }
    echo "guarda_movimientos=$(cnt 'guarda_movimientosV3')"
    echo "clasificador=$(cnt 'motor/clasificador.py')"
    echo "procesa_video=$(cnt 'motor/procesa_video.py')"
    echo "archiva_video=$(cnt 'motor/archiva_video.py')"
    n=$(pgrep -c -x ffmpeg 2>/dev/null); echo "ffmpeg=${n:-0}"
    echo

    echo "### CGROUPS SERVICIOS RF"
    for u in rf-capturador rf-detector rf-photo rf-clasificador rf-live; do
        if systemctl list-unit-files "${u}.service" >/dev/null 2>&1; then
            printf '%-18s ' "$u"
            systemctl show "$u" -p MemoryCurrent -p MemoryMax -p Nice 2>/dev/null | tr '\n' ' '
            echo
        fi
    done
    echo

    echo "### BACKLOG DE VÍDEOS (pendientes de procesar)"
    if [ -d /root/reconocimientoFacial/motor/videos ]; then
        local total=0
        while IFS= read -r d; do
            local n
            n=$(find "$d" -maxdepth 1 -type f \( -name '*.mp4' -o -name '*.avi' \) 2>/dev/null | wc -l)
            if [ "$n" -gt 0 ]; then
                echo "  ${d}: ${n}"
                total=$((total + n))
            fi
        done < <(find /root/reconocimientoFacial/motor/videos -mindepth 2 -maxdepth 2 -type d 2>/dev/null)
        echo "  TOTAL=$total"
    fi
    echo

    echo "### BARRA FIN"
    echo "==================================================================="
}

if [ -n "$OUT" ]; then
    SNAP | tee "$OUT"
    echo "[perf_snapshot] guardado en: $OUT"
else
    SNAP
fi
