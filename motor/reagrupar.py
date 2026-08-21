#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Reagrupación de la galería existente con la CASCADA (F3) — motor/reagrupar.py

Detecta personas DUPLICADAS en face_enc_v2 ejecutando el algoritmo original
(`fusion.run_cascade` con los umbrales configurados en `motor/core/config.py`).
Por cada par (A,B) de personas:
  - L1a cara: s_face = max(cos(A_enc, B_enc)); c_face = face_confidence
    (nivel + margen vs la mejor OTRA persona + nitidez de la foto representativa).
  - L1c zonas: s_zona = s_face re-confirmada; c_zona = compatibilidad de pose
    de los perfiles + acuerdo de silueta de las fotos representativas.
  - Fusión ponderada (pesos-prior configurados) -> veredicto del algoritmo:
      match     -> el par SUPERA los umbrales -> CANDIDATO A MERGE
      uncertain -> no concluye -> REVISIÓN MANUAL (no se toca)
      new       -> por debajo de los umbrales -> NO merge

Solo se fusionan los pares `match` (con --apply), con reversibilidad F6
(snapshot store + dump BD + journal por operación; `--rollback` lo deshace).

Uso:
  # reporte (SOLO LECTURA)
  motor/venv/bin/python motor/reagrupar.py --local 1 --ruta /root/reconocimientoFacial
  # aplicar SOLO los pares que superan los umbrales (reversible)
  motor/venv/bin/python motor/reagrupar.py --local 1 --ruta ... --apply
  # deshacer
  motor/venv/bin/python motor/reagrupar.py --local 1 --ruta ... \
      --rollback motor/backups/<ts>_reagrupar
"""
from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.backup import (Journal, _mysql, count_estancias, count_personas,  # noqa: E402
                               load_manifest, new_backup_dir, restore_db, snapshot_db,
                               verify_restore, write_manifest)
from motor.core.config import Config  # noqa: E402
from motor.core.fusion import CascadeContext, run_cascade  # noqa: E402
from motor.core.matching import LayerScore, face_confidence  # noqa: E402
from motor.core.model import analyze  # noqa: E402
from motor.core.photos import find_person_photos  # noqa: E402
from motor.core.quality import face_sharpness, pose_label  # noqa: E402
from motor.core.store import FaceStore  # noqa: E402
from motor.core.zones import pose_confidence, silhouette_descriptor, silhouette_sim  # noqa: E402


def load_embeddings(store: FaceStore) -> dict[str, np.ndarray]:
    """cod -> matriz (n,512) de encodings (solo personas con encodings)."""
    out = {}
    for cod in store.persons():
        encs = store.person_encodings(cod)
        if encs is not None and len(encs):
            out[cod] = np.asarray(encs, dtype=np.float32)
    return out


def best_pair_cosine(A: np.ndarray, B: np.ndarray) -> float:
    return float(np.max(A @ B.T))


class RepResolver:
    """Fotos representativas + datos de cara por persona (con caché)."""

    def __init__(self, ruta: str, local_id: str, cfg: Config):
        self.ruta = ruta
        self.local_id = local_id
        self.cfg = cfg
        self._cache: dict[str, dict] = {}

    def face_data(self, cod: str) -> dict | None:
        if cod in self._cache:
            return self._cache[cod]
        photos = find_person_photos(self.ruta, self.local_id, cod, max_n=2)
        out = {"photos": photos, "sil": None, "pose": None, "sharpness": 0.0}
        for p in photos:
            img = cv2.imread(p)
            if img is None:
                continue
            faces = analyze(img, det_size=(self.cfg.det_size, self.cfg.det_size),
                            min_score=self.cfg.min_det_score)
            if not faces:
                continue
            f = max(faces, key=lambda x: x.det_score)
            out["sil"] = silhouette_descriptor(f)
            out["pose"] = pose_label(f, self.cfg.yaw_frontal, self.cfg.yaw_45,
                                     self.cfg.yaw_90, self.cfg.pitch_frontal)
            out["sharpness"] = max(out["sharpness"], face_sharpness(img, f))
            out["photo"] = p
            break
        self._cache[cod] = out
        return out


def persona_pose_profile(store: FaceStore, cod: str) -> list[str]:
    p = store.person(cod)
    return list(p.get("poses", [])) if p else []


def zona_score_pair(store: FaceStore, resolver: RepResolver, cfg: Config,
                    cod_a: str, cod_b: str, s_face: float) -> LayerScore:
    """L1c para un PAR: compatibilidad de pose + acuerdo de silueta."""
    pa = resolver.face_data(cod_a)
    pb = resolver.face_data(cod_b)
    poses_a = persona_pose_profile(store, cod_a)
    poses_b = persona_pose_profile(store, cod_b)
    pconf = max((pose_confidence(q, g) for q in (poses_a or [None])
                 for g in (poses_b or [None])), default=0.6)
    sil = 0.5
    if pa and pb and pa.get("sil") is not None and pb.get("sil") is not None \
            and pa["sil"].size and pb["sil"].size:
        sil = silhouette_sim(pa["sil"], pb["sil"])
    c = float(np.clip(0.6 * pconf + 0.4 * sil, 0.0, 1.0))
    return LayerScore(score=float(s_face), confidence=c, available=True)


def evaluar_par(store: FaceStore, embs: dict[str, np.ndarray], resolver: RepResolver,
                cfg: Config, cod_a: str, cod_b: str, s_face: float) -> dict:
    """Ejecuta la cascada original sobre el par (A,B) -> veredicto del algoritmo.

    NOTA: en el matching POR PARES no existe el concepto de "segundo candidato"
    para el margen (ambas galerías son el par); la confianza de la capa cara usa
    nivel absoluto + nitidez de la foto representativa (s_other=0).
    Se activa la cascada (CARA autoridad + silueta/zonas de apoyo) con los
    umbrales CONFIGURADOS; torso/VLM/OpenAI quedan fuera. La capa `zonas` se
    calcula SOLO para el reporte (c_zona): desde 2026-08-21 ya no participa en
    la decisión (re-reporta s_face, evidencia circular; la banda gris la
    resuelve secure_threshold o revision)."""
    import copy
    cfg = copy.copy(cfg)                 # no mutar el Config compartido
    cfg.cascade_enabled = True
    cfg.zones_enabled = True
    cfg.torso_enabled = False
    cfg.vlm_enabled = False
    cfg.openai_enabled = False

    sharp_a = resolver.face_data(cod_a).get("sharpness", 0.0)
    c_face = face_confidence(s_face, 0.0, sharp_a, cfg)
    face_layer = LayerScore(score=float(s_face), confidence=c_face)

    face_scores = {cod_b: float(s_face)}
    ctx = CascadeContext(
        zonas=lambda cod: zona_score_pair(store, resolver, cfg, cod_a, cod, s_face),
    )
    result = run_cascade(face_scores, ctx, cfg, face_layer)
    # reporte: c_zona se conserva aunque zonas ya no decide (evidencia circular)
    result.layer_scores["zonas"] = zona_score_pair(store, resolver, cfg, cod_a, cod_b, s_face)
    S, conf = 0.0, 0.0
    # S de la fusión real (cara + zona) para el reporte
    layers = result.layer_scores
    if layers:
        from motor.core.fusion import fuse
        S, conf = fuse(layers, {"cara": cfg.w_cara, "torso": cfg.w_torso,
                                "zona": cfg.w_torso, "vlm": cfg.w_llm,
                                "openai": cfg.w_llm})
    return {
        "a": cod_a, "b": cod_b, "s_face": s_face, "c_face": c_face,
        "c_zona": (layers.get("zonas").confidence if layers.get("zonas") else 0.0),
        "S": S, "conf": conf, "verdict": result.verdict,
    }


def coherencia_interna(embs: dict[str, np.ndarray], max_sample: int = 200) -> dict[str, float]:
    """Media del coseno intra-persona (detección de galerías contaminadas)."""
    out = {}
    for cod, encs in embs.items():
        if len(encs) < 3:
            continue
        if len(encs) > max_sample:
            idx = np.linspace(0, len(encs) - 1, max_sample).astype(int)
            encs = encs[idx]
        S = encs @ encs.T
        iu = np.triu_indices(len(encs), k=1)
        out[cod] = float(S[iu].mean()) if len(iu[0]) else 0.0
    return out


def reporte(ruta: str, local_id: str, cfg: Config, store: FaceStore, floor: float,
            out_dir: str, min_coherence: float = 0.20) -> list[dict]:
    os.makedirs(out_dir, exist_ok=True)
    embs = load_embeddings(store)
    resolver = RepResolver(ruta, local_id, cfg)
    cods = sorted(embs.keys())
    n = len(cods)
    print(f"personas con encodings: {n}")

    # coherencia interna por persona (detección de galerías contaminadas)
    coh = coherencia_interna(embs)
    contaminadas = {c for c, m in coh.items() if m < min_coherence}

    # pares candidatos
    pares = []
    for i in range(n):
        for j in range(i + 1, n):
            s = best_pair_cosine(embs[cods[i]], embs[cods[j]])
            if s >= floor:
                pares.append((s, cods[i], cods[j]))
    pares.sort(reverse=True)
    print(f"pares con coseno >= {floor}: {len(pares)}")

    resultados = []
    for s, a, b in pares:
        r = evaluar_par(store, embs, resolver, cfg, a, b, s)
        # guardia anti-catch-all: el merge exige que AMBAS galerías sean coherentes
        r["contaminada"] = (a in contaminadas or b in contaminadas)
        resultados.append(r)
        # miniaturas del par para revisión visual
        pdir = os.path.join(out_dir, "pairs", f"{len(resultados):03d}_{a[:8]}_{b[:8]}")
        os.makedirs(pdir, exist_ok=True)
        for cod, tag in ((a, "A"), (b, "B")):
            fd = resolver.face_data(cod)
            if fd and fd.get("photo") and os.path.exists(fd["photo"]):
                shutil.copy2(fd["photo"], os.path.join(pdir, f"{tag}.jpg"))
            elif fd and fd.get("photos"):
                shutil.copy2(fd["photos"][0], os.path.join(pdir, f"{tag}.jpg"))

    # ordenar: match primero (por S), luego uncertain (por S)
    orden = {"match": 0, "uncertain": 1, "new": 2}
    resultados.sort(key=lambda r: (orden.get(r["verdict"], 3), -r["S"]))

    # volcado CSV
    csv_path = os.path.join(out_dir, f"reagrupar_{time.strftime('%Y%m%d_%H%M%S')}.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["a", "b", "s_face", "c_face", "c_zona", "S_fusion", "conf",
                    "verdict", "contaminada"])
        for r in resultados:
            w.writerow([r["a"], r["b"], f"{r['s_face']:.4f}", f"{r['c_face']:.3f}",
                        f"{r['c_zona']:.3f}", f"{r['S']:.4f}", f"{r['conf']:.3f}",
                        r["verdict"], "S" if r["contaminada"] else "N"])

    print(f"\n{'PAR':<28} {'nA':>3} {'nB':>3} {'s_cara':>7} {'c_cara':>6} {'c_zona':>6} "
          f"{'S_fus':>6}  VEREDICTO")
    print("-" * 82)
    for r in resultados:
        nA = store.count(r["a"]); nB = store.count(r["b"])
        marca = " *" if r["contaminada"] else ""
        print(f"{r['a'][:10]}~{r['b'][:10]:<17} {nA:>3} {nB:>3} {r['s_face']:>7.3f} "
              f"{r['c_face']:>6.2f} {r['c_zona']:>6.2f} {r['S']:>6.3f}  {r['verdict']}{marca}")

    m = sum(1 for r in resultados if r["verdict"] == "match" and not r["contaminada"])
    m_cont = sum(1 for r in resultados if r["verdict"] == "match" and r["contaminada"])
    u = sum(1 for r in resultados if r["verdict"] == "uncertain")
    print("-" * 82)
    print(f"RESUMEN: {m} pares superan umbrales con galerías coherentes (merge seguro), "
          f"{m_cont} match sobre galería contaminada (*, excluidos del auto-merge), "
          f"{u} inciertos (revisión)")
    if contaminadas:
        print(f"\nGALERÍAS CONTAMINADAS (coherencia < {min_coherence}) — candidatas a "
              f"limpiar_catchall, NO se fusionan:")
        for c in sorted(contaminadas):
            print(f"  {c}  media_intra={coh[c]:.3f}")
    print(f"\nminiaturas: {os.path.join(out_dir, 'pairs')}")
    print(f"CSV: {csv_path}")
    return resultados


def aplicar(ruta: str, local_id: str, cfg: Config, store: FaceStore,
            resultados: list[dict], force_contaminadas: bool = False) -> int:
    """Merge SOLO de los pares `match` con galerías coherentes (F6 reversible).

    Los pares `match` que involucran una galería contaminada (catch-all) se
    EXCLUYEN por defecto (van a limpiar_catchall); --force los incluye.
    """
    rows = _mysql(ruta, f"SELECT id, cod_interno FROM personas WHERE local_id={local_id}")
    pid_of = {r.split("\t")[1]: int(r.split("\t")[0]) for r in rows}

    before_counts = {"personas": count_personas(ruta), "estancias": count_estancias(ruta),
                     "store_persons": len(store.persons())}
    out_dir = new_backup_dir(ruta, "reagrupar")
    store.save_snapshot_bytes(os.path.join(out_dir, "face_enc_v2.bak"))
    snapshot_db(ruta, out_dir)
    journal = Journal(os.path.join(out_dir, "journal.jsonl"))
    write_manifest(out_dir, op="reagrupar", local_id=local_id, antes=before_counts)

    parent = {}
    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def union(a, b):
        parent[find(b)] = find(a)

    merges = [r for r in resultados
              if r["verdict"] == "match" and (force_contaminadas or not r["contaminada"])]
    merges.sort(key=lambda r: -r["S"])
    if force_contaminadas:
        print("[apply] --force: se incluyen los pares sobre galerías contaminadas")
    hechas = 0
    for r in merges:
        a, b = r["a"], r["b"]
        if find(a) == find(b):
            continue                      # ya unidas en esta pasada (evitar cadenas)
        if store.person(a) is None or store.person(b) is None:
            continue                      # una de las dos ya fue absorbida (enlace indirecto)
        # se queda la persona con más encodings
        if store.count(b) > store.count(a):
            a, b = b, a
        estancia_ids: list[int] = []
        if a in pid_of and b in pid_of:
            rows_e = _mysql(ruta, f"SELECT GROUP_CONCAT(id) FROM estancias WHERE persona_id={pid_of[b]}")
            val = rows_e[0].strip() if rows_e else ""
            # GROUP_CONCAT sin filas devuelve 'NULL' (no vacío): hay que ignorarlo
            if val and val != "NULL":
                estancia_ids = [int(x) for x in val.split(",")]
            _mysql(ruta, f"UPDATE estancias SET persona_id={pid_of[a]} WHERE persona_id={pid_of[b]}")
            _mysql(ruta, f"DELETE FROM personas WHERE id={pid_of[b]}")
            pid_of.pop(b)
        j = store.merge_undoable(a, b)
        journal.append({"op": "merge", "src": b, "dst": a,
                        "src_pid": pid_of.get(b), "dst_pid": pid_of.get(a),
                        "estancia_ids": estancia_ids,
                        "encodings_moved": j["encodings_moved"],
                        "snapshot": "face_enc_v2.bak", "db": "db_snapshot.sql",
                        "S": r["S"], "s_face": r["s_face"]})
        union(a, b)
        hechas += 1
        print(f"  merge {b[:10]} -> {a[:10]} (S={r['S']:.3f}, s_cara={r['s_face']:.3f}, "
              f"encs={j['encodings_moved']})")

    print(f"\n[apply] merges: {hechas} | personas face_enc_v2: {len(store.persons())}")
    print(f"[apply] snapshot + journal en {out_dir}")
    print(f"[apply] DESHACER: motor/venv/bin/python motor/reagrupar.py --local {local_id} "
          f"--ruta {ruta} --rollback {out_dir}")
    return hechas


def _rollback(ruta: str, backup_dir: str, local_id: str) -> int:
    db_sql = os.path.join(backup_dir, "db_snapshot.sql")
    store_bak = os.path.join(backup_dir, "face_enc_v2.bak")
    if not os.path.exists(db_sql) or not os.path.exists(store_bak):
        print(f"ERROR: faltan snapshots en {backup_dir}")
        return 1
    journal_path = os.path.join(backup_dir, "journal.jsonl")
    entries = Journal(journal_path).entries() if os.path.exists(journal_path) else []
    cfg = Config()
    store = FaceStore(os.path.join(ruta, "motor/bbdd_reconocimiento", local_id, "face_enc_v2"),
                      max_per_person=cfg.max_encodings_per_person)
    manifest = load_manifest(backup_dir)
    esperado = manifest.get("antes") or {"personas": None, "estancias": None, "store_persons": None}
    print(f"[rollback] {len(entries)} ops | estado esperado (pre-op): {esperado}")
    restore_db(ruta, db_sql)
    data = store.load_snapshot_bytes(store_bak)
    import pickle
    with open(os.path.join(ruta, "motor/bbdd_reconocimiento", local_id, "face_enc_v2"), "wb") as fh:
        pickle.dump(data, fh)
    print("[rollback] BD y face_enc_v2 restaurados")
    verify_restore(ruta, store, esperado, len(entries))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--local", default=1)
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--floor", type=float, default=None,
                    help="coseno mínimo para considerar un par candidato "
                         "(por defecto: match_threshold configurado)")
    ap.add_argument("--apply", action="store_true", help="fusionar SOLO los pares que superan los umbrales")
    ap.add_argument("--force", action="store_true",
                    help="con --apply: incluir también los pares sobre galerías contaminadas")
    ap.add_argument("--min-coherence", type=float, default=0.20,
                    help="media intra mínima para considerar una galería coherente")
    ap.add_argument("--rollback", metavar="DIR", default=None,
                    help="deshacer un apply previo (motor/backups/<ts>_reagrupar)")
    args = ap.parse_args()

    cfg = Config.from_env(args.ruta)
    if args.floor is None:
        args.floor = cfg.match_threshold

    if args.rollback:
        return _rollback(args.ruta, args.rollback, str(args.local))

    store = FaceStore(os.path.join(args.ruta, "motor/bbdd_reconocimiento", str(args.local), "face_enc_v2"),
                      max_per_person=cfg.max_encodings_per_person)
    out_dir = os.path.join(args.ruta, "motor/reagrupar_out", f"run_{time.strftime('%Y%m%d_%H%M%S')}")
    os.makedirs(out_dir, exist_ok=True)

    resultados = reporte(args.ruta, str(args.local), cfg, store, args.floor, out_dir,
                         min_coherence=args.min_coherence)

    if args.apply:
        n = aplicar(args.ruta, str(args.local), cfg, store, resultados,
                    force_contaminadas=args.force)
        print(f"\n[apply] total merges aplicados: {n}")
    else:
        print(f"\n[dry-run] no se aplicó nada. Usa --apply para fusionar los pares 'match'.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
