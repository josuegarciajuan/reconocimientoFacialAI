#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Actualiza face_enc_v2 al mover una foto entre personas (B4).

Sustituye al legacy `cambiar_foto_de_persona.py` (roto: NameError + corrompía `points`).

Uso:
    motor/venv/bin/python motor/cambiar_foto.py <local_id> <foto_id> <cod_origen> <cod_destino> [--ruta .]

Acción:
  1. Re-encodea `admin/caras_procesadas/<foto_id>.jpg` (RetinaFace/ArcFace).
  2. Añade el encoding a la persona destino.
  3. Elimina de la persona origen el encoding más parecido (si supera min_cosine).
  4. Emite etiqueta de feedback (F3, §5): la foto movida NO era de la persona
     origen -> par IMPOSTOR (verdad de calibración del panel).
"""
from __future__ import annotations

import argparse
import os
import sys

import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config                 # noqa: E402
from motor.core.model import analyze                 # noqa: E402
from motor.core.quality import face_sharpness, pose_label  # noqa: E402
from motor.core.store import FaceStore               # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("foto_id")
    ap.add_argument("cod_origen")
    ap.add_argument("cod_destino")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--min-cosine", type=float, default=0.5)
    args = ap.parse_args()

    cfg = Config()
    foto_path = os.path.join(args.ruta, "admin/caras_procesadas", args.foto_id + ".jpg")
    if not os.path.exists(foto_path):
        print("foto no encontrada")
        return 1

    img = cv2.imread(foto_path)
    if img is None:
        print("foto ilegible")
        return 1

    faces = analyze(img, det_size=(cfg.det_size, cfg.det_size), min_score=cfg.min_det_score)
    if not faces:
        print("sin cara en la foto")
        return 1

    face = max(faces, key=lambda f: f.det_score)
    store = FaceStore(os.path.join(args.ruta, "motor/bbdd_reconocimiento", args.local_id, "face_enc_v2"),
                      max_per_person=cfg.max_encodings_per_person)
    store.add(args.cod_destino,
              [face.embedding],
              [face_sharpness(img, face)],
              [pose_label(face, cfg.yaw_frontal, cfg.yaw_45, cfg.yaw_90, cfg.pitch_frontal)])
    removed = store.remove_closest(args.cod_origen, face.embedding, min_cosine=args.min_cosine)

    # F3: feedback — la foto movida era IMPOSTOR de la persona origen
    if cfg.feedback_enabled:
        from motor.core.feedback import FeedbackCollector, embedding_hash
        fc = FeedbackCollector(args.ruta, args.local_id, enabled=True)
        fc.label_move(embedding_hash(face.embedding), args.cod_origen)

    print(f"ok (encoding añadido a {args.cod_destino}; removido de origen: {removed})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
