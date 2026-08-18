#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Procesador de vídeo — motor/procesa_video.py

Sustituye a `procesa_videosV6.py` (4c):
  1. CRUCES DE LÍNEA: usa `motor/cruces.py` (MOG2 + tracking) en lugar de `cv2.bgsegm`
     (no disponible en el venv headless). Foto en `motor/fotos_lineas/<linea>/<uid>.jpg`
     y registro en `cruces_lineas` vía `ws.php guarda_cruce` (ya seguro).
  2. CARAS: usa RetinaFace/ArcFace (`analyze()`) en lugar del SSD legacy. Crop guardado
     en `motor/caras/sinclasificar/<local>/<cam>/<FICHERO>_<segs>.jpg` con el MISMO
     contrato de nombres que espera `clasificador.py`.

Uso:
    motor/venv/bin/python motor/procesa_video.py <local> <cam> <fichero> \
        [--ruta .] [--face-every 3] [--min-sharpness 60] [--dedup-cosine 0.97]
"""
from __future__ import annotations

import argparse
import os
import random
import subprocess
import sys
from datetime import datetime, timedelta

import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config                       # noqa: E402
from motor.core.model import analyze                       # noqa: E402
from motor.core.quality import face_sharpness              # noqa: E402
from motor.cruces import CrossingConfig, CrossingDetector, Line  # noqa: E402

ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

# Raíz del proyecto = padre de motor/ (ws.php y config/rutas.php viven aquí)
PROYECTO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def random_code(n: int = 25) -> str:
    return "".join(random.choice(ALPHABET) for _ in range(n))


def php_ws(*args) -> str:
    try:
        r = subprocess.run(["php", os.path.join(PROYECTO, "ws.php"), *[str(a) for a in args]],
                           capture_output=True, text=True, timeout=30, cwd=PROYECTO)
        return r.stdout.strip()
    except Exception:
        return ""


def cargar_lineas(camara_id: str) -> list[Line]:
    lineas = []
    ids = php_ws("listado_lineas", camara_id)
    for lid in [x.strip() for x in ids.split(",") if x.strip()]:
        coords = php_ws("coordenadas_linea", lid).split(",")
        if len(coords) == 4:
            try:
                lineas.append(Line(float(coords[0]), float(coords[1]), float(coords[2]), float(coords[3]), line_id=lid))
            except ValueError:
                pass
    return lineas


def fecha_base_video(fichero: str) -> datetime | None:
    """Del nombre `{cam}_{fecha}_{hora}.{micro}.avi` extrae datetime base."""
    stem = fichero.rsplit(".", 1)[0] if fichero.lower().endswith(".avi") else fichero
    parts = stem.split("_")
    if len(parts) < 3:
        return None
    hora = parts[2].split(".")[0]
    try:
        return datetime.strptime(f"{parts[1]} {hora}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def guardar_cruce(ruta: str, ev, linea: Line, fecha_base: datetime | None) -> None:
    out_dir = os.path.join(ruta, "motor/fotos_lineas", linea.line_id)
    os.makedirs(out_dir, exist_ok=True)
    uid = random_code()
    cv2.imwrite(os.path.join(out_dir, uid + ".jpg"), ev.frame)

    if fecha_base:
        fecha_str = (fecha_base + timedelta(seconds=ev.timestamp)).strftime("%Y-%m-%d %H:%M:%S")
    else:
        fecha_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    php_ws("guarda_cruce", linea.line_id, fecha_str, str(ev.direction), str(int(ev.x)), str(int(ev.y)), uid)


def guardar_cara(ruta: str, local_id: str, camara_id: str, fichero: str, frame,
                 face, segs: float, cfg: Config, buffer: list) -> None:
    # dedup: si ya guardamos una cara casi idéntica hace poco, la saltamos
    for b in buffer:
        if float(face.embedding @ b) > cfg.dedup_cosine:
            return
    if face_sharpness(frame, face) < cfg.min_sharpness:
        return
    buffer.append(face.embedding)
    if len(buffer) > 8:
        buffer.pop(0)

    h, w = frame.shape[:2]
    x1, y1, x2, y2 = face.bbox
    # pad proporcional al tamaño de la cara (más contexto en caras pequeñas;
    # antes era un pad fijo de 50 px que recortaba caras lejanas).
    pad = int(0.35 * max(y2 - y1, x2 - x1)) + 10
    x1, y1 = max(0, x1 - pad), max(0, y1 - pad)
    x2, y2 = min(w, x2 + pad), min(h, y2 + pad)
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return

    out_dir = os.path.join(ruta, "motor/caras/sinclasificar", local_id, camara_id)
    os.makedirs(out_dir, exist_ok=True)
    nombre = f"{fichero}_{segs:.6f}"
    cv2.imwrite(os.path.join(out_dir, nombre + ".jpg"), crop)


def process_video(local_id: str, camara_id: str, fichero: str, ruta: str,
                  cfg: Config, face_every: int) -> int:
    video_path = os.path.join(ruta, "motor/videos", local_id, camara_id, fichero)
    if not os.path.exists(video_path):
        return 0

    lineas = cargar_lineas(camara_id)
    detectores = [CrossingDetector(l, CrossingConfig()) for l in lineas]
    fecha_base = fecha_base_video(fichero)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return 0

    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    frame_idx = 0
    buffer = []
    cruces = 0
    caras = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        ts = frame_idx / fps

        # cruces de línea
        for det, linea in zip(detectores, lineas):
            for ev in det.process(frame, ts):
                guardar_cruce(ruta, ev, linea, fecha_base)
                cruces += 1

        # caras (muestreo para no saturar CPU)
        if frame_idx % face_every == 0:
            faces = analyze(frame, det_size=(cfg.det_size, cfg.det_size), min_score=cfg.min_det_score)
            for f in faces:
                guardar_cara(ruta, local_id, camara_id, fichero, frame, f, ts, cfg, buffer)
                caras += 1

        frame_idx += 1

    cap.release()
    os.remove(video_path)
    # marker file de detector.php
    marker = os.path.join(ruta, "aux", fichero + ".txt")
    if os.path.exists(marker):
        os.remove(marker)

    print(f"procesa_video {local_id}/{camara_id} {fichero}: {frame_idx} frames, {cruces} cruces, {caras} caras", flush=True)
    return frame_idx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("camara_id")
    ap.add_argument("fichero")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--face-every", type=int, default=3)
    ap.add_argument("--min-sharpness", type=float, default=None)
    ap.add_argument("--dedup-cosine", type=float, default=0.97)
    args = ap.parse_args()

    cfg = Config()
    if args.min_sharpness is not None:
        cfg.min_sharpness = args.min_sharpness
    cfg.dedup_cosine = args.dedup_cosine

    process_video(args.local_id, args.camara_id, args.fichero, args.ruta, cfg, args.face_every)
    return 0


if __name__ == "__main__":
    sys.exit(main())
