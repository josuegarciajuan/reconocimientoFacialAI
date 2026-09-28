#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Banco de pruebas del pipeline ROI — motor/scripts/eval_roi.py

Compara, sobre frames reales, la detección de caras actual (frame completo) con
el enfoque ROI (recortar la zona de cada persona y detectar dentro) y con ROI +
barrido de respaldo del frame completo a baja resolución (para no depender del
movimiento). Mide RECALL (vs baseline, emparejando por IoU en coordenadas de
frame) y tiempo por frame.

SOLO LECTURA: copia el vídeo a /tmp y no toca datos ni servicios.

Uso:
    motor/venv/bin/python motor/scripts/eval_roi.py <video.mp4> \
        --frames 15 --step 8 --baseline 1280 --roi-size 960 --backup 480
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

from motor.core.config import Config            # noqa: E402
from motor.core.model import analyze             # noqa: E402
from motor.core.threads import limit_threads     # noqa: E402
from motor.cruces import CrossingConfig, PersonDetector  # noqa: E402


def _iou(a, b) -> float:
    ix1, iy1 = max(a[0], b[0]), max(a[1], b[1])
    ix2, iy2 = min(a[2], b[2]), min(a[3], b[3])
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    u = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / u if u > 0 else 0.0


def _dedup(faces, thr: float = 0.5):
    """Fusiona detecciones solapadas quedándose con la de mayor det_score."""
    out = []
    for bbox, score in sorted(faces, key=lambda x: x[1], reverse=True):
        if all(_iou(bbox, b[0]) < thr for b in out):
            out.append((bbox, score))
    return out


def _faces_full(frame, det_size, min_score):
    return [(tuple(int(v) for v in f.bbox), float(f.det_score))
            for f in analyze(frame, det_size=(det_size, det_size), min_score=min_score)]


def _faces_roi(frame, det, det_size, min_score, margin, max_rois=8):
    h, w = frame.shape[:2]
    boxes = det.process(frame)
    # recortes más grandes primero; tope para acotar coste
    boxes = sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)[:max_rois]
    faces = []
    for (x, y, bw, bh) in boxes:
        mx, my = int(margin * bw), int(margin * bh)
        x1, y1 = max(0, x - mx), max(0, y - my)
        x2, y2 = min(w, x + bw + mx), min(h, y + bh + my)
        crop = frame[y1:y2, x1:x2]
        if crop.size == 0:
            continue
        for bbox, score in _faces_full(crop, det_size, min_score):
            faces.append(((bbox[0] + x1, bbox[1] + y1, bbox[2] + x1, bbox[3] + y1), score))
    return _dedup(faces)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--frames", type=int, default=15)
    ap.add_argument("--step", type=int, default=8)
    ap.add_argument("--baseline", type=int, default=1280)
    ap.add_argument("--roi-size", type=int, default=960)
    ap.add_argument("--backup", type=int, default=480)
    ap.add_argument("--margin", type=float, default=0.12)
    ap.add_argument("--ruta", default=PROYECTO)
    args = ap.parse_args()

    if not os.path.isfile(args.video):
        print(f"ERROR: no existe {args.video}")
        return 1
    cfg = Config.from_env(args.ruta)
    limit_threads()

    tmp = os.path.join("/tmp", "evalroi_" + os.path.basename(args.video))
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
        print("ERROR: sin frames")
        return 1

    det = PersonDetector(CrossingConfig())
    ms = cfg.min_det_score

    # Baseline
    t0 = time.perf_counter()
    base = [_faces_full(f, args.baseline, ms) for f in frames]
    t_base = (time.perf_counter() - t0) / len(frames) * 1000

    # ROI
    t0 = time.perf_counter()
    roi = [_faces_roi(f, det, args.roi_size, ms, args.margin) for f in frames]
    t_roi = (time.perf_counter() - t0) / len(frames) * 1000

    # ROI + backup (barrido del frame completo a baja resolución)
    t0 = time.perf_counter()
    roib = []
    for f in frames:
        merged = _faces_roi(f, det, args.roi_size, ms, args.margin)
        merged = _dedup(merged + _faces_full(f, args.backup, ms))
        roib.append(merged)
    t_roib = (time.perf_counter() - t0) / len(frames) * 1000

    def report(nombre, res, tms):
        total = sum(len(r) for r in res)
        base_total = sum(len(r) for r in base)
        matched = sum(1 for bf, cf in zip(base, res) for bb, _ in bf
                      if any(_iou(bb, cb) >= 0.5 for cb, _ in cf))
        recall = matched / base_total * 100 if base_total else 0.0
        extra = sum(1 for bf, cf in zip(base, res) for cb, _ in cf
                    if all(_iou(cb, bb) < 0.5 for bb, _ in bf))
        print(f"{nombre:<22}{total:>7}{recall:>10.1f}%{tms:>10.0f} ms   (+{extra} no en baseline)")

    bt = sum(len(r) for r in base)
    print("=" * 72)
    print(f"{'config':<22}{'caras':>7}{'recall':>11}{'ms/frame':>10}")
    print("-" * 72)
    report("baseline full@1280", base, t_base)
    report(f"ROI @{args.roi_size}", roi, t_roi)
    report(f"ROI+backup@{args.backup}", roib, t_roib)
    print("=" * 72)
    print(f"frames={len(frames)} baseline_caras={bt} margin={args.margin} "
          f"speedup_roi={t_base/t_roi:.1f}x  speedup_roi+backup={t_base/t_roib:.1f}x")
    return 0


if __name__ == "__main__":
    sys.exit(main())
