#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Archivado de vídeos de movimiento — motor/archiva_video.py

Mueve el vídeo de captura a MP4 H.264 mínimo peso (`motor/core/video.py`),
registra el resultado en la tabla `videos` (vía `ws.php guardar_video`) y, con
`--borrar`, elimina el origen. NO borra el origen por defecto: `procesa_video.py`
sigue siendo el dueño del borrado tras el análisis (caras/cruces), y este archivo
puede lanzarse en paralelo sin condiciones de carrera.

- Si la captura ya es `.mp4` (nuevo algoritmo: guarda_movimientosV3.py) solo se
  reencapsula (`remux` stream copy, rápido); el transcode queda para `.avi` legacy.
- Genera además una miniatura JPG (1 frame) junto al MP4 y la registra en la
  columna `poster` para la columna VÍDEO de la UI.

Uso:
    motor/venv/bin/python motor/archiva_video.py <local> <cam> <fichero.avi|.mp4> \\
        [--ruta .] [--crf 26] [--fps 10] [--preset medium] [--borrar]

Salida (stdout): ruta del MP4 archivado o error descriptivo; exit 0/1.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.video import VideoConfig, comprimir_video, duracion_video, \
    dimensiones_video, extraer_poster, remux_video, ruta_archivo, ruta_video  # noqa: E402

PROYECTO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def php_ws(*args) -> str:
    try:
        r = subprocess.run(["php", os.path.join(PROYECTO, "ws.php"), *[str(a) for a in args]],
                           capture_output=True, text=True, timeout=30, cwd=PROYECTO)
        return r.stdout.strip()
    except Exception:
        return ""


def fecha_base_video(fichero: str) -> datetime | None:
    """Del nombre `{cam}_{fecha}_{hora}.{micro}.avi` extrae el datetime de inicio."""
    stem = fichero.rsplit(".", 1)[0] if fichero.lower().endswith(".avi") else fichero
    parts = stem.split("_")
    if len(parts) < 3:
        return None
    hora = parts[2].split(".")[0]
    try:
        return datetime.strptime(f"{parts[1]} {hora}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("camara_id")
    ap.add_argument("fichero")
    ap.add_argument("--ruta", default=PROYECTO)
    ap.add_argument("--crf", type=int, default=None)
    ap.add_argument("--fps", type=int, default=None)
    ap.add_argument("--preset", default=None)
    ap.add_argument("--borrar", action="store_true", help="borrar el AVI fuente tras archivar")
    args = ap.parse_args()

    cfg = VideoConfig()
    if args.crf is not None:
        cfg.crf = args.crf
    if args.fps is not None:
        cfg.fps = args.fps
    if args.preset is not None:
        cfg.preset = args.preset

    src = os.path.join(args.ruta, "motor", "videos", args.local_id, args.camara_id, args.fichero)
    if not os.path.exists(src):
        print(f"ERROR: no existe el vídeo fuente: {src}")
        return 1

    nombre_mp4 = os.path.splitext(args.fichero)[0] + ".mp4"
    dst = ruta_archivo(args.ruta, args.local_id, args.camara_id, nombre_mp4)

    # La captura ya escribe MP4 H.264 directo (guarda_movimientosV3.py): basta un
    # remux con stream copy (rápido). El transcode completo queda para los .avi legacy.
    if args.fichero.lower().endswith(".mp4"):
        peso = remux_video(src, dst)
    else:
        peso = comprimir_video(src, dst, cfg)
    if peso is None:
        print(f"ERROR: no se pudo archivar {src}")
        return 1

    duracion = duracion_video(dst)
    ancho, alto = dimensiones_video(dst)

    fecha_ini = fecha_base_video(args.fichero)
    if fecha_ini is None:
        fecha_ini = datetime.now()
    fecha_fin = fecha_ini + timedelta(seconds=duracion)

    # ruta relativa a la raíz del proyecto, tal y como la sirve video.php
    rel = os.path.relpath(dst, args.ruta).replace(os.sep, "/")
    if ruta_video(rel, args.ruta) is None:
        print(f"ERROR: ruta fuera del árbol de archivo: {rel}")
        return 1

    # miniatura (1 frame del vídeo) junto al MP4: poster para la columna VÍDEO de la UI
    poster_rel = ""
    poster_jpg = os.path.splitext(dst)[0] + ".jpg"
    if extraer_poster(dst, poster_jpg):
        poster_rel = os.path.relpath(poster_jpg, args.ruta).replace(os.sep, "/")
        if ruta_video(poster_rel, args.ruta) is None:
            poster_rel = ""

    video_id = php_ws("guardar_video",
                      args.local_id, args.camara_id, nombre_mp4, rel,
                      fecha_ini.strftime("%Y-%m-%d %H:%M:%S"), fecha_fin.strftime("%Y-%m-%d %H:%M:%S"),
                      str(duracion), str(peso), str(cfg.fps), str(ancho), str(alto), poster_rel)
    if not video_id or not video_id.isdigit():
        print(f"ERROR: registro en BD fallido para {dst} (respuesta: {video_id!r})")
        return 1

    if args.borrar and os.path.exists(src):
        os.remove(src)

    # limpiar el marker que creó detector.php (aux/archiva_<fichero>.txt)
    marker = os.path.join(args.ruta, "aux", "archiva_" + args.fichero + ".txt")
    if os.path.exists(marker):
        os.remove(marker)

    print(f"OK {video_id} {dst} {peso}B {duracion}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
