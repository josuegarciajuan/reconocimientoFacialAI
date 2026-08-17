#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Harness de calibración de cruces de línea — motor/eval_cruces.py

Ejecuta CrossingDetector sobre un vídeo grabado y reporta los cruces detectados
(nº de frame, dirección, instante), para calibrar los umbrales de CrossingConfig.

Uso:
    motor/venv/bin/python motor/eval_cruces.py <video> <x1> <y1> <x2> <y2> [--out-dir .]

Opcionalmente guarda la foto de cada cruce en --out-dir.
"""
from __future__ import annotations

import argparse
import os
import sys

import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.cruces import CrossingConfig, CrossingDetector, Line  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("x1", type=float)
    ap.add_argument("y1", type=float)
    ap.add_argument("x2", type=float)
    ap.add_argument("y2", type=float)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--area-min", type=float, default=800.0)
    ap.add_argument("--min-track-frames", type=int, default=3)
    ap.add_argument("--dedup", type=float, default=3.0)
    args = ap.parse_args()

    line = Line(args.x1, args.y1, args.x2, args.y2, "test")
    cfg = CrossingConfig(area_min=args.area_min, min_track_frames=args.min_track_frames,
                         dedup_seconds=args.dedup)
    det = CrossingDetector(line, cfg)

    cap = cv2.VideoCapture(args.video)
    if not cap.isOpened():
        print(f"ERROR: no se puede abrir {args.video}")
        return 1

    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    frame_idx = 0
    crossings = []
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        ts = frame_idx / fps
        evs = det.process(frame, ts)
        for e in evs:
            crossings.append((frame_idx, e))
            print(f"CRUCE en frame {frame_idx} (t={e.timestamp:.2f}s) direccion={e.direction} "
                  f"en ({e.x:.0f},{e.y:.0f})")
            if args.out_dir:
                os.makedirs(args.out_dir, exist_ok=True)
                cv2.imwrite(os.path.join(args.out_dir, f"cruce_{frame_idx:06d}.jpg"), e.frame)
        frame_idx += 1
    cap.release()

    print(f"\nTotal cruces: {len(crossings)} (frames analizados: {frame_idx})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
