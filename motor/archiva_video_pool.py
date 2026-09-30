#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrapper one-shot de archivado para el pool de SuperServer (M3).

Reencapsula/transcodifica el vídeo fuente y genera el poster, SIN efectos en la
casa: no toca la BD (`ws.php`), no borra el origen ni el marker. Escribe:

  - el MP4 en `<out-dir>/motor/videos_archivo/<local>/<cam>/<name>`;
  - el poster JPG junto al MP4;
  - un `--out-meta` JSON con pesos/medidas para que el bridge de la casa registre
    el vídeo con `guardar_video` igual que el proceso clásico.

Uso (en el worker):
    python /app/motor/archiva_video_pool.py --src /work/in/<f> \
        --out-dir /work/out --local 1 --cam 15 --name <f>.mp4 \
        [--crf 20 --fps 10 --preset medium] --out-meta /work/out/archive.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.video import (VideoConfig, comprimir_video, duracion_video,  # noqa: E402
                              dimensiones_video, extraer_poster, remux_video,
                              ruta_archivo, ruta_video)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="vídeo fuente dentro del sandbox")
    ap.add_argument("--out-dir", required=True, help="raíz de salida (se usa como --ruta)")
    ap.add_argument("--local", required=True)
    ap.add_argument("--cam", required=True)
    ap.add_argument("--name", required=True, help="nombre del MP4 de salida")
    ap.add_argument("--crf", type=int, default=None)
    ap.add_argument("--fps", type=int, default=None)
    ap.add_argument("--preset", default=None)
    ap.add_argument("--out-meta", required=True)
    args = ap.parse_args()

    if not os.path.exists(args.src):
        print(f"ERROR: no existe el vídeo fuente: {args.src}", flush=True)
        return 1

    cfg = VideoConfig()
    if args.crf is not None:
        cfg.crf = args.crf
    if args.fps is not None:
        cfg.fps = args.fps
    if args.preset is not None:
        cfg.preset = args.preset

    dst = ruta_archivo(args.out_dir, args.local, args.cam, args.name)
    if args.src.lower().endswith(".mp4"):
        peso = remux_video(args.src, dst)
    else:
        peso = comprimir_video(args.src, dst, cfg)
    if peso is None:
        print(f"ERROR: no se pudo archivar {args.src}", flush=True)
        return 1

    rel = os.path.relpath(dst, args.out_dir).replace(os.sep, "/")
    if ruta_video(rel, args.out_dir) is None:
        print(f"ERROR: ruta fuera del árbol de archivo: {rel}", flush=True)
        return 1

    poster_rel = ""
    poster_jpg = os.path.splitext(dst)[0] + ".jpg"
    if extraer_poster(dst, poster_jpg):
        poster_rel = os.path.relpath(poster_jpg, args.out_dir).replace(os.sep, "/")
        if ruta_video(poster_rel, args.out_dir) is None:
            poster_rel = ""

    meta = {
        "local": str(args.local),
        "cam": str(args.cam),
        "name": args.name,
        "rel": rel,
        "peso": int(peso),
        "duracion": duracion_video(dst),
        "ancho": dimensiones_video(dst)[0],
        "alto": dimensiones_video(dst)[1],
        "poster_rel": poster_rel,
        "fps": int(cfg.fps),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out_meta)), exist_ok=True)
    with open(args.out_meta, "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False)
    print(f"[archive-pool] {rel} {peso}B {meta['duracion']}s poster={poster_rel!r}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
