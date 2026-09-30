#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrapper one-shot de la foto HQ para el pool de SuperServer (M3).

Calcula la HQ de **un** job y NO aplica efectos en la casa:
  - escribe el `.hq` en `--out-hq` (dentro del sandbox);
  - NO borra el JSON ni las fuentes (lo hará el puente en la casa).
Las rutas `frames[].src` del job deben apuntar a ficheros ya presentes en el
sandbox (el adaptador los trae y reescribe las rutas).

Uso (en el worker):
    python /app/motor/photo_worker_pool.py --job /work/job.json --ruta /work \
        --out-hq /work/out/<nombre>.hq
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config                     # noqa: E402
from motor.photo_worker import compute_hq, load_pairs, write_hq  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    ap.add_argument("--ruta", required=True)
    ap.add_argument("--out-hq", required=True)
    args = ap.parse_args()

    from motor.core.threads import limit_threads
    limit_threads()

    cfg = Config.from_env(args.ruta)
    out, pairs, _srcs = load_pairs(args.job)
    if not out or not pairs:
        print(f"[photo-pool] job sin material: {args.job}", flush=True)
        return 2

    img_hq = compute_hq(pairs, cfg)
    os.makedirs(os.path.dirname(os.path.abspath(args.out_hq)), exist_ok=True)
    write_hq(args.out_hq, img_hq)
    print(f"[photo-pool] {os.path.basename(out)}.hq "
          f"({img_hq.shape[1]}x{img_hq.shape[0]}) [{len(pairs)} frame(s)]", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
