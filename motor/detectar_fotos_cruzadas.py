#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Barrido global de fotos cruzadas — motor/detectar_fotos_cruzadas.py

Detecta fotos cuya CARA MOSTRADA no corresponde a la persona asignada en BD
(contaminación del tipo "2 caras en la misma foto": el match por embeddings era
correcto pero la foto que se guardó mostraba a otra persona).

Solo LECTURA: no corrige nada. Reporta para revisión manual; el operador aplica
"mover foto" (mover_foto_db + cambiar_foto.py) o borrado desde el panel.

Cómo funciona:
  1. Lee de BD (vía ws.php) foto_id + persona asignada (estancia) + cod_interno.
  2. Para cada foto del panel (admin/caras_procesadas/<foto_id>.jpg) detecta las
     caras y calcula sus embeddings (mismo modelo del motor).
  3. Compara contra face_enc_v2 del local:
       - score_persona_bd  = mejor coseno contra la galería de la persona asignada
       - mejor otro        = mejor coseno contra CUALQUIER otra persona
     Marca CRUZADA si: mejor_otro >= --min-cos  Y  mejor_otro - score_persona_bd >= --margin
     (el rostro mostrado pertenece claramente a otra persona).

Uso:
    motor/venv/bin/python motor/detectar_fotos_cruzadas.py <local_id> \
        [--ruta .] [--min-cos 0.45] [--margin 0.10] [--out reporte.txt]

Salida: tabla por consola + fichero de reporte (--out) + resumen.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config            # noqa: E402
from motor.core.model import analyze            # noqa: E402
from motor.core.store import FaceStore          # noqa: E402


def php_ws(ruta: str, *args) -> str:
    try:
        r = subprocess.run(["php", os.path.join(ruta, "ws.php"), *[str(a) for a in args]],
                           capture_output=True, text=True, timeout=60, cwd=ruta)
        return r.stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--min-cos", type=float, default=0.45,
                    help="mejor coseno contra otra persona para marcar cruzada")
    ap.add_argument("--margin", type=float, default=0.10,
                    help="ventaja mínima de la otra persona sobre la asignada")
    ap.add_argument("--limit", type=int, default=0,
                    help="limitar el nº de fotos a revisar (0 = todas)")
    ap.add_argument("--out", default="", help="fichero de reporte (opcional)")
    args = ap.parse_args()

    cfg = Config.from_env(args.ruta)
    store = FaceStore(os.path.join(args.ruta, "motor/bbdd_reconocimiento",
                                   args.local_id, "face_enc_v2"),
                      max_per_person=cfg.max_encodings_per_person)
    persons = store.persons()
    if not persons:
        print("face_enc_v2 vacío o sin personas: nada que revisar")
        return 0

    # galería completa en memoria UNA vez (store.person_encodings relee el pickle
    # por persona y por foto; aquí se evita ese cuello de botella).
    gallery: dict[str, np.ndarray] = {}
    for cod in persons:
        g = store.person_encodings(cod)
        if g is not None and len(g):
            gallery[cod] = np.asarray(g, dtype=np.float32)
    if not gallery:
        print("sin galerías en face_enc_v2")
        return 0

    def fast_scores(emb: np.ndarray) -> dict[str, float]:
        e = np.asarray(emb, dtype=np.float32)
        return {cod: float((g @ e).max()) for cod, g in gallery.items()}

    raw = php_ws(args.ruta, "listado_fotos_persona", args.local_id)
    try:
        fotos = json.loads(raw) if raw else []
    except json.JSONDecodeError:
        print(f"ws.php no devolvió JSON válido: {raw[:200]}")
        return 1
    if not fotos:
        print("sin fotos en BD para este local")
        return 0
    if args.limit > 0:
        fotos = fotos[:args.limit]

    rev_dir = os.path.join(args.ruta, "admin/caras_procesadas")
    cruzadas = []
    sin_cara = []
    revisadas = 0
    t0 = time.time()

    for n, row in enumerate(fotos, 1):
        fid = int(row["foto_id"])
        cod_bd = row.get("cod_interno")
        if cod_bd not in gallery:
            continue
        p = os.path.join(rev_dir, f"{fid}.jpg")
        if not os.path.exists(p):
            continue
        img = cv2.imread(p)
        if img is None:
            continue
        faces = analyze(img, det_size=(cfg.crop_det_size, cfg.crop_det_size),
                        min_score=cfg.min_det_score)
        if not faces:
            sin_cara.append(fid)
            continue
        revisadas += 1
        # mejor coseno del rostro más parecido contra cada persona
        mejor_persona = None
        mejor_score = -1.0
        score_bd = -1.0
        for f in faces:
            sc = fast_scores(f.embedding)
            for cod, s in sc.items():
                if s > mejor_score:
                    mejor_score, mejor_persona = s, cod
            score_bd = max(score_bd, sc.get(cod_bd, 0.0))
        if (mejor_persona != cod_bd and mejor_score >= args.min_cos
                and (mejor_score - score_bd) >= args.margin):
            cruzadas.append({
                "foto": fid, "camara": row.get("camara_id"), "persona_bd": cod_bd,
                "mejor": mejor_persona, "score_mejor": round(mejor_score, 3),
                "score_bd": round(score_bd, 3),
            })
        if n % 50 == 0:
            print(f"  ... {n}/{len(fotos)} revisadas "
                  f"({time.time() - t0:.0f}s, {len(cruzadas)} cruzadas)", flush=True)

    lines = []
    lines.append(f"Barrido fotos cruzadas local {args.local_id} "
                 f"(min-cos={args.min_cos}, margin={args.margin})")
    lines.append(f"  fotos revisadas: {revisadas} | sin cara detectada: {len(sin_cara)} "
                 f"| CRUZADAS: {len(cruzadas)}")
    if sin_cara:
        lines.append(f"  sin cara (revisar visualmente): {', '.join(map(str, sin_cara[:30]))}"
                     + ("..." if len(sin_cara) > 30 else ""))
    for c in cruzadas:
        lines.append(f"  foto {c['foto']} cam{c['camara']}: asignada a {c['persona_bd'][:10]} "
                     f"(score {c['score_bd']}) pero el rostro mostrado es de "
                     f"{c['mejor'][:10]} (score {c['score_mejor']})")
    report = "\n".join(lines)
    print(report)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(report + "\n")
        print(f"reporte: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
