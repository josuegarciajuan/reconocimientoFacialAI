#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Wrapper de `procesa_video.py` para el pool de SuperServer (M3).

Procesa UN vídeo **sin efectos sobre la casa**:
  - NO borra el vídeo, NO quita el marker, NO registra cruces en `ws.php`,
    NO escribe el embudo.
  - Escribe caras en `<ruta>/motor/caras/sinclasificar/...` y fotos de cruce en
    `<ruta>/motor/fotos_lineas/<linea>/...` (dentro del sandbox del worker).
  - Devuelve un JSON con los cruces detectados y las métricas del embudo para que
    la casa aplique los mismos efectos (`motor/pool_bridge.py`).

Uso (en el worker, con `--ruta` apuntando al sandbox):
    motor/venv/bin/python motor/procesa_video_pool.py <local> <cam> <fichero> \
        --ruta <sandbox> --lineas <lineas.json> --out-json <efectos.json> [--face-every N]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config            # noqa: E402
from motor.cruces import Line                   # noqa: E402
from motor.procesa_video import process_video   # noqa: E402


def cargar_lineas_json(path: str) -> list[Line]:
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    lineas = []
    for it in raw:
        lineas.append(Line(float(it["x1"]), float(it["y1"]), float(it["x2"]), float(it["y2"]),
                           line_id=str(it["id"])))
    return lineas


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("camara_id")
    ap.add_argument("fichero")
    ap.add_argument("--ruta", required=True, help="raíz del sandbox (motor/videos, .env)")
    ap.add_argument("--lineas", required=True, help="JSON con las líneas de la cámara")
    ap.add_argument("--out-json", required=True, help="ruta del JSON de efectos")
    ap.add_argument("--face-every", type=int, default=None)
    args = ap.parse_args()

    # Mismos topes de hilos que el proceso clásico (anti-sobresuscripción).
    from motor.core.threads import limit_threads
    limit_threads()

    cfg = Config.from_env(args.ruta)
    face_every = args.face_every if args.face_every is not None else cfg.face_every
    lineas = cargar_lineas_json(args.lineas)

    eventos: list = []
    resumen: dict = {}
    process_video(args.local_id, args.camara_id, args.fichero, args.ruta, cfg, face_every,
                  lineas=lineas, efectos=False, eventos=eventos, resumen=resumen)
    resumen["cruces_count"] = resumen.get("cruces", 0)
    resumen["cruces"] = eventos
    resumen["ts"] = time.time()

    out = os.path.abspath(args.out_json)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(resumen, fh, ensure_ascii=False, indent=2)

    print(f"[pool-video] {args.local_id}/{args.camara_id} {args.fichero}: "
          f"{resumen.get('frames', 0)} frames, {len(eventos)} cruces, "
          f"{resumen.get('caras_guard', 0)} caras guardadas", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
