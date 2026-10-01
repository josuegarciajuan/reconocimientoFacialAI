#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Diagnóstico de encuadre de caras por cámara — motor/diagnostico_caras.py

Herramienta READ-ONLY para el operador: mide el ANCHO MÁXIMO de cara que ve cada
cámara en los vídeos más recientes y clasifica cada cámara según lo aprovechable
que sea su cara para el reconocimiento:

    < 96 px     -> CRITICO (inutilizable)
    96 - 159 px -> mejorable (acercar/zoom)
    >= 160 px   -> ok

Sirve para decidir qué cámaras conviene acercar/reorientar/hacer zoom sin tocar
nada del sistema. No escribe ficheros ni modifica la BD.

Uso:
    motor/venv/bin/python motor/diagnostico_caras.py --local 1
    motor/venv/bin/python motor/diagnostico_caras.py --local 1 --camaras 21,13 \\
        --videos 2 --frames 5
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config      # noqa: E402
from motor.core.model import analyze      # noqa: E402

PROYECTO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
VIDEO_EXTS = (".mp4", ".avi", ".mkv", ".mov", ".m4v")

# Umbrales de diagnóstico (lado/ancho de cara en píxeles).
CRITICO_PX = 96
OK_PX = 160


def _diagnostico(max_width: int) -> str:
    if max_width < CRITICO_PX:
        return "CRITICO (inutilizable)"
    if max_width < OK_PX:
        return "mejorable (acercar/zoom)"
    return "ok"


def _camaras_con_videos(ruta: str, local_id: str) -> list[str]:
    base = os.path.join(ruta, "motor/videos", local_id)
    if not os.path.isdir(base):
        return []
    return sorted(d for d in os.listdir(base)
                  if os.path.isdir(os.path.join(base, d)))


def _videos_de_camara(ruta: str, local_id: str, camara_id: str,
                      n: int) -> list[str]:
    """Los `n` vídeos MÁS RECIENTES de la cámara (nombre incluye timestamp)."""
    base = os.path.join(ruta, "motor/videos", local_id, camara_id)
    if not os.path.isdir(base):
        return []
    vids = sorted(f for f in os.listdir(base)
                  if f.lower().endswith(VIDEO_EXTS))
    if n > 0:
        vids = vids[-n:]
    return vids


def _sample_frames(video_path: str, n_frames: int):
    """Genera `n_frames` frames repartidos uniformemente por el vídeo."""
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        cap.release()
        return
    try:
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if total <= 0:
            total = n_frames
        n_frames = max(1, int(n_frames))
        for i in range(n_frames):
            pos = int((i + 0.5) * total / n_frames)
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, pos))
            ret, frame = cap.read()
            if ret and frame is not None:
                yield frame
    finally:
        cap.release()


def medir_camara(ruta: str, local_id: str, camara_id: str, cfg: Config,
                 n_videos: int, n_frames: int) -> dict:
    """Mide el ancho de cara por cámara. Nunca lanza: devuelve anchuras vacías."""
    anchos: list[int] = []
    videos = _videos_de_camara(ruta, local_id, camara_id, n_videos)
    for fichero in videos:
        video_path = os.path.join(ruta, "motor/videos", local_id, camara_id, fichero)
        try:
            for frame in _sample_frames(video_path, n_frames):
                faces = analyze(frame, det_size=(cfg.det_size, cfg.det_size),
                                min_score=cfg.capture_min_det_score)
                for f in faces:
                    x1, _y1, x2, _y2 = f.bbox
                    anchos.append(max(0, int(round(x2 - x1))))
        except Exception as e:  # noqa: BLE001
            print(f"[aviso] {camara_id}/{fichero}: no se pudo analizar ({e})",
                  file=sys.stderr)
    if not anchos:
        return {"camara": camara_id, "n": 0, "max": 0, "avg": 0.0,
                "diag": "sin caras"}
    return {"camara": camara_id, "n": len(anchos), "max": max(anchos),
            "avg": sum(anchos) / len(anchos), "diag": _diagnostico(max(anchos))}


def _print_table(rows: list[dict]) -> None:
    print(f"{'cámara':<10} {'#caras':>7} {'max px':>7} {'avg px':>7}  diagnóstico")
    print("-" * 70)
    for r in rows:
        print(f"{r['camara']:<10} {r['n']:>7} {r['max']:>7} {r['avg']:>7.1f}  {r['diag']}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ruta", default=PROYECTO, help="raíz del proyecto")
    ap.add_argument("--local", default="1", help="id del local (default 1)")
    ap.add_argument("--camaras", default=None,
                    help="lista separada por comas; default: todas con vídeos")
    ap.add_argument("--videos", type=int, default=1,
                    help="vídeos más recientes por cámara (default 1)")
    ap.add_argument("--frames", type=int, default=3,
                    help="frames muestreados por vídeo (default 3)")
    ap.add_argument("--json", default=None,
                    help="escribe el informe como JSON en esta ruta (para el panel)")
    args = ap.parse_args()

    # OpenCV: topes de hilos como el resto del motor (no cambia resultados).
    try:
        from motor.core.threads import limit_threads
        limit_threads()
    except Exception:  # noqa: BLE001
        pass

    cfg = Config.from_env(args.ruta)

    if args.camaras:
        camaras = [c.strip() for c in args.camaras.split(",") if c.strip()]
    else:
        camaras = _camaras_con_videos(args.ruta, args.local)

    if not camaras:
        print(f"[diagnostico] no hay cámaras con vídeos en "
              f"motor/videos/{args.local}/")
        if args.json:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
                with open(args.json + ".tmp", "w", encoding="utf-8") as fh:
                    json.dump({"generado": time.time(), "local": args.local,
                               "filas": [], "criticas": []}, fh, ensure_ascii=False, indent=2)
                os.replace(args.json + ".tmp", args.json)
            except OSError as e:
                print(f"[diagnostico] no se pudo escribir el JSON: {e}", file=sys.stderr)
        return 0

    rows = []
    for cam in camaras:
        print(f"[diagnostico] analizando cámara {cam} "
              f"({args.videos} vídeo(s) x {args.frames} frame(s))...",
              file=sys.stderr)
        rows.append(medir_camara(args.ruta, args.local, cam, cfg,
                                 args.videos, args.frames))

    print()
    _print_table(rows)

    criticas = [r["camara"] for r in rows if r["max"] < CRITICO_PX]

    if args.json:
        # Informe estable para el panel (misma estructura que la tabla).
        informe = {
            "generado": time.time(),
            "local": args.local,
            "videos": args.videos,
            "frames": args.frames,
            "critico_px": CRITICO_PX,
            "ok_px": OK_PX,
            "filas": rows,
            "criticas": criticas,
        }
        try:
            os.makedirs(os.path.dirname(os.path.abspath(args.json)), exist_ok=True)
            tmp = args.json + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(informe, fh, ensure_ascii=False, indent=2)
            os.replace(tmp, args.json)
        except OSError as e:
            print(f"[diagnostico] no se pudo escribir el JSON: {e}", file=sys.stderr)

    if criticas:
        print()
        print("[RECOMENDACIÓN] Cámaras CRÍTICAS (cara < %d px, inutilizable para "
              "reconocimiento):" % CRITICO_PX)
        print("  " + ", ".join(criticas))
        print("  -> acercar/reorientar la cámara o forzar zoom para que la cara "
              "ocupe al menos 160 px de ancho.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
