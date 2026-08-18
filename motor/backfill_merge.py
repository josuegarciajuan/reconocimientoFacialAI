#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backfill de merge de personas duplicadas — motor/backfill_merge.py

Tras recalibrar umbrales y limpiar galerías catch-all, algunas personas de
face_enc_v2/BD son la misma identidad (p. ej. KaiZA3↔nRLmEs = 0.385, y casos
con coseno 1.000: la misma cara quedó enrolada en dos personas).

Estrategia CONSERVADORA (aprendida del primer intento, que sobre-fusionó 71→9):
  1. Calcula el best-cosine entre cada par de personas.
  2. Union-Find solo sobre pares con coseno >= --thr (por defecto 0.60: duplicados
     evidentes; 1.000 = misma cara exacta).
  3. VALIDACIÓN anti-encadenamiento: cada clúster candidato solo se fusiona si su
     coherencia interna (media del best-cosine entre TODAS las personas del grupo)
     supera --min-coherence (0.45). Si no, se descarta el clúster entero.
  4. Fusiona en la persona con más encodings: FaceStore.merge + reasignar estancias
     en BD + borrar la persona redundante.

El límite de 0.60 evita el encadenamiento A~B, B~C (0.40) ⇒ A~C que rompió la
primera versión; los pares del usuario por debajo de 0.60 quedan para el flujo
normal del clasificador (umbrales ya calibrados) o para "Unir" manual (F5).

Uso:
  # solo informe
  motor/venv/bin/python motor/backfill_merge.py 1 --ruta /root/reconocimientoFacial
  # aplicar (crea snapshot + journal en motor/backups/<ts>_backfill/)
  motor/venv/bin/python motor/backfill_merge.py 1 --ruta /root/reconocimientoFacial --apply
  # deshacer (F6): restaura BD + face_enc_v2 al estado previo y verifica recuentos
  motor/venv/bin/python motor/backfill_merge.py 1 --ruta /root/reconocimientoFacial \
      --rollback motor/backups/<ts>_backfill
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config               # noqa: E402
from motor.core.store import FaceStore              # noqa: E402
from motor.core.backup import (Journal, count_estancias, count_personas,
                               new_backup_dir, restore_db, snapshot_db,
                               verify_restore, write_manifest)  # noqa: E402


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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--apply", action="store_true", help="aplicar cambios (por defecto: dry-run)")
    ap.add_argument("--thr", type=float, default=0.60, help="best-cosine mínimo entre personas para considerar fusión")
    ap.add_argument("--min-coherence", type=float, default=0.45, help="media intra mínima del clúster candidato")
    ap.add_argument("--rollback", metavar="DIR", default=None,
                    help="F6: deshacer el backfill de un directorio motor/backups/<ts>_backfill")
    args = ap.parse_args()

    if args.rollback:
        return _rollback(args.ruta, args.rollback)

    cfg = Config()
    store = FaceStore(os.path.join(args.ruta, "motor/bbdd_reconocimiento", args.local_id, "face_enc_v2"),
                      max_per_person=cfg.max_encodings_per_person)

    cods = store.persons()
    print(f"personas: {len(cods)} | umbral fusión={args.thr} coherencia={args.min_coherence}")

    emb_cache = {c: store.person_encodings(c) for c in cods}
    emb_cache = {c: e for c, e in emb_cache.items() if e is not None and len(e) > 0}

    # 1. pares con best-cosine >= thr
    pairs = []
    lista = sorted(emb_cache.keys())
    for i in range(len(lista)):
        A = emb_cache[lista[i]]
        for j in range(i + 1, len(lista)):
            B = emb_cache[lista[j]]
            s = float(np.max(A @ B.T))
            if s >= args.thr:
                pairs.append((s, lista[i], lista[j]))
    pairs.sort(reverse=True)
    print(f"pares con best-cosine >= {args.thr}: {len(pairs)}")

    # 2. union-find
    parent = {c: c for c in lista}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for _, a, b in pairs:
        union(a, b)

    groups = defaultdict(list)
    for c in lista:
        groups[find(c)].append(c)

    # 3. validar coherencia de cada clúster (media del best-cosine entre sus personas)
    candidatos = []
    for g in groups.values():
        if len(g) < 2:
            continue
        sims = []
        for i in range(len(g)):
            A = emb_cache[g[i]]
            for j in range(i + 1, len(g)):
                B = emb_cache[g[j]]
                sims.append(float(np.max(A @ B.T)))
        media = float(np.mean(sims))
        if media >= args.min_coherence:
            candidatos.append((media, g))
        else:
            print(f"  DESCARTADO (coherencia {media:.3f} < {args.min_coherence}): {[c[:10] for c in g]}")

    candidatos.sort(reverse=True)
    print(f"clústers a fusionar (coherentes): {len(candidatos)}")
    for media, g in candidatos:
        n_enc = {c: len(emb_cache[c]) for c in g}
        keep = max(g, key=lambda c: n_enc[c])
        print(f"  coherencia={media:.3f} | {len(g)} personas | se queda {keep[:12]} "
              f"({n_enc[keep]} encs) | absorbe {[c[:10] for c in g if c != keep]}")

    if not args.apply:
        print("\n[dry-run] no se aplicó nada. Usa --apply para ejecutar.")
        return 0

    # 4. aplicar (F6: reversible — snapshot + journal antes de mutar)
    rows = _mysql(args.ruta, f"SELECT id, cod_interno, local_id FROM personas WHERE local_id={args.local_id}")
    pid_of = {r.split("\t")[1]: int(r.split("\t")[0]) for r in rows}

    before_counts = {"personas": count_personas(args.ruta),
                     "estancias": count_estancias(args.ruta),
                     "store_persons": len(store.persons())}

    out_dir = new_backup_dir(args.ruta, "backfill")
    store.save_snapshot_bytes(os.path.join(out_dir, "face_enc_v2.bak"))
    snapshot_db(args.ruta, out_dir)
    journal = Journal(os.path.join(out_dir, "journal.jsonl"))
    write_manifest(out_dir, op="backfill_merge", local_id=args.local_id,
                   thr=args.thr, min_coherence=args.min_coherence,
                   before_counts=before_counts)

    fusiones = 0
    for media, g in candidatos:
        n_enc = {c: len(emb_cache[c]) for c in g}
        keep = max(g, key=lambda c: n_enc[c])
        for c in g:
            if c == keep:
                continue
            # estancias que se reasignan (para auditoría)
            estancia_ids: list[int] = []
            if keep in pid_of and c in pid_of:
                estancia_ids = [int(x) for x in _mysql(
                    args.ruta, f"SELECT GROUP_CONCAT(id) FROM estancias WHERE persona_id={pid_of[c]}"
                )[0].split(",")] if _mysql(args.ruta, f"SELECT 1 FROM estancias WHERE persona_id={pid_of[c]} LIMIT 1") else []
                _mysql(args.ruta, f"UPDATE estancias SET persona_id={pid_of[keep]} WHERE persona_id={pid_of[c]}")
                _mysql(args.ruta, f"DELETE FROM personas WHERE id={pid_of[c]}")
                pid_of.pop(c)
            j = store.merge_undoable(keep, c)
            journal.append({
                "op": "merge", "src": c, "dst": keep,
                "src_pid": pid_of.get(c), "dst_pid": pid_of.get(keep),
                "estancia_ids": estancia_ids,
                "encodings_moved": j["encodings_moved"],
                "snapshot": "face_enc_v2.bak", "db": "db_snapshot.sql",
                "src_person": None,   # la copia exacta vive en el snapshot completo
            })
            fusiones += 1

    print(f"\n[apply] fusiones: {fusiones} | personas finales face_enc_v2: {len(store.persons())}")
    print(f"[apply] snapshot + journal en {out_dir}  (rollback: --rollback {out_dir})")
    return 0


def _rollback(ruta: str, backup_dir: str) -> int:
    """F6: restaura BD + face_enc_v2 al estado previo del backfill y verifica."""
    db_sql = os.path.join(backup_dir, "db_snapshot.sql")
    store_bak = os.path.join(backup_dir, "face_enc_v2.bak")
    if not os.path.exists(db_sql) or not os.path.exists(store_bak):
        print(f"ERROR: faltan snapshots en {backup_dir} (necesito db_snapshot.sql y face_enc_v2.bak)")
        return 1

    journal_path = os.path.join(backup_dir, "journal.jsonl")
    entries = Journal(journal_path).entries() if os.path.exists(journal_path) else []
    n_ops = len(entries)

    cfg = Config()
    store = FaceStore(os.path.join(ruta, "motor/bbdd_reconocimiento", "1", "face_enc_v2"),
                      max_per_person=cfg.max_encodings_per_person)
    before = {"personas": count_personas(ruta), "estancias": count_estancias(ruta),
              "store_persons": len(store.persons())}

    print(f"[rollback] {n_ops} ops en journal | antes: {before}")
    restore_db(ruta, db_sql)
    store_data = store.load_snapshot_bytes(store_bak)
    with open(os.path.join(ruta, "motor/bbdd_reconocimiento", "1", "face_enc_v2"), "wb") as fh:
        import pickle
        pickle.dump(store_data, fh)
    print("[rollback] BD y face_enc_v2 restaurados desde snapshots")
    verify_restore(ruta, store, before, n_ops)
    return 0


if __name__ == "__main__":
    sys.exit(main())
