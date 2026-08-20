#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reprocesado en alta resolución — motor/reprocesar.py

Aplica a lo ya capturado las mejoras de resolución y matching del pipeline
(det_size 1280 + SR x4 con top-up + SR-before-embedding):

  (a) --fotos   Restaura las fotos de `admin/caras_procesadas/` con GFPGAN
                (SR x4 + prior facial): las fotos pixeladas del pipeline antiguo
                (top-up LANCZOS4 a 512) pasan a caras naturales de 512 px.

  (b) --videos  Re-escanea `motor/videos_archivo/<local>/<cam>/*.mp4` con
                `Config.det_size` (1280) para recuperar caras lejanas que el
                detector a 640 perdía. Los crops se guardan en
                `motor/caras/sinclasificar/` con el MISMO contrato de nombres
                que `procesa_video.py`, y el daemon clasificador los procesa
                normalmente (matching contra face_enc_v2; puede crear persona
                nueva si no hay match, como en el pipeline normal).

  (c) --galeria Recalcula los embeddings de `face_enc_v2` con SR-before-embedding
                desde las fotos de cada persona (query y galería quedan en el
                mismo dominio). Antes de tocar nada hace un snapshot en
                `motor/backups/` (F6, reversible).

Ejecución (manual, con el sistema en marcha es seguro; los daemons recogen los
crops nuevos solos):
    motor/venv/bin/python motor/reprocesar.py <local> --fotos --videos --galeria

Advertencia: `--videos` recarga insightface a 1280 (~1 GB) y SR; ejecutar con
la máquina sin otras cargas pesadas si hay pocos GB libres.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config                            # noqa: E402
from motor.core.model import analyze                            # noqa: E402
from motor.core.quality import face_sharpness, pose_label       # noqa: E402
from motor.core.store import FaceStore                          # noqa: E402
from motor.core.superres import enhance_embedding, restore_face   # noqa: E402
from motor.procesa_video import guardar_cara                    # noqa: E402


def reprocesar_fotos(ruta: str, cfg: Config) -> int:
    """(a) Restaura las fotos de `admin/caras_procesadas/` con GFPGAN (SR + prior facial).

    Convierte las fotos pixeladas (top-up LANCZOS4 a 512 del pipeline antiguo)
    en caras naturales de 512 px. Si GFPGAN no está disponible, `restore_face`
    devuelve la imagen sin cambios (no rompe nada).
    """
    d = os.path.join(ruta, "admin/caras_procesadas")
    if not os.path.isdir(d):
        return 0
    n = 0
    for f in sorted(os.listdir(d)):
        if not f.lower().endswith(".jpg"):
            continue
        p = os.path.join(d, f)
        img = cv2.imread(p)
        if img is None:
            continue
        out = restore_face(img, cfg)
        cv2.imwrite(p, out, [cv2.IMWRITE_JPEG_QUALITY, 95])
        n += 1
    return n


def rescannear_video(ruta: str, local_id: str, camara_id: str, fichero: str,
                     cfg: Config, face_every: int) -> int:
    """Re-escanea UN vídeo archivado extrayendo caras a det_size alto (1280).

    Solo extracción (caras + crop de torso compañero); no toca cruces ni borra
    el vídeo. Devuelve el nº de caras guardadas en sinclasificar.
    """
    video_path = os.path.join(ruta, "motor/videos_archivo", local_id, camara_id, fichero)
    if not os.path.exists(video_path):
        return 0
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return 0
    fps = cap.get(cv2.CAP_PROP_FPS) or 10.0
    frame_idx = 0
    buffer = []
    caras = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % face_every == 0:
            faces = analyze(frame, det_size=(cfg.det_size, cfg.det_size),
                            min_score=cfg.min_det_score)
            for f in faces:
                guardar_cara(ruta, local_id, camara_id, fichero, frame, f,
                             frame_idx / fps, cfg, buffer)
                caras += 1
        frame_idx += 1
    cap.release()
    return caras


def rescannear_videos(ruta: str, local_id: str, cfg: Config, face_every: int) -> int:
    """(b) Re-escanea todos los MP4 archivados del local."""
    base = os.path.join(ruta, "motor/videos_archivo", local_id)
    if not os.path.isdir(base):
        return 0
    total = 0
    for cam in sorted(os.listdir(base)):
        cdir = os.path.join(base, cam)
        if not os.path.isdir(cdir):
            continue
        for fichero in sorted(os.listdir(cdir)):
            if not fichero.lower().endswith(".mp4"):
                continue
            c = rescannear_video(ruta, local_id, cam, fichero, cfg, face_every)
            total += c
            print(f"  {cam}/{fichero}: {c} caras", flush=True)
    return total


def reembeder_galeria(ruta: str, local_id: str, cfg: Config, max_fotos: int = 50) -> int:
    """(c) Recalcula los embeddings de cada persona con SR-before-embedding.

    Snapshot previo en cfg.backups_dir (F6) y sustitución por persona vía
    `FaceStore.reembed_person` (conserva la capa de apariencia/torso).
    """
    from motor.core.photos import find_person_photos

    store = FaceStore(os.path.join(ruta, "motor/bbdd_reconocimiento", local_id, "face_enc_v2"),
                      max_per_person=cfg.max_encodings_per_person)
    snap = os.path.join(ruta, cfg.backups_dir,
                        f"face_enc_v2_pre_reembed_{local_id}_{int(time.time())}.pickle")
    store.save_snapshot_bytes(snap)
    print(f"snapshot galería: {snap}", flush=True)

    n = 0
    for cod in store.persons():
        photos = find_person_photos(ruta, local_id, cod, max_n=max_fotos)
        encs: list = []
        quals: list[float] = []
        poses: list[str] = []
        for p in photos:
            img = cv2.imread(p)
            if img is None:
                continue
            faces = analyze(img, det_size=(cfg.crop_det_size, cfg.crop_det_size),
                            min_score=cfg.min_det_score)
            for f in faces:
                sh = face_sharpness(img, f)
                if sh < cfg.min_sharpness:
                    continue
                emb = enhance_embedding(img, f, cfg)
                encs.append(emb)
                quals.append(sh)
                poses.append(pose_label(f, cfg.yaw_frontal, cfg.yaw_45,
                                        cfg.yaw_90, cfg.pitch_frontal))
        if encs:
            store.reembed_person(cod, encs, quals, poses)
            n += 1
            print(f"  {cod}: {len(encs)} encodings re-embebidos", flush=True)
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--fotos", action="store_true", help="sube de resolución las fotos existentes")
    ap.add_argument("--videos", action="store_true", help="re-escanea los vídeos archivados a det_size alto")
    ap.add_argument("--galeria", action="store_true", help="recalcula los embeddings de la galería (face_enc_v2)")
    ap.add_argument("--face-every", type=int, default=6, help="muestreo de frames (6 = cada 6 frames)")
    args = ap.parse_args()

    if not (args.fotos or args.videos or args.galeria):
        ap.error("elige al menos una acción: --fotos, --videos o --galeria")

    cfg = Config.from_env(args.ruta)

    if args.fotos:
        n = reprocesar_fotos(args.ruta, cfg)
        print(f"fotos reprocesadas: {n}", flush=True)

    if args.videos:
        total = rescannear_videos(args.ruta, args.local_id, cfg, args.face_every)
        print(f"caras re-extraídas de vídeos: {total}", flush=True)

    if args.galeria:
        n = reembeder_galeria(args.ruta, args.local_id, cfg)
        print(f"personas con galería re-embebida: {n}", flush=True)

    return 0


if __name__ == "__main__":
    sys.exit(main())
