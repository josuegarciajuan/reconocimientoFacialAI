#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detecta y limpia perfiles MEZCLADOS en face_enc_v2 — motor/detectar_mezclados.py

Problema: un clúster de batería transitivo (union-find a 0.30) podía añadir caras
de 2-3 personas distintas a UNA galería (perfil mezclado). El clasificador luego
hace match con cualquiera de ellas (agregación max) -> falsos positivos.

Dos modos:
  1. --check (por defecto): análisis por persona de face_enc_v2 (sin tocar nada).
     Marca perfiles con >= 2 sub-clústeres de tamaño >= min_size separados por un
     hueco (max sim inter-clúster < --thr): candidatos a estar mezclados.
  2. --apply: para las personas marcadas (o --cod concretos) re-embebe las fotos
     reales de la BD, re-clusteriza con umbral alto (--thr-apply) y separa en
     personas nuevas, con snapshot + journal reversible (F6).

Uso:
  motor/venv/bin/python motor/detectar_mezclados.py <local> [--ruta .] [--thr 0.30]
  motor/venv/bin/python motor/detectar_mezclados.py <local> --apply [--thr-apply 0.45]
  motor/venv/bin/python motor/detectar_mezclados.py <local> --apply --cod XXX YYY
  motor/venv/bin/python motor/detectar_mezclados.py <local> --rollback motor/backups/<ts>_mezclados

Requiere el binario `mysql` en PATH y credenciales en <ruta>/.env (RF_DB_*).
"""
from __future__ import annotations

import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config                 # noqa: E402
from motor.core.store import FaceStore               # noqa: E402
from motor.core.backup import (Journal, count_estancias, count_personas,   # noqa: E402
                               load_manifest, new_backup_dir, restore_db,
                               snapshot_db, verify_restore, write_manifest)
# Reutiliza el pipeline de re-embebido + clustering + BD de limpiar_catchall
from motor.limpiar_catchall import (cluster_centroide, embed_foto, load_cache,  # noqa: E402
                                    new_cod, save_cache, _mysql)


def find_mixed_profiles(store: FaceStore, thr: float = 0.30,
                        min_size: int = 2, min_total: int = 6) -> list[dict]:
    """Devuelve los perfiles candidatos a estar mezclados (análisis SOLO del
    diccionario face_enc_v2, sin re-embebido ni BD).

    Regla: >= 2 sub-clústeres de tamaño >= min_size, con un hueco entre ellos
    (max sim inter-clúster < thr) y >= min_total encodings en la persona.
    Un perfil limpio (una sola persona con poses variadas, genuino >= 0.32)
    normalmente forma 1 clúster o varios conectados por un hueco >= thr.
    """
    out: list[dict] = []
    for cod in store.persons():
        encs = store.person_encodings(cod)
        if encs is None or len(encs) < min_total:
            continue
        clusters = cluster_centroide(list(encs), thr, min_size=1)
        big = [c for c in clusters if len(c) >= min_size]
        if len(big) < 2:
            continue
        # hueco máximo entre sub-clústeres (similitud media entre miembros)
        S = encs @ encs.T
        inter_max = 0.0
        for i in range(len(big)):
            for j in range(i + 1, len(big)):
                sub = S[np.ix_(big[i], big[j])]
                if sub.size:
                    inter_max = max(inter_max, float(sub.max()))
        if inter_max < thr:
            out.append({
                "cod": cod,
                "total": len(encs),
                "clusters": sorted((len(c) for c in big), reverse=True),
                "inter_max": round(inter_max, 4),
            })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--thr", type=float, default=0.30,
                    help="umbral para considerar 2 sub-clústeres separados (check)")
    ap.add_argument("--min-size", type=int, default=2,
                    help="tamaño mínimo de cada sub-clúster para marcar")
    ap.add_argument("--apply", action="store_true",
                    help="aplicar limpieza a los perfiles marcados (o a --cod)")
    ap.add_argument("--thr-apply", type=float, default=0.45,
                    help="umbral de re-clusterización al aplicar (fotos reales re-embebidas)")
    ap.add_argument("--cod", action="append", default=[],
                    help="código(s) concreto(s) a limpiar (además de los marcados)")
    ap.add_argument("--rollback", metavar="DIR", default=None,
                    help="F6: deshacer una limpieza (motor/backups/<ts>_mezclados)")
    args = ap.parse_args()

    if args.rollback:
        return _rollback(args.ruta, args.rollback)

    cfg = Config()
    store = FaceStore(os.path.join(args.ruta, "motor/bbdd_reconocimiento", args.local_id, "face_enc_v2"),
                      max_per_person=cfg.max_encodings_per_person)

    marcados = find_mixed_profiles(store, thr=args.thr, min_size=args.min_size)
    print(f"personas en face_enc_v2: {len(store.persons())}")
    if not marcados:
        print("sin perfiles mezclados detectados")
    for m in marcados:
        print(f"  MIXED {m['cod']}  encodings={m['total']}  sub-clústeres={m['clusters']}  "
              f"hueco max inter={m['inter_max']}")

    if not args.apply:
        print("\n[check] solo informe. Usa --apply para limpiar (reversible).")
        return 0

    cods = sorted({m["cod"] for m in marcados} | set(args.cod))
    if not cods:
        print("[apply] nada que limpiar")
        return 0
    print(f"[apply] limpiando {len(cods)} personas: {cods}")

    # ---- pipeline (reutiliza limpiar_catchall): re-embebe fotos reales ----
    cache = load_cache("/tmp/mezclados_emb_cache.pkl")
    esc = lambda s: s.replace("\\", "\\\\").replace("'", "\\'")
    in_list = ",".join(f"'{esc(c)}'" for c in cods)
    rows = _mysql(args.ruta,
        "SELECT f.id, e.id FROM fotos f JOIN estancias e ON e.id=f.estancia_id "
        f"WHERE e.persona_id IN (SELECT id FROM personas WHERE cod_interno IN "
        f"({in_list})) ORDER BY f.id")
    print(f"fotos de los perfiles marcados: {len(rows)}")
    items, sin_cara = [], []
    for r in rows:
        fid, eid = (int(x) for x in r.split("\t"))
        res = embed_foto(args.ruta, fid, cfg, cache)
        if res is None:
            sin_cara.append((fid, eid))
        else:
            items.append({"fid": fid, "eid": eid, "emb": res[0], "q": res[1], "pose": res[2]})
    save_cache(cache, "/tmp/mezclados_emb_cache.pkl")

    clusters = cluster_centroide([it["emb"] for it in items], args.thr_apply)
    clusters.sort(key=len, reverse=True)
    print(f"re-clústers (umbral {args.thr_apply}): {len(clusters)}")

    # F6: snapshot + journal (reversible)
    before_counts = {"personas": count_personas(args.ruta),
                     "estancias": count_estancias(args.ruta),
                     "store_persons": len(store.persons())}
    out_dir = new_backup_dir(args.ruta, "mezclados")
    store.save_snapshot_bytes(os.path.join(out_dir, "face_enc_v2.bak"))
    snapshot_db(args.ruta, out_dir)
    journal = Journal(os.path.join(out_dir, "journal.jsonl"))
    write_manifest(out_dir, op="limpiar_mezclados", local_id=args.local_id,
                   thr_apply=args.thr_apply, cods=cods, before_counts=before_counts)

    asignaciones: dict[int, int] = {}
    for cl in clusters:
        cod = new_cod(args.ruta)
        embs = [items[j]["emb"] for j in cl]
        quals = [items[j]["q"] for j in cl]
        poses = [items[j]["pose"] for j in cl]
        store.add(cod, embs, quals, poses)
        pid = int(_mysql(args.ruta,
            "INSERT INTO personas (local_id, cod_interno) VALUES "
            f"({args.local_id}, '{cod}'); SELECT LAST_INSERT_ID();")[0])
        journal.append({"op": "create", "cod": cod, "pid": pid,
                        "estancia_ids": [items[j]["eid"] for j in cl],
                        "snapshot": "face_enc_v2.bak", "db": "db_snapshot.sql"})
        for j in cl:
            asignaciones[items[j]["eid"]] = pid

    if sin_cara:
        cod = new_cod(args.ruta)
        pid = int(_mysql(args.ruta,
            "INSERT INTO personas (local_id, cod_interno) VALUES "
            f"({args.local_id}, '{cod}'); SELECT LAST_INSERT_ID();")[0])
        journal.append({"op": "create", "cod": cod, "pid": pid,
                        "estancia_ids": [eid for _, eid in sin_cara],
                        "snapshot": "face_enc_v2.bak", "db": "db_snapshot.sql"})
        for _, eid in sin_cara:
            asignaciones[eid] = pid

    for eid, pid in asignaciones.items():
        _mysql(args.ruta, f"UPDATE estancias SET persona_id={pid} WHERE id={eid}")

    for cod in cods:
        store.remove(cod)
        _mysql(args.ruta, f"DELETE FROM personas WHERE cod_interno='{cod}'")
        journal.append({"op": "remove", "cod": cod,
                        "snapshot": "face_enc_v2.bak", "db": "db_snapshot.sql"})

    print(f"[apply] hechas {len(asignaciones)} reasignaciones, {len(clusters) + (1 if sin_cara else 0)} "
          f"personas nuevas, {len(cods)} perfiles mezclados eliminados.")
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
    store = FaceStore(os.path.join(ruta, "motor/bbdd_reconocimiento", "1", "face_enc_v2"),
                      max_per_person=cfg.max_encodings_per_person)
    manifest = load_manifest(backup_dir)
    esperado = manifest.get("antes") or {"personas": None, "estancias": None, "store_persons": None}
    print(f"[rollback] {len(entries)} ops en journal | estado esperado (pre-op): {esperado}")
    restore_db(ruta, db_sql)
    with open(os.path.join(ruta, "motor/bbdd_reconocimiento", "1", "face_enc_v2"), "wb") as fh:
        import pickle
        pickle.dump(store.load_snapshot_bytes(store_bak), fh)
    print("[rollback] BD y face_enc_v2 restaurados desde snapshots")
    verify_restore(ruta, store, esperado, len(entries))
    return 0


if __name__ == "__main__":
    sys.exit(main())
