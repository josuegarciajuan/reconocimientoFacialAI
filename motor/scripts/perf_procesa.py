#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Perfilador de `procesa_video.py` — SOLO LECTURA sobre los datos.

Mide dónde se va el tiempo al analizar un vídeo real, fase por fase:
decodificación, cruces (MOG2 por línea), detector de personas y RetinaFace
(`analyze`), además de la carga de modelos (arranque + compilación OpenVINO).

NO toca datos: copia el vídeo a /tmp, nunca escribe en `motor/` ni borra el
origen. No arranca ni para servicios. Sirve para decidir si el backlog de vídeos
es techo de cómputo o patología de orquestación (docs/specs/16).

Uso:
    motor/venv/bin/python motor/scripts/perf_procesa.py <video.mp4> \
        [--cam 19] [--ruta /root/reconocimientoFacial] \
        [--lineas "x1,y1,x2,y2;x1,y1,x2,y2"] [--face-every 2] [--limit 0]
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
import time

import cv2

PROYECTO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, PROYECTO)

from motor.core.config import Config            # noqa: E402
from motor.core.model import analyze, get_app    # noqa: E402
from motor.core.quality import face_sharpness   # noqa: E402
from motor.cruces import (CrossingConfig, CrossingDetector, Line,  # noqa: E402
                          PersonDetector)


def _fmt(seg: float) -> str:
    return f"{seg:8.2f}s" if seg < 60 else f"{seg/60:8.2f}m"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", help="ruta del .mp4 de motor/videos/...")
    ap.add_argument("--cam", default="0")
    ap.add_argument("--ruta", default=PROYECTO)
    ap.add_argument("--lineas", default="",
                    help='líneas "x1,y1,x2,y2" separadas por ";" (las reales de la cámara)')
    ap.add_argument("--face-every", type=int, default=None)
    ap.add_argument("--limit", type=int, default=0, help="máx. frames (0 = todos)")
    args = ap.parse_args()

    if not os.path.isfile(args.video):
        print(f"ERROR: no existe {args.video}")
        return 1

    cfg = Config.from_env(args.ruta)
    face_every = args.face_every if args.face_every else cfg.face_every

    # Copia a /tmp: NUNCA se toca el origen (procesa_video lo borraría).
    tmp = os.path.join("/tmp", "perf_procesa_" + os.path.basename(args.video))
    shutil.copy2(args.video, tmp)

    lineas: list[Line] = []
    if args.lineas:
        for i, ln in enumerate([x for x in args.lineas.split(";") if x.strip()]):
            x1, y1, x2, y2 = (float(v) for v in ln.split(","))
            lineas.append(Line(x1, y1, x2, y2, line_id=str(i)))
    detectores = [CrossingDetector(l, CrossingConfig()) for l in lineas]
    persona = PersonDetector(CrossingConfig())

    # Arranque de modelos (carga ONNX + compilación OpenVINO), medido aparte.
    t0 = time.perf_counter()
    app = get_app((cfg.det_size, cfg.det_size))
    t_load = time.perf_counter() - t0
    provider = "?"
    try:
        provider = app.models["detection"].session.get_providers()[0]
    except Exception:  # noqa: BLE001
        pass

    cap = cv2.VideoCapture(tmp)
    if not cap.isOpened():
        print(f"ERROR: no se pudo abrir {tmp}")
        os.remove(tmp)
        return 1
    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0

    t = {"decode": 0.0, "cruces": 0.0, "analyze": 0.0, "sharp": 0.0, "persona": 0.0}
    nframes = n_analyzed = nface = nbody = ncross = 0
    t_start = time.perf_counter()
    while True:
        a = time.perf_counter()
        ret, frame = cap.read()
        t["decode"] += time.perf_counter() - a
        if not ret:
            break
        nframes += 1
        if args.limit and nframes > args.limit:
            break
        ts = nframes / fps

        if detectores:
            a = time.perf_counter()
            for det, ln in zip(detectores, lineas):
                for _ev in det.process(frame, ts):
                    ncross += 1
            t["cruces"] += time.perf_counter() - a

        if nframes % face_every == 0:
            n_analyzed += 1
            a = time.perf_counter()
            faces = analyze(frame, det_size=(cfg.det_size, cfg.det_size),
                            min_score=cfg.min_det_score)
            t["analyze"] += time.perf_counter() - a
            nface += len(faces)
            a = time.perf_counter()
            for f in faces:
                face_sharpness(frame, f)
            t["sharp"] += time.perf_counter() - a
            a = time.perf_counter()
            bbs = persona.process(frame)
            t["persona"] += time.perf_counter() - a
            nbody += len(bbs)

    cap.release()
    os.remove(tmp)
    total = time.perf_counter() - t_start

    print("=" * 62)
    print(f"perf_procesa  {os.path.basename(args.video)}")
    print(f"provider={provider}  det_size={cfg.det_size}  face_every={face_every}")
    print("-" * 62)
    print(f"arranque_modelos (1ª vez)            {_fmt(t_load)}")
    print(f"frames={nframes}  analizados={n_analyzed}  caras={nface}  cuerpos={nbody}  cruces={ncross}")
    print("-" * 62)
    print(f"decodificación                       {_fmt(t['decode'])}")
    print(f"cruces (MOG2 x{len(lineas)})              {_fmt(t['cruces'])}")
    print(f"RetinaFace (analyze)                 {_fmt(t['analyze'])}")
    print(f"nitidez (Laplaciano)                 {_fmt(t['sharp'])}")
    print(f"detector de personas                 {_fmt(t['persona'])}")
    print("-" * 62)
    print(f"TOTAL bucle                          {_fmt(total)}")
    if n_analyzed:
        print(f"media por frame analizado            {t['analyze']/n_analyzed*1000:8.0f} ms")
    if total > 0:
        for k in ("decode", "cruces", "analyze", "sharp", "persona"):
            print(f"  {k:8s} {t[k]/total*100:5.1f}%")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())
