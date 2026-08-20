#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Une dos personas en face_enc_v2 + BD (motor nuevo) — motor/juntar_personas_v2.py

Sustituye al legacy `juntar_personas.py` (operaba sobre el diccionario antiguo
`face_enc` y dejaba el clasificador nuevo sin actualizar).

Uso (invocado desde admin/pages/visitantes/acciones.php tras validar la petición):
    motor/venv/bin/python motor/juntar_personas_v2.py <local_id> <cod_original> <cod_copia> [--ruta .]

Acción (P5: ÚNICA transacción BD + galería, síncrona):
  - F6: snapshot (face_enc_v2.bak + db_snapshot.sql) + journal en motor/backups/<ts>_unir/.
  - Mueve todos los encodings de `cod_copia` a `cod_original` (FaceStore.merge_undoable,
    conservando la proveniencia `sources` de cada cara — P5).
  - Reasigna la BD: UPDATE estancias SET persona_id = <original> WHERE persona_id = <copia>;
    DELETE FROM personas WHERE id = <copia>. (Antes lo hacía acciones.php en PHP con una
    ventana inconsistente; ahora la BD y la galería quedan en el MISMO estado.)
  - Emite etiqueta de feedback (F3, §5): el par (original, copia) es GENUINO — el
    panel "Unir" es la verdad de calibración.

El orden importa: primero se valida que AMBAS personas existen (BD), luego snapshot,
luego merge de galería y reasignación de BD; si algo falla a mitad, el snapshot+journal
permiten restaurar (F6).
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.backup import (Journal, count_estancias, count_personas,  # noqa: E402
                               _mysql, new_backup_dir, snapshot_db,
                               write_manifest)
from motor.core.config import Config      # noqa: E402
from motor.core.store import FaceStore    # noqa: E402


def esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace("'", "\\'")


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

    # validar AMBAS personas en BD antes de tocar nada (la galería puede no tener copia)
    rows_o = _mysql(args.ruta, f"SELECT id FROM personas WHERE cod_interno='{esc(args.cod_original)}' LIMIT 1")
    rows_c = _mysql(args.ruta, f"SELECT id FROM personas WHERE cod_interno='{esc(args.cod_copia)}' LIMIT 1")
    if not rows_c:
        print(f"cod_copia {args.cod_copia} no existe en personas: noop")
        return 1
    pid_o = int(rows_o[0]) if rows_o else 0
    pid_c = int(rows_c[0])
    if pid_o == 0 or pid_o == pid_c:
        print(f"original {args.cod_original} no válido en personas: noop")
        return 1

    if store.person(args.cod_copia) is None:
        print(f"cod_copia {args.cod_copia} no está en face_enc_v2 (BD sí): noop de galería")
        return 1

    n_antes = store.count(args.cod_original) + store.count(args.cod_copia)
    antes = {"personas": count_personas(args.ruta),
             "estancias": count_estancias(args.ruta),
             "store_persons": len(store.persons())}

    # F6: snapshot (store + BD) y journal antes de mutar
    out_dir = new_backup_dir(args.ruta, "unir")
    store.save_snapshot_bytes(os.path.join(out_dir, "face_enc_v2.bak"))
    snapshot_db(args.ruta, out_dir)
    journal = Journal(os.path.join(out_dir, "journal.jsonl"))
    write_manifest(out_dir, op="unir", local_id=args.local_id,
                   src=args.cod_copia, dst=args.cod_original, antes=antes)

    # 1) galería: fusiona TODOS los encodings (y sus `sources`) en el original
    j = store.merge_undoable(args.cod_original, args.cod_copia)
    journal.append({"op": "merge", "src": args.cod_copia, "dst": args.cod_original,
                    "encodings_moved": j["encodings_moved"], "ts": time.time(),
                    "snapshot": "face_enc_v2.bak"})

    # 2) BD: reasignar estancias y borrar la persona copia
    _mysql(args.ruta, f"UPDATE estancias SET persona_id={pid_o} WHERE persona_id={pid_c}")
    _mysql(args.ruta, f"DELETE FROM personas WHERE id={pid_c}")
    journal.append({"op": "db_reassign", "src_pid": pid_c, "dst_pid": pid_o,
                    "ts": time.time(), "db": "db_snapshot.sql"})

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
