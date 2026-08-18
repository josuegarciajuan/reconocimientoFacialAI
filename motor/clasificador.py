#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Clasificador de caras — motor/clasificador.py

Sustituye a `procesa_fotos_def_borrosaparteV2.py`. Flujo por pasada:
  1. Recorre `motor/caras/sinclasificar/<local>/<cam>/`.
  2. Filtra: sin cara -> removidas/notienecaras; desenfocada -> removidas/nopasafiltros.
  3. Agrupa por proximidad temporal ("baterías", < batch_seconds).
  4. Dentro de cada batería, agrupa caras de la misma persona (coseno).
  5. Match contra face_enc_v2 (mejor coincidencia multi-plantilla).
  6. Asigna persona (match) o crea nueva; mueve la foto representativa con el
     MISMO contrato de nombre que espera clasificadorV2.php:
        motor/caras/<local>/<cam>/<persona>/<stem>[_----<stem2>]_<id>.jpg

Uso (daemon, como antes):
    motor/venv/bin/python motor/clasificador.py <local> <cam>
Uso (una pasada, para tests/calibración):
    motor/venv/bin/python motor/clasificador.py <local> <cam> --once
"""
from __future__ import annotations

import argparse
import os
import random
import shutil
import sys
import time
from datetime import datetime

import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config            # noqa: E402
from motor.core.matching import cosine, match_group  # noqa: E402
from motor.core.model import analyze           # noqa: E402
from motor.core.quality import face_sharpness, pose_label  # noqa: E402
from motor.core.store import FaceStore         # noqa: E402

ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
IMG_EXTS = (".jpg", ".jpeg", ".png")


def log(*args):
    print(*args, flush=True)


def random_code(n: int = 25) -> str:
    return "".join(random.choice(ALPHABET) for _ in range(n))


def parse_timestamp(filename: str) -> float | None:
    """Del nombre `{cam}_{fecha}_{hora}.{micro}.avi_{segs}.jpg` extrae epoch (float)."""
    stem = filename.rsplit(".", 1)[0]           # quita la extensión de imagen
    parts = stem.split("_")
    if len(parts) < 4:
        return None
    fecha, hora_part, segs_part = parts[1], parts[2], parts[3]
    hora = hora_part.split(".")[0]
    segs = segs_part.split(".")[0]
    try:
        base = datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M:%S")
        return base.timestamp() + float(segs)
    except ValueError:
        return None


def cluster_faces(faces_emb, group_threshold: float) -> list[list[int]]:
    """Union-Find sobre los embeddings de la batería (misma persona = mismo clúster)."""
    n = len(faces_emb)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(n):
        for j in range(i + 1, n):
            if cosine(faces_emb[i], faces_emb[j]) >= group_threshold:
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return list(groups.values())


def process_battery(battery, ruta: str, local_id: str, camara_id: str, cfg: Config, store: FaceStore):
    # batería: lista de dicts {file, path, img, faces, ts}
    # aplanar caras -> (embedding, índice_item)
    face_list = []  # (emb, item_idx)
    for idx, it in enumerate(battery):
        for f in it["faces"]:
            face_list.append((f.embedding, idx))

    clusters = cluster_faces([e for e, _ in face_list], cfg.group_threshold)

    for cluster in clusters:
        item_idxs = sorted({face_list[i][1] for i in cluster})
        embs = [face_list[i][0] for i in cluster]

        # foto representativa = la más enfocada del clúster
        best = None
        best_sharp = -1.0
        for idx in item_idxs:
            it = battery[idx]
            for f in it["faces"]:
                sh = face_sharpness(it["img"], f)
                if sh > best_sharp:
                    best_sharp = sh
                    best = (idx, f)

        result = match_group(embs, store, cfg)
        if result.verdict == "new" or result.person is None:
            person = random_code()
        else:
            person = result.person

        # nombre de salida: stem representativo (+ "----" entrada/salida si hay >=2 fotos distintas)
        stems = [battery[idx]["file"].rsplit(".", 1)[0] for idx in item_idxs]
        stems_sorted = sorted(stems, key=lambda s: parse_timestamp(s + ".jpg") or 0)
        if len(stems_sorted) >= 2 and stems_sorted[0] != stems_sorted[-1]:
            nombre = f"{stems_sorted[0]}----{stems_sorted[-1]}"
        else:
            nombre = stems_sorted[0] if stems_sorted else battery[item_idxs[0]]["file"].rsplit(".", 1)[0]

        foto_id = random_code()
        out_dir = os.path.join(ruta, "motor/caras", local_id, camara_id, person)
        os.makedirs(out_dir, exist_ok=True)
        out_name = f"{nombre}_{foto_id}.jpg"
        rep_item = battery[best[0]]
        shutil.move(rep_item["path"], os.path.join(out_dir, out_name))

        # refinar el diccionario (solo si es match seguro; no contaminar en "uncertain")
        if result.verdict == "match":
            encs = [f.embedding for idx in item_idxs for f in battery[idx]["faces"]]
            quals = [face_sharpness(battery[idx]["img"], f) for idx in item_idxs for f in battery[idx]["faces"]]
            poses = [pose_label(f, cfg.yaw_frontal, cfg.yaw_45, cfg.yaw_90, cfg.pitch_frontal)
                     for idx in item_idxs for f in battery[idx]["faces"]]
            store.add(person, encs, quals, poses)
        elif result.verdict == "new":
            encs = [f.embedding for idx in item_idxs for f in battery[idx]["faces"]]
            quals = [face_sharpness(battery[idx]["img"], f) for idx in item_idxs for f in battery[idx]["faces"]]
            poses = [pose_label(f, cfg.yaw_frontal, cfg.yaw_45, cfg.yaw_90, cfg.pitch_frontal)
                     for idx in item_idxs for f in battery[idx]["faces"]]
            store.add(person, encs, quals, poses)

        # eliminar el resto de fotos del clúster (ya procesadas)
        for idx in item_idxs:
            p = battery[idx]["path"]
            if os.path.exists(p):
                os.remove(p)

        log(f"[{result.verdict}] {len(item_idxs)} foto(s) -> {person} (best={result.best_score:.3f})")


def process_once(ruta: str, local_id: str, camara_id: str, cfg: Config, store: FaceStore) -> int:
    dir_in = os.path.join(ruta, "motor/caras/sinclasificar", local_id, camara_id)
    notienecaras = os.path.join(ruta, "motor/removidas/notienecaras")
    nopasafiltros = os.path.join(ruta, "motor/removidas/nopasafiltros")
    os.makedirs(notienecaras, exist_ok=True)
    os.makedirs(nopasafiltros, exist_ok=True)

    if not os.path.isdir(dir_in):
        return 0

    items = []
    for f in sorted(os.listdir(dir_in)):
        if not f.lower().endswith(IMG_EXTS):
            continue
        p = os.path.join(dir_in, f)
        img = cv2.imread(p)
        if img is None:
            shutil.move(p, os.path.join(nopasafiltros, f))
            continue
        faces = analyze(img, det_size=(cfg.det_size, cfg.det_size), min_score=cfg.min_det_score)
        if not faces:
            shutil.move(p, os.path.join(notienecaras, f))
            continue
        focused = [fc for fc in faces if face_sharpness(img, fc) >= cfg.min_sharpness]
        if not focused:
            shutil.move(p, os.path.join(nopasafiltros, f))
            continue
        items.append({"file": f, "path": p, "img": img, "faces": focused, "ts": parse_timestamp(f)})

    if not items:
        return 0

    items.sort(key=lambda x: (x["ts"] is None, x["ts"] or 0))

    # agrupar en baterías
    baterias = []
    cur = []
    prev_ts = None
    for it in items:
        if prev_ts is None or (it["ts"] is not None and prev_ts is not None and (it["ts"] - prev_ts) <= cfg.batch_seconds):
            cur.append(it)
        else:
            if cur:
                baterias.append(cur)
            cur = [it]
        prev_ts = it["ts"]
    if cur:
        baterias.append(cur)

    n = 0
    for bat in baterias:
        process_battery(bat, ruta, local_id, camara_id, cfg, store)
        n += 1
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("camara_id")
    ap.add_argument("token", nargs="?", default=None, help="token identificador de Jos_Thread (se ignora)")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--once", action="store_true", help="una sola pasada (sin bucle)")
    ap.add_argument("--secure", type=float, default=None)
    ap.add_argument("--match", type=float, default=None)
    ap.add_argument("--margin", type=float, default=None)
    ap.add_argument("--min-sharpness", type=float, default=None)
    args, _desconocidos = ap.parse_known_args()  # tolera el token final de Jos_Thread

    cfg = Config()
    if args.secure is not None:
        cfg.secure_threshold = args.secure
    if args.match is not None:
        cfg.match_threshold = args.match
    if args.margin is not None:
        cfg.margin = args.margin
    if args.min_sharpness is not None:
        cfg.min_sharpness = args.min_sharpness

    store = FaceStore(os.path.join(args.ruta, "motor/bbdd_reconocimiento", args.local_id, "face_enc_v2"),
                      max_per_person=cfg.max_encodings_per_person)

    log(f"clasificador {args.local_id}/{args.camara_id} — face_enc_v2 con {len(store.persons())} personas")
    while True:
        try:
            n = process_once(args.ruta, args.local_id, args.camara_id, cfg, store)
            if n:
                log(f"procesadas {n} batería(s)")
            if args.once:
                return 0
            time.sleep(1)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(main())
