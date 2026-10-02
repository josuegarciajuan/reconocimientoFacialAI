#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrapper del pool para `classify` (M3 de SuperServer) — split de embeddings.

Hace SOLO la parte pesada por crop: detección (`analyze`) + SR-before-embedding
(`enhance_embedding`) y devuelve, por fichero, las caras con su embedding. NO
toca la galería, no decide y no mueve nada: la decisión y la galería siguen en
la casa (`clasificador.py`), que inyecta estos resultados con `--faces-json`.

Uso (en el worker):
    python /app/motor/clasificador_pool.py --in /work/in --out /work/out/faces.json
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
from motor.core.superres import enhance_embedding                # noqa: E402

IMG_EXTS = (".jpg", ".jpeg", ".png")


def caras_de_crop(img, cfg) -> list[dict]:
    faces = analyze(img, det_size=(cfg.crop_det_size, cfg.crop_det_size),
                    min_score=cfg.min_det_score)
    out = []
    for fc in faces:
        emb = enhance_embedding(img, fc, cfg)
        out.append({
            "bbox": [int(v) for v in fc.bbox],
            "det_score": float(fc.det_score),
            "pose": [float(v) for v in fc.pose],
            "embedding": [float(v) for v in emb],
        })
    return out


def caras_base_de_crop(img, cfg) -> list[dict]:
    """Detección + embedding BASE (sin SR). Para elegir la cara de display en el
    busto (F17a): la casa solo compara cosenos, no necesita SR aquí y así el
    worker no paga `enhance_embedding` en cada busto."""
    faces = analyze(img, det_size=(cfg.crop_det_size, cfg.crop_det_size),
                    min_score=cfg.min_det_score)
    out = []
    for fc in faces:
        out.append({
            "bbox": [int(v) for v in fc.bbox],
            "det_score": float(fc.det_score),
            "pose": [float(v) for v in fc.pose],
            "embedding": [float(v) for v in fc.embedding],
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="in_dir", required=True, help="directorio con los crops")
    ap.add_argument("--busto-dir", dest="busto_dir", default=None,
                    help="directorio con los bustos del lote (F17a, opcional)")
    ap.add_argument("--local", required=True)
    ap.add_argument("--cam", required=True)
    ap.add_argument("--batch", default=None, help="id del lote (F4)")
    ap.add_argument("--out", required=True, help="ruta del faces.json de salida")
    args = ap.parse_args()

    from motor.core.threads import limit_threads
    limit_threads()
    cfg = Config.from_env(os.path.dirname(os.path.abspath(args.in_dir)))

    faces_map: dict[str, list] = {}
    if os.path.isdir(args.in_dir):
        for f in sorted(os.listdir(args.in_dir)):
            if not f.lower().endswith(IMG_EXTS):
                continue
            img = cv2.imread(os.path.join(args.in_dir, f))
            if img is None:
                continue
            faces_map[f] = caras_de_crop(img, cfg)

    busto_map: dict[str, list] = {}
    if args.busto_dir and os.path.isdir(args.busto_dir):
        for f in sorted(os.listdir(args.busto_dir)):
            if not f.lower().endswith(IMG_EXTS):
                continue
            img = cv2.imread(os.path.join(args.busto_dir, f))
            if img is None:
                continue
            busto_map[f] = caras_base_de_crop(img, cfg)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"local": str(args.local), "cam": str(args.cam), "batch": args.batch,
                   "faces": faces_map, "busto": busto_map}, fh)
    total = sum(len(v) for v in faces_map.values())
    print(f"[classify-pool] {len(faces_map)} crops, {total} caras, "
          f"{len(busto_map)} bustos", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
