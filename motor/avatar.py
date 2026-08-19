#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Genera el avatar (cabeza recortada con fondo transparente) de una persona.

Uso:
    motor/venv/bin/python motor/avatar.py --foto <foto_id> --src <jpg> --out <png> [--size 96]
    motor/venv/bin/python motor/avatar.py --fotos "id1:ruta1;id2:ruta2" --out <png> [--size 96]

Modo --fotos: elige automáticamente la mejor cara frontal (motor/core/avatar.best_frontal)
y escribe `generado <foto_id>` en stdout (el llamador PHP lo guarda en personas_avatar).

No toca la BD: el llamador (PHP) pasa las rutas explícitamente.
"""
from __future__ import annotations

import argparse
import os
import sys

import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.avatar import best_frontal, generar_avatar  # noqa: E402


def _parse_fotos(raw: str) -> list[tuple[int, str]]:
    """'id1:ruta1;id2:ruta2' -> [(id1, ruta1), ...] (rutas con ':' raro se unen)."""
    out = []
    for parte in raw.split(";"):
        parte = parte.strip()
        if not parte:
            continue
        if ":" not in parte:
            continue
        fid_s, _, ruta = parte.partition(":")
        try:
            out.append((int(fid_s), ruta))
        except ValueError:
            continue
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Avatar de persona (cabeza transparente)")
    ap.add_argument("--foto", type=int, default=0, help="foto concreta a usar")
    ap.add_argument("--src", default="", help="ruta del jpg de la foto (con --foto)")
    ap.add_argument("--fotos", default="", help="'id:ruta;id:ruta' para elegir la mejor frontal")
    ap.add_argument("--out", required=True, help="ruta de salida del PNG")
    ap.add_argument("--size", type=int, default=96, help="lado del PNG (px)")
    args = ap.parse_args()

    if args.size < 32 or args.size > 512:
        print("size fuera de rango")
        return 1

    if args.foto > 0:
        if not args.src or not os.path.exists(args.src):
            print("src no encontrada")
            return 1
        ruta = generar_avatar(args.foto, args.src, args.out, out_size=args.size)
        if not ruta:
            print("no se pudo generar el avatar")
            return 1
        print(f"generado {args.foto}")
        return 0

    if args.fotos:
        fotos = _parse_fotos(args.fotos)
        if not fotos:
            print("fotos inválidas")
            return 1
        elegida = best_frontal(fotos)
        if elegida is None:
            # Sin cara detectable en ninguna: usar la primera foto legible.
            for fid, ruta in fotos:
                img = cv2.imread(ruta)
                if img is not None:
                    elegida = fid
                    break
        if elegida is None:
            print("sin fotos legibles")
            return 1
        ruta_foto = dict(fotos)[elegida]
        ruta = generar_avatar(elegida, ruta_foto, args.out, out_size=args.size)
        if not ruta:
            print("no se pudo generar el avatar")
            return 1
        print(f"generado {elegida}")
        return 0

    print("usa --foto/--src o --fotos")
    return 1


if __name__ == "__main__":
    sys.exit(main())
