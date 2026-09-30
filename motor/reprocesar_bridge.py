#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Puente del pool para `reprocesar.py --videos` (M3 de SuperServer).

Orquesta el re-escaneo nocturno delegando CADA vídeo archivado al pool y
aplicando los mismos efectos que el proceso clásico: mueve los crops a
`motor/caras/sinclasificar/…` y escribe el marker idempotente
`motor/reprocesado/<local>/<cam>/<fichero>.done`. NO toca la BD ni borra nada.

`--fotos` y `--galeria` NO se delegan (se quedan en la casa): este bridge solo
cubre el trabajo de `--videos`.

Si el modo es `local`, ejecuta `reprocesar.py --videos` tal cual.

Uso:
    <venv>/python motor/reprocesar_bridge.py [local_id] --ruta <RUTA_PROYECTO> \
        [--todos] [--face-every 2] [--force] [--timeout 7200]
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

from motor.reprocesar import _locales_disponibles          # noqa: E402

MODE_FILE = "/var/lib/taildeck/projects/reconocimientoFacial.mode"
SPOOL_DIR = "/var/lib/taildeck/spool"
RETURNS_DIR = "/var/lib/taildeck/returns/reconocimientoFacial"
PROYECTO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SUFIJOS = ("", "_busto", "_cuerpo")


def modo() -> str:
    try:
        with open(MODE_FILE, encoding="utf-8") as fh:
            return "superserver" if fh.read().strip() == "superserver" else "local"
    except OSError:
        return "local"


def build_request(local_id: str, camara_id: str, fichero: str, face_every: int,
                  rid: str | None = None) -> dict:
    rid = rid or f"req-{int(time.time())}-{os.getpid()}"
    return {
        "id": rid,
        "project": "reconocimientoFacial",
        "process": "rescan",
        "params": {"local": local_id, "cam": camara_id, "fichero": fichero,
                   "face_every": face_every},
        "externalId": f"rescan:{local_id}/{camara_id}/{fichero}",
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


def _leer_meta(d: str) -> dict | None:
    if os.path.exists(os.path.join(d, ".aplicado")):
        return None
    root = _artifact_root(d)
    f = os.path.join(root, "reprocesar.json")
    if not os.path.exists(f):
        return None
    try:
        with open(f, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def esperar_resultado(local_id: str, camara_id: str, fichero: str,
                      timeout_s: float, poll_s: float = 5.0) -> tuple[str, dict] | None:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if os.path.isdir(RETURNS_DIR):
            for d in sorted(os.listdir(RETURNS_DIR)):
                full = os.path.join(RETURNS_DIR, d)
                if not os.path.isdir(full):
                    continue
                meta = _leer_meta(full)
                if not meta:
                    continue
                if (str(meta.get("local")) == str(local_id) and str(meta.get("cam")) == str(camara_id)
                        and meta.get("fichero") == fichero):
                    return full, meta
        time.sleep(poll_s)
    return None


def _mover_archivos(src_dir: str, dst_dir: str) -> int:
    n = 0
    if not os.path.isdir(src_dir):
        return 0
    for root, _dirs, files in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        target = dst_dir if rel == "." else os.path.join(dst_dir, rel)
        os.makedirs(target, exist_ok=True)
        for f in files:
            shutil.move(os.path.join(root, f), os.path.join(target, f))
            n += 1
    return n


def aplicar(result_dir: str, local_id: str, camara_id: str, fichero: str, ruta: str) -> int:
    root = _artifact_root(result_dir)
    caras = 0
    for sufijo in SUFIJOS:
        src = os.path.join(root, "motor/caras/sinclasificar", str(local_id), f"{camara_id}{sufijo}")
        dst = os.path.join(ruta, "motor/caras/sinclasificar", str(local_id), f"{camara_id}{sufijo}")
        caras += _mover_archivos(src, dst)
    try:
        with open(os.path.join(result_dir, ".aplicado"), "w", encoding="utf-8") as fh:
            fh.write(str(time.time()))
    except OSError:
        pass
    return caras


def marcador(ruta: str, local_id: str, camara_id: str, fichero: str) -> str:
    return os.path.join(ruta, "motor/reprocesado", str(local_id), str(camara_id), fichero + ".done")


def escribir_marcador(ruta: str, local_id: str, camara_id: str, fichero: str) -> None:
    m = marcador(ruta, local_id, camara_id, fichero)
    try:
        os.makedirs(os.path.dirname(m), exist_ok=True)
        with open(m, "w", encoding="utf-8") as fh:
            fh.write(str(time.time()) + "\n")
    except OSError:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id", nargs="?", default=None)
    ap.add_argument("--ruta", default=PROYECTO)
    ap.add_argument("--face-every", type=int, default=2)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--timeout", type=float, default=7200.0)
    ap.add_argument("--poll", type=float, default=5.0)
    args = ap.parse_args()

    if modo() != "superserver":
        cmd = [sys.executable, os.path.join(PROYECTO, "motor/reprocesar.py")]
        if args.local_id:
            cmd.append(args.local_id)
        cmd += ["--ruta", args.ruta, "--videos", "--face-every", str(args.face_every)]
        if args.force:
            cmd.append("--force")
        if args.todos:
            cmd.append("--todos")
        return subprocess.call(cmd)

    locales = _locales_disponibles(args.ruta) if args.todos else ([args.local_id] if args.local_id else [])
    if not locales:
        print("[rescan-bridge] sin locales con vídeos archivados", flush=True)
        return 0

    total = 0
    for loc in locales:
        base = os.path.join(args.ruta, "motor/videos_archivo", str(loc))
        if not os.path.isdir(base):
            continue
        for cam in sorted(os.listdir(base)):
            cdir = os.path.join(base, cam)
            if not os.path.isdir(cdir):
                continue
            for fichero in sorted(os.listdir(cdir)):
                if not fichero.lower().endswith(".mp4"):
                    continue
                if os.path.exists(marcador(args.ruta, loc, cam, fichero)) and not args.force:
                    continue
                req = build_request(loc, cam, fichero, args.face_every)
                escribir_peticion(req)
                got = esperar_resultado(loc, cam, fichero, args.timeout, args.poll)
                if not got:
                    print(f"[rescan-bridge] timeout en {req['externalId']}", flush=True)
                    continue
                result_dir, meta = got
                ficheros = aplicar(result_dir, loc, cam, fichero, args.ruta)
                escribir_marcador(args.ruta, loc, cam, fichero)
                caras = int(meta.get("caras") or 0)
                total += caras
                print(f"[rescan-bridge] {cam}/{fichero}: {caras} caras ({ficheros} ficheros)", flush=True)
    print(f"[rescan-bridge] caras re-extraídas: {total}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
