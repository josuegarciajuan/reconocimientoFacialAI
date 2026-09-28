#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A/B de DETECCIÓN de caras — motor/scripts/eval_deteccion.py

`motor/eval/eval.py` mide el embedding (caras ya recortadas); esto mide lo otro:
la RECALL de detección sobre frames reales de cámara y la velocidad, comparando
detectores (RetinaFace det_10g vs SCRFD det_500m) y `det_size`.

Empareja cada detección con la del baseline (det_10g @ baseline_size) por IoU
para estimar recall. SOLO LECTURA: copia el vídeo a /tmp y no toca datos ni
servicios.

Uso:
    motor/venv/bin/python motor/scripts/eval_deteccion.py <video.mp4> \
        --frames 15 --step 8 \
        --configs "det_10g:1280,det_500m:1280,det_10g:960,det_500m:960,det_500m:640"
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time

import cv2

PROYECTO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROYECTO)

from motor.core.config import Config                    # noqa: E402
from motor.core.model import _patch_ort_sessions, ort_providers  # noqa: E402


def _iou(a, b) -> float:
    x1, y1, x2, y2 = a
    X1, Y1, X2, Y2 = b
    ix1, iy1, ix2, iy2 = max(x1, X1), max(y1, Y1), min(x2, X2), min(y2, Y2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    u = (x2 - x1) * (y2 - y1) + (X2 - X1) * (Y2 - Y1) - inter
    return inter / u if u > 0 else 0.0


def _build(detector: str, det_size: int, det_model_path: str | None):
    from insightface.app import FaceAnalysis
    from insightface.model_zoo import get_model

    _patch_ort_sessions()
    providers = ort_providers()
    app = FaceAnalysis(name="buffalo_l", providers=providers)   # rec/landmark
    app.prepare(ctx_id=0, det_size=(det_size, det_size))
    if detector != "det_10g" and det_model_path:
        det = get_model(det_model_path, providers=providers)
        det.prepare(ctx_id=0, input_size=(det_size, det_size), det_thresh=0.5)
        app.det_model = det
        app.models["detection"] = det
    return app


def _detect(app, frame):
    faces = app.get(frame)
    return [(tuple(int(v) for v in f.bbox), float(f.det_score)) for f in faces]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--frames", type=int, default=15)
    ap.add_argument("--step", type=int, default=8, help="muestrear 1 de cada N frames")
    ap.add_argument("--configs", default="det_10g:1280,det_500m:1280,det_10g:960,det_500m:960,det_500m:640")
    ap.add_argument("--baseline", default="det_10g:1280")
    ap.add_argument("--ruta", default=PROYECTO)
    ap.add_argument("--det-model", default=os.path.expanduser(
        "~/.insightface/models/buffalo_s/det_500m.onnx"))
    args = ap.parse_args()

    if not os.path.isfile(args.video):
        print(f"ERROR: no existe {args.video}")
        return 1
    if not os.path.isfile(args.det_model):
        print(f"ERROR: falta el detector alternativo {args.det_model}")
        return 1

    tmp = os.path.join("/tmp", "evaldet_" + os.path.basename(args.video))
    shutil.copy2(args.video, tmp)
    cap = cv2.VideoCapture(tmp)
    frames = []
    i = 0
    while len(frames) < args.frames:
        ret, fr = cap.read()
        if not ret:
            break
        if i % args.step == 0:
            frames.append(fr)
        i += 1
    cap.release()
    os.remove(tmp)
    if not frames:
        print("ERROR: no se pudieron extraer frames")
        return 1
    print(f"frames muestreados: {len(frames)}  (de {os.path.basename(args.video)})")

    results = {}
    for cfg in [c.strip() for c in args.configs.split(",") if c.strip()]:
        det, size = cfg.split(":")
        size = int(size)
        t0 = time.perf_counter()
        app = _build(det, size, args.det_model if det == "det_500m" else None)
        t_load = time.perf_counter() - t0
        res = []
        t0 = time.perf_counter()
        for fr in frames:
            res.append(_detect(app, fr))
        dt = (time.perf_counter() - t0) / len(frames) * 1000
        results[cfg] = {"res": res, "ms": dt, "load": t_load}
        print(f"  [{cfg}] cargado en {t_load:.1f}s, {dt:.0f} ms/frame")

    base = results.get(args.baseline)
    if base is None:
        print(f"ERROR: baseline {args.baseline} no está en configs")
        return 1

    print("=" * 78)
    print(f"{'config':<18}{'detecciones':>12}{'recall vs base':>16}{'ms/frame':>12}")
    print("-" * 78)
    base_total = sum(len(r) for r in base["res"])
    for cfg, r in results.items():
        total = sum(len(x) for x in r["res"])
        matched = 0
        for bf, cf in zip(base["res"], r["res"]):
            for bb, _ in bf:
                if any(_iou(bb, cb) >= 0.5 for cb, _ in cf):
                    matched += 1
        recall = (matched / base_total * 100) if base_total else 0.0
        print(f"{cfg:<18}{total:>12}{recall:>15.1f}%{r['ms']:>11.0f}")
    print("=" * 78)
    print(f"baseline={args.baseline}  detecciones_base={base_total}")
    print("recall = caras del baseline encontradas por la config (IoU>=0.5)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
