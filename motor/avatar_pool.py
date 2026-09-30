#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrapper one-shot de avatar para el pool de SuperServer (M3).

Calcula el PNG del avatar de **una** persona y NO aplica efectos en la casa:
  - escribe el PNG en `--out` (dentro del sandbox);
  - escribe el id de la foto elegida en `--chosen` (el bridge de la casa lo usa
    para el sidecar `.foto`); NO escribe el sidecar.

Las rutas `src` de `--fotos-json` deben apuntar a ficheros presentes en el
sandbox (el adaptador los trae).

Uso (en el worker):
    python /app/motor/avatar_pool.py --fotos-json /work/fotos.json \
        --out /work/out/<persona>.png --chosen /work/out/chosen.txt --size 96
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2                                                       # noqa: E402
from motor.core.avatar import best_frontal, generar_avatar       # noqa: E402


def cargar_fotos(path: str) -> list[tuple[int, str]]:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    out = []
    for it in raw:
        try:
            fid = int(it.get("id"))
        except (TypeError, ValueError):
            continue
        src = str(it.get("src") or "")
        if fid > 0 and src:
            out.append((fid, src))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fotos-json", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--chosen", required=True)
    ap.add_argument("--size", type=int, default=96)
    args = ap.parse_args()

    from motor.core.threads import limit_threads
    limit_threads()

    fotos = cargar_fotos(args.fotos_json)
    if not fotos:
        print("[avatar-pool] sin fotos válidas", flush=True)
        return 2

    elegida = best_frontal(fotos)
    if elegida is None:
        for fid, ruta in fotos:
            if cv2.imread(ruta) is not None:
                elegida = fid
                break
    if elegida is None:
        print("[avatar-pool] sin fotos legibles", flush=True)
        return 2

    ruta_foto = dict(fotos)[elegida]
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    png = generar_avatar(elegida, ruta_foto, args.out, out_size=args.size)
    if not png:
        print("[avatar-pool] no se pudo generar el avatar", flush=True)
        return 1
    os.makedirs(os.path.dirname(os.path.abspath(args.chosen)), exist_ok=True)
    with open(args.chosen, "w", encoding="utf-8") as fh:
        fh.write(str(elegida))
    print(f"[avatar-pool] generado {elegida} ({args.size}px)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
