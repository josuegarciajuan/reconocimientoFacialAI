#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Actualiza face_enc_v2 al mover una foto entre personas (B4 + P4 proveniencia).

Sustituye al legacy `cambiar_foto_de_persona.py` (roto: NameError + corrompía `points`).

Uso:
    motor/venv/bin/python motor/cambiar_foto.py <local_id> <foto_id> <cod_origen> <cod_destino> [--ruta .] [--min-cosine 0.45]

Acción (motor/core/provenance.move_foto):
  1. Proveniencia exacta: si el encoding de esa foto (`fotos.identificador_unico`)
     está en la galería de origen, se mueven TODOS sus encodings al destino
     (sin re-embebido ni residuos).
  2. Fallback coseno: encodings legacy sin `sources` → re-embebe la foto y mueve
     los que casen >= min_cosine.
  3. Re-embed: si la cara ya no está en origen, se añade al destino.
  4. Emite etiqueta de feedback (F3, §5): la foto movida NO era de la persona
     origen -> par IMPOSTOR (verdad de calibración del panel).
  La reasignación de BD (estancias/fotos) la hace acciones.php (PDO).
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config                 # noqa: E402
from motor.core.provenance import move_foto          # noqa: E402
from motor.core.store import FaceStore               # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("foto_id")
    ap.add_argument("cod_origen")
    ap.add_argument("cod_destino")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--min-cosine", type=float, default=0.45)
    args = ap.parse_args()

    cfg = Config.from_env(args.ruta)   # F3: carga .env (feedback_enabled y VLM consistentes)
    store = FaceStore(os.path.join(args.ruta, "motor/bbdd_reconocimiento", args.local_id, "face_enc_v2"),
                      max_per_person=cfg.max_encodings_per_person)

    res = move_foto(store, args.ruta, cfg, args.foto_id,
                    args.cod_origen, args.cod_destino, min_cosine=args.min_cosine)

    # F3: feedback — la foto movida era IMPOSTOR de la persona origen
    if cfg.feedback_enabled and res["label_emb"] is not None:
        from motor.core.feedback import FeedbackCollector, embedding_hash
        fc = FeedbackCollector(args.ruta, args.local_id, enabled=True)
        fc.label_move(embedding_hash(res["label_emb"]), args.cod_origen)

    print(f"ok (movidos {res['moved']} encoding(s) vía {res['via']} de "
          f"{args.cod_origen} -> {args.cod_destino})")
    return 0 if res["moved"] else 1


if __name__ == "__main__":
    sys.exit(main())
