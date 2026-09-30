#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Puente del pool para el avatar (M3 de SuperServer).

Lo lanza `libs/avatars.php` cuando el proyecto está en modo `superserver`:
envía la petición al spool, espera el PNG del nodo y aplica los MISMOS efectos
que `motor/avatar.py` en local:

  1. coloca el PNG en su ruta (atómico);
  2. escribe el sidecar `<png>.foto` con el id de la foto elegida.

El `.pid` que gestiona el PHP mantiene la semántica de "generando" (el bridge
vive hasta aplicado el resultado).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.photo_pool import RETURNS_DIR, escribir_peticion, modo  # noqa: E402

PROYECTO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def build_request(fotos: list[dict], out: str, size: int, rid: str | None = None) -> dict:
    rid = rid or f"req-{int(time.time())}-{os.getpid()}"
    return {
        "id": rid,
        "project": "reconocimientoFacial",
        "process": "avatar",
        "params": {"fotos": fotos, "out": out, "size": size},
        "externalId": f"avatar:{out}",
    }


def esperar_resultado(png_name: str, timeout_s: float, poll_s: float = 5.0) -> str | None:
    """Espera `result/<png>` + `result/chosen.txt` y devuelve el dir de resultado."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if os.path.isdir(RETURNS_DIR):
            for d in sorted(os.listdir(RETURNS_DIR)):
                root = os.path.join(RETURNS_DIR, d, "result")
                if os.path.isfile(os.path.join(root, png_name)) and os.path.isfile(os.path.join(root, "chosen.txt")):
                    return root
        time.sleep(poll_s)
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fotos-json", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--size", type=int, default=96)
    ap.add_argument("--timeout", type=float, default=900.0)
    args = ap.parse_args()

    try:
        with open(args.fotos_json, encoding="utf-8") as fh:
            fotos = json.load(fh)
    except (OSError, ValueError):
        print("[avatar-bridge] fotos-json inválido", flush=True)
        return 2
    if not fotos:
        return 2

    if modo() != "superserver":
        # Fallback defensivo: modo local clásico.
        fs = ";".join(f"{int(f['id'])}:{f['src']}" for f in fotos if f.get("id") and f.get("src"))
        return subprocess.call([sys.executable, os.path.join(PROYECTO, "motor", "avatar.py"),
                                "--fotos", fs, "--out", args.out])

    req = build_request(fotos, args.out, args.size)
    escribir_peticion(req)
    print(f"[avatar-bridge] petición {req['id']} para {req['externalId']}", flush=True)

    png_name = os.path.basename(args.out)
    root = esperar_resultado(png_name, args.timeout)
    if not root:
        print(f"[avatar-bridge] timeout esperando {png_name}", flush=True)
        return 1

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    tmp = args.out + ".tmp"
    shutil.copyfile(os.path.join(root, png_name), tmp)
    os.replace(tmp, args.out)
    try:
        with open(os.path.join(root, "chosen.txt"), encoding="utf-8") as fh:
            with open(args.out + ".foto", "w", encoding="utf-8") as out:
                out.write(fh.read().strip())
    except OSError:
        pass
    try:
        os.remove(args.fotos_json)
    except OSError:
        pass
    print(f"[avatar-bridge] aplicado {png_name} (+ sidecar .foto)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
