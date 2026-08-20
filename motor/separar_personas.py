#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Separa varias fotos de una persona y las lleva a otra (P4 — bulk con proveniencia).

Caso de uso: el clasificador metió caras de la persona B dentro de la galería de A
(contaminación). El operador selecciona en el panel las fotos intrusas y las mueve
a B (o a una persona nueva). Este script mueve en face_enc_v2 EXACTAMENTE los
encodings que aportaron esas fotos (move_by_source) — sin residuos en A y sin
adivinar por coseno — y emite la etiqueta de feedback impostor por cada foto.

La reasignación de BD (estancias/fotos, crear persona nueva si procede) la hace
acciones.php (PDO), igual que con "mover foto" individual.

Uso:
    motor/venv/bin/python motor/separar_personas.py <local_id> <cod_origen> <cod_destino> \
        --fotos id1,id2,... [--ruta .] [--min-cosine 0.45]

Salida: nº total de encodings movidos y desglose por foto (vía: source|cosine|reembed).
F6: snapshot + journal en motor/backups/<ts>_separar/ (rollback CLI: --rollback pendiente de fase "deshacer").
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.backup import Journal, new_backup_dir, write_manifest  # noqa: E402
from motor.core.config import Config                                   # noqa: E402
from motor.core.feedback import FeedbackCollector, embedding_hash      # noqa: E402
from motor.core.provenance import move_foto                            # noqa: E402
from motor.core.store import FaceStore                                 # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("cod_origen")
    ap.add_argument("cod_destino")
    ap.add_argument("--fotos", required=True, help="CSV de fotos.id a separar")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--min-cosine", type=float, default=0.45)
    args = ap.parse_args()

    foto_ids = [int(x) for x in args.fotos.split(",") if str(x).strip().isdigit()]
    if not foto_ids:
        print("sin fotos válidas")
        return 1
    if args.cod_origen == args.cod_destino:
        print("cod_origen == cod_destino: noop")
        return 1

    cfg = Config.from_env(args.ruta)
    store = FaceStore(os.path.join(args.ruta, "motor/bbdd_reconocimiento", args.local_id, "face_enc_v2"),
                      max_per_person=cfg.max_encodings_per_person)

    if store.person(args.cod_origen) is None:
        print(f"cod_origen {args.cod_origen} no está en face_enc_v2: noop")
        return 1

    # F6: snapshot + journal (auditoría y reversibilidad)
    out_dir = new_backup_dir(args.ruta, "separar")
    store.save_snapshot_bytes(os.path.join(out_dir, "face_enc_v2.bak"))
    journal = Journal(os.path.join(out_dir, "journal.jsonl"))
    write_manifest(out_dir, op="separar", local_id=args.local_id,
                   src=args.cod_origen, dst=args.cod_destino, fotos=foto_ids)

    total = 0
    detalle = []
    etiquetas = []
    for fid in foto_ids:
        res = move_foto(store, args.ruta, cfg, fid, args.cod_origen, args.cod_destino,
                        min_cosine=args.min_cosine)
        total += res["moved"]
        detalle.append({"foto": fid, "via": res["via"], "moved": res["moved"]})
        journal.append({"op": "move_foto", "foto": fid, "via": res["via"],
                        "moved": res["moved"], "ts": time.time(),
                        "snapshot": "face_enc_v2.bak"})
        if res["label_emb"] is not None:
            etiquetas.append(embedding_hash(res["label_emb"]))

    # F3: feedback — cada foto movida era IMPOSTOR de la persona origen
    if cfg.feedback_enabled and etiquetas:
        fc = FeedbackCollector(args.ruta, args.local_id, enabled=True)
        for h in etiquetas:
            fc.label_move(h, args.cod_origen)

    for d in detalle:
        print(f"  foto {d['foto']}: {d['moved']} encoding(s) vía {d['via']}")
    print(f"ok (total {total} encoding(s) de {args.cod_origen} -> {args.cod_destino})")
    print(f"journal: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
