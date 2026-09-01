#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Enrolamiento multi-pose — motor/enrolamiento.py

Sustituye a `procesa_video_registro_1.py` + `procesa_video_registro_2.py` (B5: guardaba el
frame completo y sin resize/mean; B8: NameError). Extrae caras enfocadas del vídeo de
registro, las agrupa por pose y guarda TODAS las poses en face_enc_v2.

Uso:
    motor/venv/bin/python motor/enrolamiento.py <local_id> <video.avi> <cod_interno> \
        [--ruta .] [--frames-step 5] [--max-per-pose 8] [--min-sharpness 80]

Salida: número de encodings guardados (0 si el vídeo no aporta caras útiles).
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import defaultdict

import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config          # noqa: E402
from motor.core.model import analyze          # noqa: E402
from motor.core.quality import face_sharpness, pose_label  # noqa: E402
from motor.core.store import FaceStore        # noqa: E402


def enroll(local_id: str, video_path: str, cod_interno: str, ruta: str,
           cfg: Config, frames_step: int = 5, max_per_pose: int = 8) -> int:
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return 0

    buckets: dict[str, list[tuple[float, object]]] = defaultdict(list)
    i = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        i += 1
        if i % frames_step != 0:
            continue
        faces = analyze(frame, det_size=(cfg.det_size, cfg.det_size), min_score=cfg.min_det_score)
        if not faces:
            continue
        face = max(faces, key=lambda f: f.det_score)
        sh = face_sharpness(frame, face)
        if sh < cfg.enrollment_min_sharpness:
            continue
        pl = pose_label(face, cfg.yaw_frontal, cfg.yaw_45, cfg.yaw_90, cfg.pitch_frontal)
        # Solo se enrolan las poses permitidas (min_poses): se descartan los
        # perfiles 90° (pi/pd, "casi de espaldas") y las poses degeneradas
        # (`other`), que ensuciaban la galería y daban baja tasa de acierto.
        if pl not in cfg.min_poses:
            continue
        buckets[pl].append((sh, face.embedding))
    cap.release()

    encs, quals, poses = [], [], []
    for pl, lst in buckets.items():
        lst.sort(key=lambda x: -x[0])
        for sh, emb in lst[:max_per_pose]:
            encs.append(emb)
            quals.append(sh)
            poses.append(pl)

    if encs:
        store = FaceStore(os.path.join(ruta, "motor/bbdd_reconocimiento", local_id, "face_enc_v2"),
                          max_per_person=cfg.max_encodings_per_person)
        # P2: proveniencia sintética estable (las poses de enrolamiento no tienen
        # fotos.id; se mueven con la persona al unir y nunca se separan por foto).
        store.add(cod_interno, encs, quals, poses,
                  sources=[f"enroll:{cod_interno}"] * len(encs))
    return len(encs)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("video")
    ap.add_argument("cod_interno")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--frames-step", type=int, default=5)
    ap.add_argument("--max-per-pose", type=int, default=8)
    ap.add_argument("--min-sharpness", type=float, default=None)
    args = ap.parse_args()

    cfg = Config()
    if args.min_sharpness is not None:
        cfg.enrollment_min_sharpness = args.min_sharpness

    n = enroll(args.local_id, args.video, args.cod_interno, args.ruta, cfg,
               frames_step=args.frames_step, max_per_pose=args.max_per_pose)
    print(n)
    return 0


if __name__ == "__main__":
    sys.exit(main())
