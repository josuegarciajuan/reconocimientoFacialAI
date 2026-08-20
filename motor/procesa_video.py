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
from motor.cruces import (CrossingConfig, CrossingDetector, Line,  # noqa: E402
                          PersonDetector, bbox_iou, bbox_overlap)

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


def torso_bbox(face, frame_w: int, frame_h: int, cfg: Config):
    """Caja de torso (F1, L1b): bajo la barbilla, ancho/alto proporcionales a la cara.

    Devuelve (x1, y1, x2, y2) o None si el crop no es viable (persona muy cerca,
    caja fuera del frame). NO altera el bbox ni el embedding de la cara: es un
    artefacto aparte con el mismo stem (mismo timestamp) para poder emparejarlo.
    """
    x1, y1, x2, y2 = face.bbox
    fw, fh = x2 - x1, y2 - y1
    if fw <= 0 or fh <= 0:
        return None
    cx = (x1 + x2) / 2.0
    w = fw * cfg.torso_w_face
    h = fh * cfg.torso_h_face
    tx1, tx2 = cx - w / 2.0, cx + w / 2.0
    ty1 = y2 + int(0.15 * fh)          # barbilla + pequeño offset
    ty2 = ty1 + h
    tx1, ty1 = max(0, int(tx1)), max(0, int(ty1))
    tx2, ty2 = min(frame_w, int(tx2)), min(frame_h, int(ty2))
    if (tx2 - tx1) < 0.5 * fw or (ty2 - ty1) < 0.5 * fh:
        return None
    return (tx1, ty1, tx2, ty2)


def busto_bbox(face, frame_w: int, frame_h: int, cfg: Config):
    """Caja de BUSTO (cabeza + hombros) para la foto final de display.

    A diferencia del crop de cara (tight, para embeddings) y del torso (solo
    ropa, L1b), este incluye la cabeza (arriba) y algo de pecho: es la imagen
    "de persona" que se muestra en el panel, con píxeles reales en el torso y
    solo la cara restaurada. Devuelve (x1, y1, x2, y2) o None si no es viable.
    """
    x1, y1, x2, y2 = face.bbox
    fw, fh = x2 - x1, y2 - y1
    if fw <= 0 or fh <= 0:
        return None
    cx = (x1 + x2) / 2.0
    w = fw * cfg.busto_w_face
    h = fh * cfg.busto_h_face
    top = y1 - fh * cfg.busto_head_pad
    bx1 = max(0, int(cx - w / 2.0))
    bx2 = min(frame_w, int(cx + w / 2.0))
    by1 = max(0, int(top))
    by2 = min(frame_h, int(top + h))
    if (bx2 - bx1) < fw or (by2 - by1) < fh:
        return None
    return (bx1, by1, bx2, by2)


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
    # PNG sin pérdidas: el crop es el input del SR/GFPGAN; guardarlo como JPEG
    # añadía una generación de compresión sobre caras ya muy pequeñas (~45 px).
    cv2.imwrite(os.path.join(out_dir, nombre + ".png"), crop)

    # Foto de busto (display): contexto cabeza+hombros, mismo stem en <cam>_busto/.
    # Se usa para la foto final que se muestra en el panel (torso real nítido).
    if cfg.busto_enabled:
        bb = busto_bbox(face, w, h, cfg)
        if bb is not None:
            busto = frame[bb[1]:bb[3], bb[0]:bb[2]]
            if busto.size > 0:
                busto_dir = os.path.join(ruta, "motor/caras/sinclasificar", local_id, f"{camara_id}_busto")
                os.makedirs(busto_dir, exist_ok=True)
                cv2.imwrite(os.path.join(busto_dir, nombre + ".png"), busto)

    # F1: crop de torso separado (mismo stem) para la capa L1b.
    # Si no hay torso visible (persona muy cerca / caja fuera), NO se guarda:
    # la capa quedará sin señal (c_torso=0) y el peso se redistribuye.
    tb = torso_bbox(face, w, h, cfg)
    if tb is not None:
        torso = frame[tb[1]:tb[3], tb[0]:tb[2]]
        if torso.size > 0:
            torso_dir = os.path.join(ruta, "motor/caras/sinclasificar", local_id, f"{camara_id}_cuerpo")
            os.makedirs(torso_dir, exist_ok=True)
            cv2.imwrite(os.path.join(torso_dir, nombre + ".jpg"), torso)


def guardar_cuerpo_sin_cara(ruta: str, local_id: str, camara_id: str, fichero: str,
                            frame, bbox, segs: float, cfg: Config, body_buffer: list) -> None:
    """F7: guarda el crop de CUERPO de una persona SIN cara visible (de espaldas).

    Contrato de nombres: `<cam>_cuerpo/<fichero>_<segs>_nocara.jpg` — el sufijo
    `_nocara` distingue estos crops de los de torso compañero (mismo stem que la
    cara). El clasificador los procesa SOLO con torso+VLM; NUNCA crea persona
    nueva por un crop de espaldas no identificable.
    """
    h, w = frame.shape[:2]
    x, y, bw, bh = bbox
    # margen para no cortar cabeza/piés
    x1, y1 = max(0, int(x - 0.1 * bw)), max(0, int(y - 0.05 * bh))
    x2, y2 = min(w, int(x + bw * 1.1)), min(h, int(y + bh * 1.05))
    crop = frame[y1:y2, x1:x2]
    if crop.size == 0:
        return
    # dedup por IoU con crops recientes de la misma persona
    for b in body_buffer:
        if bbox_iou((x, y, bw, bh), b) > 0.85:
            return
    body_buffer.append((x, y, bw, bh))
    if len(body_buffer) > 12:
        body_buffer.pop(0)

    out_dir = os.path.join(ruta, "motor/caras/sinclasificar", local_id, f"{camara_id}_cuerpo")
    os.makedirs(out_dir, exist_ok=True)
    nombre = f"{fichero}_{segs:.6f}_nocara"
    cv2.imwrite(os.path.join(out_dir, nombre + ".jpg"), crop)


def process_video(local_id: str, camara_id: str, fichero: str, ruta: str,
                  cfg: Config, face_every: int) -> int:
    video_path = os.path.join(ruta, "motor/videos", local_id, camara_id, fichero)
    if not os.path.exists(video_path):
        return 0

    lineas = cargar_lineas(camara_id)
    detectores = [CrossingDetector(l, CrossingConfig()) for l in lineas]
    persona_det = PersonDetector(CrossingConfig())
    fecha_base = fecha_base_video(fichero)

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return 0

    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    frame_idx = 0
    buffer = []
    body_buffer = []
    cruces = 0
    caras = 0
    cuerpos = 0

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

            # F7: personas SIN cara (de espaldas) -> crop de cuerpo
            for bb in persona_det.process(frame):
                tiene_cara = any(bbox_overlap(bb, tuple(f.bbox)) for f in faces)
                if not tiene_cara:
                    guardar_cuerpo_sin_cara(ruta, local_id, camara_id, fichero,
                                            frame, bb, ts, cfg, body_buffer)
                    cuerpos += 1

        frame_idx += 1

    cap.release()
    os.remove(video_path)
    # marker file de detector.php
    marker = os.path.join(ruta, "aux", fichero + ".txt")
    if os.path.exists(marker):
        os.remove(marker)

    print(f"procesa_video {local_id}/{camara_id} {fichero}: {frame_idx} frames, {cruces} cruces, "
          f"{caras} caras, {cuerpos} cuerpos-sin-cara", flush=True)
    return frame_idx


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("camara_id")
    ap.add_argument("fichero")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--face-every", type=int, default=None)
    ap.add_argument("--min-sharpness", type=float, default=None)
    ap.add_argument("--dedup-cosine", type=float, default=0.97)
    args = ap.parse_args()

    # Config.from_env (no Config()): aplica los overrides de .env (RF_MIN_SHARPNESS,
    # RF_DET_SIZE, etc.) igual que clasificador.py y reprocesar.py.
    cfg = Config.from_env(args.ruta)
    if args.min_sharpness is not None:
        cfg.min_sharpness = args.min_sharpness
    cfg.dedup_cosine = args.dedup_cosine
    face_every = args.face_every if args.face_every is not None else cfg.face_every

    process_video(args.local_id, args.camara_id, args.fichero, args.ruta, cfg, face_every)
    return 0


if __name__ == "__main__":
    sys.exit(main())
