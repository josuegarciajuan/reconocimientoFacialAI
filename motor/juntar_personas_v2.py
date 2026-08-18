#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Une dos personas en face_enc_v2 (motor nuevo) — motor/juntar_personas_v2.py

Sustituye al legacy `juntar_personas.py` (que operaba sobre el diccionario antiguo
`face_enc` y dejaba el clasificador nuevo sin actualizar: al volver a clasificar,
la persona volvía a separarse).

Uso (invocado desde admin/pages/visitantes/acciones.php tras reasignar la BD):
    motor/venv/bin/python motor/juntar_personas_v2.py <local_id> <cod_original> <cod_copia> [--ruta .]

Acción:
  - Mueve todos los encodings de `cod_copia` a `cod_original` (FaceStore.merge_undoable)
    y elimina `cod_copia` del diccionario.
  - Emite etiqueta de feedback (F3, §5): el par (original, copia) es GENUINO — el
    panel "Unir" es la verdad de calibración.
  - Escribe journal de auditoría (F6) en motor/backups/<ts>_unir/ con snapshot.
  - NO toca la BD: la reasignación de estancias y el borrado de la persona la hace
    acciones.php (PDO), igual que con el script legacy.
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config      # noqa: E402
from motor.core.store import FaceStore    # noqa: E402
from motor.core.backup import Journal, new_backup_dir, write_manifest  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("cod_original")
    ap.add_argument("cod_copia")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    args = ap.parse_args()

    cfg = Config.from_env(args.ruta)
    store = FaceStore(os.path.join(args.ruta, "motor/bbdd_reconocimiento", args.local_id, "face_enc_v2"),
                      max_per_person=cfg.max_encodings_per_person)

    if args.cod_original == args.cod_copia:
        print("cod_original == cod_copia: noop")
        return 1

    # existe copia en el diccionario? (original puede no existir aún: se crea vacía)
    if store.person(args.cod_copia) is None:
        print(f"cod_copia {args.cod_copia} no está en face_enc_v2: noop")
        return 1

    n_antes = store.count(args.cod_original) + store.count(args.cod_copia)

    # F6: snapshot + journal (auditoría y reversibilidad)
    out_dir = new_backup_dir(args.ruta, "unir")
    store.save_snapshot_bytes(os.path.join(out_dir, "face_enc_v2.bak"))
    journal = Journal(os.path.join(out_dir, "journal.jsonl"))
    write_manifest(out_dir, op="unir", local_id=args.local_id,
                   src=args.cod_copia, dst=args.cod_original)

    j = store.merge_undoable(args.cod_original, args.cod_copia)
    journal.append({"op": "merge", "src": args.cod_copia, "dst": args.cod_original,
                    "encodings_moved": j["encodings_moved"],
                    "ts": time.time(), "snapshot": "face_enc_v2.bak"})

    # F3: feedback — el panel "Unir" etiqueta el par como GENUINO (calibración)
    if cfg.feedback_enabled:
        from motor.core.feedback import FeedbackCollector
        fc = FeedbackCollector(args.ruta, args.local_id, enabled=True)
        fc.label_merge(args.cod_original, args.cod_copia)

    n_despues = store.count(args.cod_original)
    print(f"ok (merge {args.cod_copia} -> {args.cod_original}; encodings {n_antes} -> {n_despues}; "
          f"cod_copia presente: {store.person(args.cod_copia) is not None})")
    print(f"journal: {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
