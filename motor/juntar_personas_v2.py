#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Une dos personas en face_enc_v2 (motor nuevo) — motor/juntar_personas_v2.py

Sustituye al legacy `juntar_personas.py` (que operaba sobre el diccionario antiguo
`face_enc` y dejaba el clasificador nuevo sin actualizar: al volver a clasificar,
la persona volvía a separarse).

Uso (invocado desde admin/pages/visitantes/acciones.php tras reasignar la BD):
    motor/venv/bin/python motor/juntar_personas_v2.py <local_id> <cod_original> <cod_copia> [--ruta .]

Acción:
  - Mueve todos los encodings de `cod_copia` a `cod_original` (FaceStore.merge)
    y elimina `cod_copia` del diccionario.
  - NO toca la BD: la reasignación de estancias y el borrado de la persona la hace
    acciones.php (PDO), igual que con el script legacy.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config      # noqa: E402
from motor.core.store import FaceStore    # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("cod_original")
    ap.add_argument("cod_copia")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    args = ap.parse_args()

    cfg = Config()
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
    store.merge(args.cod_original, args.cod_copia)
    n_despues = store.count(args.cod_original)
    print(f"ok (merge {args.cod_copia} -> {args.cod_original}; encodings {n_antes} -> {n_despues}; "
          f"cod_copia presente: {store.person(args.cod_copia) is not None})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
