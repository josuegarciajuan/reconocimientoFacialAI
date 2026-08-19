#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Limpia galerías 'catch-all' de face_enc_v2 + BD — motor/limpiar_catchall.py

Problema: las personas `0EQGxYBl4d...` y `M4uYLqx...` absorbieron cientos de encodings
de gente distinta (500 cada una, consistencia interna ~0.38 con mínimos negativos).
Eso infla las puntuaciones del 2º puesto y rompe la regla del margen del matching.

Solución (lo más completo posible):
  1. Re-embebe cada foto real de esas personas (admin/caras_procesadas/<foto_id>.jpg).
  2. Union-Find sobre los embeddings (umbral por defecto 0.45) -> sub-personas reales.
  3. Crea una persona nueva por clúster (cod_interno nuevo + encodings en face_enc_v2
     + fila en BD), reasigna sus estancias/fotos.
  4. Estancias sin cara embebible -> persona residual 'sinclasificar_<ts>' (revisión manual).
  5. Elimina las personas catch-all de BD y del diccionario.

Uso:
  # solo informe (no toca nada)
  motor/venv/bin/python motor/limpiar_catchall.py 1 --ruta /root/reconocimientoFacial
  # aplicar (crea snapshot + journal en motor/backups/<ts>_catchall/)
  motor/venv/bin/python motor/limpiar_catchall.py 1 --ruta /root/reconocimientoFacial --apply
  # deshacer (F6): restaura BD + face_enc_v2 al estado previo y verifica recuentos
  motor/venv/bin/python motor/limpiar_catchall.py 1 --ruta /root/reconocimientoFacial \
      --rollback motor/backups/<ts>_catchall

Requiere el binario `mysql` en PATH y credenciales en <ruta>/.env (RF_DB_*).
"""
from __future__ import annotations

import argparse
import os
import pickle
import random
import subprocess
import sys
from collections import defaultdict
from datetime import datetime

import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config                 # noqa: E402
from motor.core.model import analyze                 # noqa: E402
from motor.core.quality import face_sharpness, pose_label  # noqa: E402
from motor.core.store import FaceStore               # noqa: E402
from motor.core.backup import (Journal, count_estancias, count_personas,
                               load_manifest,
                               new_backup_dir, restore_db, snapshot_db,
                               verify_restore, write_manifest)  # noqa: E402

ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
CATCHALLS = ["0EQGxYBl4d8LETS1uDDyzLZM0", "M4uYLqx021I0aywbwNk9moIPg",
             "igpMtyWI7G1IzOIRWgemHz5oO", "LcBiCdPXCTPh66eXkjc1dKnpj",
             "hV5VdsbjdhcC2A3H8Js2a6LGc", "t0BQCfmUXjHxojdupwpwUfmmI"]
CACHE = "/tmp/catchall_emb_cache.pkl"


# ----------------------------------------------------------------------------
# helpers BD vía CLI mysql (el venv no trae driver MySQL; datos en árbol principal)
# ----------------------------------------------------------------------------

def _env(ruta: str) -> dict:
    env = {}
    f = os.path.join(ruta, ".env")
    if os.path.isfile(f):
        for line in open(f):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env[k] = v
    return env


def _mysql(ruta: str, sql: str) -> list[str]:
    env = _env(ruta)
    cmd = ["mysql", "-u", env.get("RF_DB_USER", "root"), "-p" + env.get("RF_DB_PASS", ""),
           "-h", env.get("RF_DB_HOST", "localhost"), env.get("RF_DB_NAME", "reconocimientofacial"),
           "-N", "-e", sql]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"mysql error: {out.stderr.strip()}")
    return [l for l in out.stdout.strip().splitlines() if l.strip()]


def new_cod(ruta: str) -> str:
    while True:
        cod = "".join(random.choice(ALPHABET) for _ in range(25))
        if not _mysql(ruta, f"SELECT 1 FROM personas WHERE cod_interno='{cod}' LIMIT 1"):
            return cod


# ----------------------------------------------------------------------------
# embeddings con caché (evita re-encodear en dry-run/apply)
# ----------------------------------------------------------------------------

def load_cache(cache_path: str) -> dict:
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "rb") as fh:
                return pickle.load(fh)
        except Exception:
            return {}
    return {}


def save_cache(cache: dict, cache_path: str) -> None:
    with open(cache_path, "wb") as fh:
        pickle.dump(cache, fh)


def embed_foto(ruta: str, fid: int, cfg: Config, cache: dict):
    key = str(fid)
    if key in cache:
        return cache[key]
    img = cv2.imread(os.path.join(ruta, "admin/caras_procesadas", f"{fid}.jpg"))
    if img is None:
        cache[key] = None
        return None
    faces = analyze(img, det_size=(cfg.det_size, cfg.det_size), min_score=cfg.min_det_score)
    if not faces:
        cache[key] = None
        return None
    f = max(faces, key=lambda x: x.det_score)
    cache[key] = (f.embedding, face_sharpness(img, f),
                  pose_label(f, cfg.yaw_frontal, cfg.yaw_45, cfg.yaw_90, cfg.pitch_frontal))
    return cache[key]


# ----------------------------------------------------------------------------
# clustering por centroide (evita el encadenamiento transitivo del union-find:
# A~B y B~C podían unir A~C aunque no se parecieran; aquí cada miembro debe
# superar el umbral contra el centroide del clúster)
# ----------------------------------------------------------------------------

def cluster_centroide(embs, thr: float, min_size: int = 2):
    import numpy as np
    S = np.stack(embs) @ np.stack(embs).T
    n = len(embs)
    remaining = set(range(n))
    clusters = []
    while remaining:
        idx = list(remaining)
        sub = S[np.ix_(idx, idx)]
        nbrs = sub >= thr
        nbrs[np.arange(len(idx)), np.arange(len(idx))] = False
        seed = idx[int(np.argmax(nbrs.sum(axis=1)))]
        members = {seed}
        centroid = np.stack(embs)[seed].copy()
        for _ in range(20):
            scores = np.stack(embs) @ centroid
            newm = {i for i in remaining if scores[i] >= thr}
            if newm == members:
                break
            members = newm
            centroid = np.stack(embs)[list(members)].mean(axis=0)
            norm = np.linalg.norm(centroid)
            if norm > 0:
                centroid /= norm
        if len(members) >= min_size:
            clusters.append(sorted(members))
        else:
            for i in sorted(members):
                clusters.append([i])
        remaining -= members
    return clusters


# ----------------------------------------------------------------------------
# main
# ----------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--apply", action="store_true", help="aplicar cambios (por defecto: dry-run)")
    ap.add_argument("--thr", type=float, default=0.45, help="umbral coseno para separar personas")
    ap.add_argument("--cache", default=CACHE)
    ap.add_argument("--cod", action="append", default=[], help="código adicional a limpiar")
    ap.add_argument("--rollback", metavar="DIR", default=None,
                    help="F6: deshacer la limpieza de un directorio motor/backups/<ts>_catchall")
    args = ap.parse_args()
    cods = CATCHALLS + args.cod

    if args.rollback:
        return _rollback(args.ruta, args.rollback)

    cfg = Config()
    cache = load_cache(args.cache)
    placeholders = ",".join("?" for _ in cods)
    # el CLI mysql no soporta prepared statements; se escapa cada código
    esc = lambda s: s.replace("\\", "\\\\").replace("'", "\\'")
    in_list = ",".join(f"'{esc(c)}'" for c in cods)
    rows = _mysql(args.ruta,
        "SELECT f.id, e.id FROM fotos f JOIN estancias e ON e.id=f.estancia_id "
        f"WHERE e.persona_id IN (SELECT id FROM personas WHERE cod_interno IN "
        f"({in_list})) ORDER BY f.id")
    print(f"fotos en catch-all: {len(rows)}")
    items = []          # {fid, eid, emb}
    sin_cara = []       # (fid, eid)
    for r in rows:
        fid, eid = (int(x) for x in r.split("\t"))
        res = embed_foto(args.ruta, fid, cfg, cache)
        if res is None:
            sin_cara.append((fid, eid))
        else:
            items.append({"fid": fid, "eid": eid, "emb": res[0], "q": res[1], "pose": res[2]})
    save_cache(cache, args.cache)

    print(f"  con cara embebible: {len(items)} | sin cara: {len(sin_cara)}")

    # 2. clústers de personas reales
    clusters = cluster_centroide([it["emb"] for it in items], args.thr)
    clusters.sort(key=len, reverse=True)
    print(f"clústers detectados (umbral {args.thr}): {len(clusters)}")
    for i, cl in enumerate(clusters):
        fids = sorted(items[j]["fid"] for j in cl)
        cams = set()
        print(f"  clúster {i}: {len(cl)} fotos, fids={fids[:6]}{'...' if len(fids)>6 else ''}")

    if not args.apply:
        print("\n[dry-run] no se aplicó nada. Usa --apply para ejecutar.")
        return 0

    # 3. aplicar: crear personas + reasignar + limpiar (F6: snapshot + journal)
    store = FaceStore(os.path.join(args.ruta, "motor/bbdd_reconocimiento", args.local_id, "face_enc_v2"),
                      max_per_person=cfg.max_encodings_per_person)

    before_counts = {"personas": count_personas(args.ruta),
                     "estancias": count_estancias(args.ruta),
                     "store_persons": len(store.persons())}
    out_dir = new_backup_dir(args.ruta, "catchall")
    store.save_snapshot_bytes(os.path.join(out_dir, "face_enc_v2.bak"))
    snapshot_db(args.ruta, out_dir)
    journal = Journal(os.path.join(out_dir, "journal.jsonl"))
    write_manifest(out_dir, op="limpiar_catchall", local_id=args.local_id,
                   thr=args.thr, cods=cods, before_counts=before_counts)

    asignaciones: dict[int, int] = {}   # estancia_id -> persona_id (nueva)
    nuevos_cods: list[str] = []

    for cl in clusters:
        cod = new_cod(args.ruta)
        nuevos_cods.append(cod)
        # face_enc_v2
        embs = [items[j]["emb"] for j in cl]
        quals = [items[j]["q"] for j in cl]
        poses = [items[j]["pose"] for j in cl]
        store.add(cod, embs, quals, poses)
        # BD: persona nueva
        pid = int(_mysql(args.ruta,
            "INSERT INTO personas (local_id, cod_interno) VALUES "
            f"({args.local_id}, '{cod}'); SELECT LAST_INSERT_ID();")[0])
        journal.append({"op": "create", "cod": cod, "pid": pid,
                        "estancia_ids": [items[j]["eid"] for j in cl],
                        "snapshot": "face_enc_v2.bak", "db": "db_snapshot.sql"})
        for j in cl:
            asignaciones[items[j]["eid"]] = pid

    # persona residual para estancias sin cara
    if sin_cara:
        cod = new_cod(args.ruta)
        nuevos_cods.append(cod)
        # entrada vacía en face_enc_v2: la persona existe para que store==BD
        # (el clasificador la ignora: 0 encodings -> score 0 en el matching)
        store.add(cod, [], [], [])
        pid = int(_mysql(args.ruta,
            "INSERT INTO personas (local_id, cod_interno, nombre) VALUES "
            f"({args.local_id}, '{cod}', 'sinclasificar_{datetime.now():%Y%m%d_%H%M%S}'); "
            "SELECT LAST_INSERT_ID();")[0])
        journal.append({"op": "create", "cod": cod, "pid": pid,
                        "estancia_ids": [eid for _, eid in sin_cara],
                        "snapshot": "face_enc_v2.bak", "db": "db_snapshot.sql"})
        for fid, eid in sin_cara:
            asignaciones[eid] = pid

    # reasignar estancias
    for eid, pid in asignaciones.items():
        _mysql(args.ruta, f"UPDATE estancias SET persona_id={pid} WHERE id={eid}")

    # eliminar personas catch-all (y sus encodings del diccionario)
    for cod in cods:
        store.remove(cod)
        _mysql(args.ruta, f"DELETE FROM personas WHERE cod_interno='{cod}'")
        journal.append({"op": "remove", "cod": cod,
                        "snapshot": "face_enc_v2.bak", "db": "db_snapshot.sql"})

    print(f"\n[apply] hechas {len(asignaciones)} reasignaciones, {len(nuevos_cods)} personas nuevas, "
          f"catch-all eliminadas ({len(cods)}).")
    print(f"[apply] snapshot + journal en {out_dir}  (rollback: --rollback {out_dir})")
    return 0


def _rollback(ruta: str, backup_dir: str) -> int:
    """F6: restaura BD + face_enc_v2 al estado previo de la limpieza y verifica."""
    db_sql = os.path.join(backup_dir, "db_snapshot.sql")
    store_bak = os.path.join(backup_dir, "face_enc_v2.bak")
    if not os.path.exists(db_sql) or not os.path.exists(store_bak):
        print(f"ERROR: faltan snapshots en {backup_dir} (necesito db_snapshot.sql y face_enc_v2.bak)")
        return 1
    journal_path = os.path.join(backup_dir, "journal.jsonl")
    entries = Journal(journal_path).entries() if os.path.exists(journal_path) else []

    cfg = Config()
    local_id = "1"   # el dump restaura el estado completo; solo necesitamos el path del store
    store = FaceStore(os.path.join(ruta, "motor/bbdd_reconocimiento", local_id, "face_enc_v2"),
                      max_per_person=cfg.max_encodings_per_person)
    manifest = load_manifest(backup_dir)
    esperado = manifest.get("antes") or {"personas": None, "estancias": None, "store_persons": None}
    print(f"[rollback] {len(entries)} ops en journal | estado esperado (pre-op): {esperado}")
    restore_db(ruta, db_sql)
    store_data = store.load_snapshot_bytes(store_bak)
    with open(os.path.join(ruta, "motor/bbdd_reconocimiento", local_id, "face_enc_v2"), "wb") as fh:
        pickle.dump(store_data, fh)
    print("[rollback] BD y face_enc_v2 restaurados desde snapshots")
    verify_restore(ruta, store, esperado, len(entries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
