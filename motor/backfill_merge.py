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
  # aplicar
  motor/venv/bin/python motor/backfill_merge.py 1 --ruta /root/reconocimientoFacial --apply
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
    args = ap.parse_args()

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

    # 4. aplicar
    rows = _mysql(args.ruta, f"SELECT id, cod_interno FROM personas WHERE local_id={args.local_id}")
    pid_of = {r.split("\t")[1]: int(r.split("\t")[0]) for r in rows}

    fusiones = 0
    for media, g in candidatos:
        n_enc = {c: len(emb_cache[c]) for c in g}
        keep = max(g, key=lambda c: n_enc[c])
        for c in g:
            if c == keep:
                continue
            if keep in pid_of and c in pid_of:
                _mysql(args.ruta, f"UPDATE estancias SET persona_id={pid_of[keep]} WHERE persona_id={pid_of[c]}")
                _mysql(args.ruta, f"DELETE FROM personas WHERE id={pid_of[c]}")
                pid_of.pop(c)
            store.merge(keep, c)
            fusiones += 1

    print(f"\n[apply] fusiones: {fusiones} | personas finales face_enc_v2: {len(store.persons())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
