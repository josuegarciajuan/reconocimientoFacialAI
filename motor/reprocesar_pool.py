#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrapper one-shot del re-escaneo de UN vídeo archivado (M3 de SuperServer).

Extrae caras a `cfg.det_size` alto (1280) y guarda los crops en
`<out-dir>/motor/caras/sinclasificar/<local>/<cam>/` (mismo contrato de nombres
que `reprocesar.py --videos`), SIN efectos en la casa: no toca la BD, no escribe
markers y no borra nada. El bridge de la casa mueve los crops y marca el vídeo.

Uso (en el worker):
    python /app/motor/reprocesar_pool.py --src /work/in/<f>.mp4 --out-dir /work/out \
        --local 1 --cam 15 --fichero <f>.mp4 --face-every 2 --out-meta /work/out/reprocesar.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2                                                       # noqa: E402
from motor.core.config import Config                             # noqa: E402
from motor.core.model import analyze                             # noqa: E402
from motor.procesa_video import guardar_cara                     # noqa: E402


def reprocesar(src: str, out_dir: str, local_id: str, camara_id: str, fichero: str,
               cfg: Config, face_every: int) -> int:
    if not os.path.exists(src):
        return 0
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        return 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    frame_idx = 0
    buffer: list = []
    caras = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % face_every == 0:
            faces = analyze(frame, det_size=(cfg.det_size, cfg.det_size),
                            min_score=cfg.min_det_score)
            for f in faces:
                guardar_cara(out_dir, local_id, camara_id, fichero, frame, f,
                             frame_idx / fps, cfg, buffer)
                caras += 1
        frame_idx += 1
    cap.release()
    return caras


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--local", required=True)
    ap.add_argument("--cam", required=True)
    ap.add_argument("--fichero", required=True)
    ap.add_argument("--face-every", type=int, default=None)
    ap.add_argument("--out-meta", required=True)
    args = ap.parse_args()

    cfg = Config.from_env(args.out_dir)
    face_every = args.face_every if args.face_every is not None else cfg.face_every
    caras = reprocesar(args.src, args.out_dir, args.local, args.cam, args.fichero,
                       cfg, face_every)
    meta = {"local": str(args.local), "cam": str(args.cam), "fichero": args.fichero,
            "caras": int(caras)}
    os.makedirs(os.path.dirname(os.path.abspath(args.out_meta)), exist_ok=True)
    with open(args.out_meta, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False)
    print(f"[rescan-pool] {args.cam}/{args.fichero}: {caras} caras", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
