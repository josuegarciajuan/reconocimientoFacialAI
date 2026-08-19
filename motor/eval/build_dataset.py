#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Construye el set etiquetado de evaluación desde crops REALES (F2/F3).

Fuente: `admin/caras_procesadas/<foto_id>.jpg` con el mapeo identidad de la BD
(fotos -> estancias -> personas). Salida (gitignored):

    motor/eval/data/<persona_cod>/
        <foto_id>_<pose>.jpg

Pose por foto calculada con el motor (pose_label de quality.py). Se limita a
`max_per_pose` fotos por clase de pose por persona para equilibrar el set.

Uso:
    motor/venv/bin/python motor/eval/build_dataset.py \
        --local 1 --min-fotos 4 --max-personas 8 --ruta /root/reconocimientoFacial
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import cv2  # noqa: E402

from motor.core.config import Config  # noqa: E402
from motor.core.env import load_env  # noqa: E402
from motor.core.model import analyze  # noqa: E402
from motor.core.quality import face_sharpness, pose_label  # noqa: E402

POSE_SUFIJOS = {"f", "pi", "pd", "m45i", "m45d", "arr", "aba", "other"}


def _mysql(ruta: str, sql: str) -> list[str]:
    env = load_env(ruta)
    cmd = ["mysql", "-u", env.get("RF_DB_USER", "root"), "-p" + env.get("RF_DB_PASS", ""),
           "-h", env.get("RF_DB_HOST", "localhost"), env.get("RF_DB_NAME", "reconocimientofacial"),
           "-N", "-e", sql]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"mysql error: {out.stderr.strip()}")
    return [l for l in out.stdout.strip().splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", default=1)
    ap.add_argument("--min-fotos", type=int, default=4)
    ap.add_argument("--max-personas", type=int, default=8)
    ap.add_argument("--max-per-pose", type=int, default=5)
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    args = ap.parse_args()

    cfg = Config()
    data_dir = os.path.join(args.ruta, "motor/eval/data")
    fotos_dir = os.path.join(args.ruta, "admin/caras_procesadas")
    os.makedirs(data_dir, exist_ok=True)

    # personas con >= min-fotos
    rows = _mysql(args.ruta,
        "SELECT p.cod_interno, COUNT(f.id) AS nf FROM personas p "
        "JOIN estancias e ON e.persona_id=p.id JOIN fotos f ON f.estancia_id=e.id "
        f"WHERE p.local_id={args.local} GROUP BY p.id HAVING nf>={args.min_fotos} "
        "ORDER BY nf DESC")
    personas = [r.split("\t")[0] for r in rows][: args.max_personas]
    print(f"personas elegidas: {len(personas)}")

    total = 0
    for cod in personas:
        out_p = os.path.join(data_dir, cod)
        os.makedirs(out_p, exist_ok=True)
        # limpiar versiones previas de este cod
        for f in os.listdir(out_p):
            os.remove(os.path.join(out_p, f))
        fotos = _mysql(args.ruta,
            "SELECT f.id FROM fotos f JOIN estancias e ON e.id=f.estancia_id "
            f"JOIN personas p ON p.id=e.persona_id WHERE p.cod_interno='{cod}' "
            "ORDER BY f.id")
        per_pose: dict[str, int] = {}
        n = 0
        for r in fotos:
            fid = r.strip()
            p = os.path.join(fotos_dir, f"{fid}.jpg")
            if not os.path.exists(p):
                continue
            img = cv2.imread(p)
            if img is None:
                continue
            faces = analyze(img, det_size=(cfg.det_size, cfg.det_size), min_score=cfg.min_det_score)
            if not faces:
                continue
            f = max(faces, key=lambda x: x.det_score)
            pose = pose_label(f, cfg.yaw_frontal, cfg.yaw_45, cfg.yaw_90, cfg.pitch_frontal)
            per_pose[pose] = per_pose.get(pose, 0) + 1
            if per_pose[pose] > args.max_per_pose:
                continue
            shutil.copy2(p, os.path.join(out_p, f"{fid}_{pose}.jpg"))
            n += 1
        total += n
        poses = ", ".join(f"{k}:{v}" for k, v in sorted(per_pose.items()))
        print(f"  {cod[:12]}... -> {n} fotos ({poses})")

    print(f"\ntotal set etiquetado: {total} fotos en {data_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
