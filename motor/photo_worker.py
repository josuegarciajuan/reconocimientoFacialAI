#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Worker único de foto — motor/photo_worker.py

Genera la foto final HQ de las personas (RealESRGAN x4plus + GFPGAN) para el
panel. Es UN solo proceso (daemon `rf-photo.service`) para que los modelos
pesados (GFPGANv1.4 ~348 MB, RealESRGAN_x4plus ~67 MB + runtime torch) vivan
en UNA sola copia en RAM, en vez de duplicarse en cada clasificador de cámara.

Protocolo de cola (disco, contrato con motor/clasificador.py::_queue_hq):
    motor/photo_queue/<local>/<cam>/<foto_id>_f<i>.png  frames fuente (lossless)
    motor/photo_queue/<local>/<cam>/<foto_id>.json      {frames:[{src,bbox}...], out, ts}
Retrocompatible con el formato antiguo de un solo frame ({src, out, bbox, ts}).
El JSON con >=2 frames activa el MF-SR real (photo_busto_fused).

Salida: escribe `<out>.hq` (la foto rápida ya publicada se "autonitida").
clasificadorV2.php ingesta `*.hq` y sobreescribe la foto (generada_hq=1),
exactamente igual que antes de este refactor.

RAM/CPU-gate: si la memoria disponible baja de cfg.ram_min_free_gb, o la carga
media de 1 min supera cfg.hq_load_max (si >0), el worker duerme (no compite con
autotube). El cgroup del servicio (MemoryMax) limita el pico absoluto. Inferencia
con UN hilo (torch.set_num_threads(1) en motor/core/superres.py +
OMP_NUM_THREADS=1 en el unit). La cola se acota a cfg.hq_max_queue jobs en disco.

Uso (daemon):
    motor/venv/bin/python motor/photo_worker.py --ruta /root/reconocimientoFacial
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config            # noqa: E402
from motor.core.superres import photo_busto, photo_busto_fused  # noqa: E402

JOB_EXTS = (".json",)
# TTL de la cola: si el worker estuvo apagado mucho tiempo (p.ej. motor OFF),
# al volver NO procesa jobs obsoletos (fotos viejas que el panel ya mostró
# como "rápidas"): los descarta y libera disco.
JOB_TTL_S = 24 * 3600


def _discard_job(job_path: str) -> None:
    """Elimina un job (y TODAS sus fuentes PNG) sin procesarlo."""
    try:
        with open(job_path, encoding="utf-8") as fh:
            job = json.load(fh)
        srcs = set()
        for fr in (job.get("frames") or []):
            if isinstance(fr, dict) and fr.get("src"):
                srcs.add(fr["src"])
        if job.get("src"):                     # retrocompat: job de 1 frame
            srcs.add(job["src"])
        for src in srcs:
            if src and os.path.exists(src):
                os.remove(src)
    except Exception:  # noqa: BLE001
        pass
    try:
        os.remove(job_path)
    except OSError:
        pass


def _ram_available_gb() -> float:
    """GB disponibles (MemAvailable de /proc/meminfo); 99.0 si no se puede leer."""
    try:
        with open("/proc/meminfo", encoding="ascii") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) / 1024 / 1024
    except Exception:  # noqa: BLE001
        pass
    return 99.0


def _loadavg() -> float:
    """Carga media de 1 min (/proc/loadavg); 99.0 si no se puede leer."""
    try:
        with open("/proc/loadavg", encoding="ascii") as fh:
            return float(fh.read().split()[0])
    except Exception:  # noqa: BLE001
        return 99.0


def _process_job(job_path: str, cfg: Config) -> None:
    """Ejecuta un trabajo HQ: genera `<out>.hq` y limpia el job + todas las fuentes.

    Formato de job (clasificador.py::_queue_hq): `{"frames": [{"src", "bbox"}...],
    "out", "ts"}`. Retrocompatible con el formato antiguo `{src, out, bbox}`.
    Si hay >=2 frames y `sr_mf_enabled`, usa el MF-SR real (`photo_busto_fused`);
    si no, o si la fusión no da material, cae a `photo_busto` con el frame 0.
    """
    # descartar jobs obsoletos (cola vieja de un motor apagado mucho tiempo)
    try:
        if time.time() - os.path.getmtime(job_path) > JOB_TTL_S:
            _discard_job(job_path)
            return
    except OSError:
        os.remove(job_path)
        return
    with open(job_path, encoding="utf-8") as fh:
        job = json.load(fh)
    out = job.get("out")
    raw_frames = job.get("frames")
    if not raw_frames:
        # retrocompat: job antiguo de un solo frame
        raw_frames = [{"src": job.get("src"), "bbox": job.get("bbox")}]
    pairs = []
    srcs = []
    for fr in raw_frames:
        if not isinstance(fr, dict):
            continue
        src = fr.get("src")
        bbox = fr.get("bbox")
        if not src or not bbox or len(bbox) != 4:
            continue
        srcs.append(src)
        if not os.path.exists(src):
            continue
        img = cv2.imread(src)
        if img is None:
            continue
        pairs.append((img, tuple(int(v) for v in bbox)))
    if not out or not pairs:
        _discard_job(job_path)
        return
    t0 = time.time()
    img_hq = None
    if len(pairs) >= 2 and cfg.sr_mf_enabled:
        img_hq = photo_busto_fused(pairs, cfg, model=cfg.sr_model_photo)
        if img_hq is None:
            print(f"[photo-worker] MF-SR sin material ({os.path.basename(out)}), "
                  f"un solo frame", flush=True)
    if img_hq is None:
        img_hq = photo_busto(pairs[0][0], pairs[0][1], cfg, model=cfg.sr_model_photo)
    hq_path = out + ".hq"
    # cv2.imwrite NO conoce la extensión ".hq" (error histórico del hilo HQ
    # anterior: cargaba x4plus y fallaba en silencio -> generada_hq siempre 0).
    # Se escribe a un .jpg temporal y se renombra de forma atómica: el contrato
    # con clasificadorV2.php es solo el NOMBRE del fichero (*.jpg.hq).
    tmp_jpg = out + ".hq.tmp.jpg"
    if not cv2.imwrite(tmp_jpg, img_hq, [cv2.IMWRITE_JPEG_QUALITY, 95]):
        raise RuntimeError(f"no se pudo escribir el temporal HQ: {tmp_jpg}")
    os.replace(tmp_jpg, hq_path)
    print(f"[photo-worker] {os.path.basename(out)}.hq generado "
          f"({img_hq.shape[1]}x{img_hq.shape[0]}) en {time.time() - t0:.1f}s "
          f"[{len(pairs)} frame(s)]", flush=True)
    # limpiar el trabajo consumido (JSON + TODAS las fuentes PNG)
    os.remove(job_path)
    for src in set(srcs):
        try:
            os.remove(src)
        except OSError:
            pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    args = ap.parse_args()

    # F1: topes de hilos (OpenCV 1; torch queda en RF_TORCH_THREADS, default 1,
    # que el unit rf-photo sube). No cambia la salida de SR/GFPGAN.
    from motor.core.threads import limit_threads
    limit_threads()

    cfg = Config.from_env(args.ruta)
    queue_root = os.path.join(args.ruta, "motor/photo_queue")
    print(f"[photo-worker] cola: {queue_root} | modelo HQ: {cfg.sr_model_photo} | "
          f"GFPGAN: {cfg.sr_face_enabled}", flush=True)

    while True:
        try:
            # RAM-gate: con la memoria disponible escasa (p.ej. autotube
            # renderizando) se duerme en vez de cargar GFPGAN/x4plus.
            if _ram_available_gb() < cfg.ram_min_free_gb:
                time.sleep(5)
                continue
            # CPU-gate (C): con la carga media por encima de hq_load_max el
            # worker duerme; la foto HQ es diferible y no debe ahogar a autotube.
            if cfg.hq_load_max > 0 and _loadavg() > cfg.hq_load_max:
                time.sleep(5)
                continue
            # recoger el trabajo más antiguo (los primeros encolados primero)
            jobs: list[str] = []
            for root, _dirs, files in os.walk(queue_root):
                for f in files:
                    if f.endswith(JOB_EXTS):
                        jobs.append(os.path.join(root, f))
            if not jobs:
                time.sleep(1)
                continue
            jobs.sort(key=lambda p: os.path.getmtime(p))
            # Tope de cola (C): si se supera, descarta los MÁS ANTIGUOS (fotos
            # que el panel ya mostró en versión rápida) para no acumular trabajo
            # obsoleto y liberar disco.
            if cfg.hq_max_queue > 0 and len(jobs) > cfg.hq_max_queue:
                n_drop = len(jobs) - cfg.hq_max_queue
                for old in jobs[:n_drop]:
                    _discard_job(old)
                print(f"[photo-worker] cola supera {cfg.hq_max_queue}: "
                      f"descartados {n_drop} job(s) antiguo(s)", flush=True)
                jobs = jobs[n_drop:]
                if not jobs:
                    time.sleep(1)
                    continue
            _process_job(jobs[0], cfg)
            time.sleep(0.2)  # pequeño respiro entre trabajos (CPU compartida)
        except KeyboardInterrupt:
            return 0
        except Exception as e:  # noqa: BLE001 — un job corrupto no tumba el daemon
            print(f"[photo-worker] error: {e}", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
