#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Puente del pool para `classify` (M3 de SuperServer) — split de embeddings.

Lo lanza `detector.php` (en modo `superserver`) en lugar de `clasificador.py`.
Para cada cámara del grupo:

  1. Envía los crops de `motor/caras/sinclasificar/<local>/<cam>/` al pool.
  2. Espera `faces.json` (detección + SR + embedding por crop).
  3. Ejecuta el `clasificador.py` LOCAL con `--once --faces-json <tmp>`: la casa
     decide y escribe la galería (único escritor); solo se evita `analyze` +
     `enhance_embedding` (lo pesado), que ya vino del pool.

Si el modo es `local`, ejecuta `clasificador.py` tal cual (sin cambios).

Uso (lo lanza detector.php; el token final de Jos_Thread se ignora):
    <venv>/python motor/clasificador_bridge.py <local> <cam[,cam2]> --ruta <RUTA> [TOKEN]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

MODE_FILE = "/var/lib/taildeck/projects/reconocimientoFacial.mode"
SPOOL_DIR = "/var/lib/taildeck/spool"
RETURNS_DIR = "/var/lib/taildeck/returns/reconocimientoFacial"
PROYECTO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IMG_EXTS = (".jpg", ".jpeg", ".png")


def modo() -> str:
    try:
        with open(MODE_FILE, encoding="utf-8") as fh:
            return "superserver" if fh.read().strip() == "superserver" else "local"
    except OSError:
        return "local"


def build_request(local_id: str, camara_id: str, crops: list[str], rid: str | None = None) -> dict:
    rid = rid or f"req-{int(time.time())}-{os.getpid()}"
    return {
        "id": rid,
        "project": "reconocimientoFacial",
        "process": "classify",
        "params": {"local": local_id, "cam": camara_id, "crops": crops},
        "externalId": f"classify:{local_id}/{camara_id}",
    }


def escribir_peticion(req: dict) -> str:
    os.makedirs(SPOOL_DIR, exist_ok=True)
    dst = os.path.join(SPOOL_DIR, f"{req['id']}.json")
    tmp = dst + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(req, fh, ensure_ascii=False)
    os.replace(tmp, dst)
    return dst


def _artifact_root(d: str) -> str:
    return os.path.join(d, "result") if os.path.isdir(os.path.join(d, "result")) else d


def _leer_faces(d: str, local_id: str, camara_id: str) -> dict | None:
    root = _artifact_root(d)
    f = os.path.join(root, "faces.json")
    if not os.path.exists(f):
        return None
    try:
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if str(data.get("local")) != str(local_id) or str(data.get("cam")) != str(camara_id):
        return None
    return data.get("faces") or {}


def esperar_faces(local_id: str, camara_id: str, timeout_s: float, poll_s: float = 5.0) -> dict | None:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if os.path.isdir(RETURNS_DIR):
            for d in sorted(os.listdir(RETURNS_DIR)):
                full = os.path.join(RETURNS_DIR, d)
                if not os.path.isdir(full):
                    continue
                faces = _leer_faces(full, local_id, camara_id)
                if faces is not None:
                    return faces
        time.sleep(poll_s)
    return None


def procesar_cam(local_id: str, camara_id: str, ruta: str, timeout: float, poll: float) -> int:
    dir_in = os.path.join(ruta, "motor/caras/sinclasificar", str(local_id), str(camara_id))
    if not os.path.isdir(dir_in):
        return 0
    crops = [os.path.join(dir_in, f) for f in sorted(os.listdir(dir_in))
             if f.lower().endswith(IMG_EXTS)]
    if not crops:
        return 0

    # Seguridad: solo ficheros dentro del árbol del proyecto.
    root_abs = os.path.abspath(ruta)
    crops = [os.path.abspath(c) for c in crops if os.path.abspath(c).startswith(root_abs + os.sep)]
    if not crops:
        return 0

    req = build_request(local_id, camara_id, crops)
    escribir_peticion(req)
    print(f"[classify-bridge] petición {req['id']} para {req['externalId']} ({len(crops)} crops)", flush=True)

    faces = esperar_faces(local_id, camara_id, timeout, poll)
    if faces is None:
        print(f"[classify-bridge] timeout esperando faces de {req['externalId']}", flush=True)
        return 0

    tmp = os.path.join(ruta, "motor/caras", f".faces_{local_id}_{camara_id}.json")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(faces, fh)
        cmd = [sys.executable, os.path.join(PROYECTO, "motor/clasificador.py"),
               str(local_id), str(camara_id), "--ruta", ruta, "--once", "--faces-json", tmp]
        rc = subprocess.call(cmd)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    print(f"[classify-bridge] {camara_id}: decisión local aplicada (rc={rc})", flush=True)
    return rc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("camara_id")
    ap.add_argument("token", nargs="?", default=None, help="token de Jos_Thread (se ignora)")
    ap.add_argument("--ruta", default=PROYECTO)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--timeout", type=float, default=3600.0)
    ap.add_argument("--poll", type=float, default=5.0)
    args = ap.parse_args()

    cameras = [c.strip() for c in str(args.camara_id).split(",") if c.strip()]

    if modo() != "superserver":
        cmd = [sys.executable, os.path.join(PROYECTO, "motor/clasificador.py"),
               args.local_id, args.camara_id, "--ruta", args.ruta]
        if args.once:
            cmd.append("--once")
        return subprocess.call(cmd)

    for cam in cameras:
        try:
            procesar_cam(args.local_id, cam, args.ruta, args.timeout, args.poll)
        except Exception as e:  # noqa: BLE001 — nunca rompe el bucle de cámaras
            print(f"[classify-bridge] error en cam {cam}: {e}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
