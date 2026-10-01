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


def buscar_resultado(local_id: str, camara_id: str, fichero: str) -> tuple[str, dict] | None:
    """Escanea UNA vez los retornos y devuelve (dir, meta) si el resultado ya está."""
    if not os.path.isdir(RETURNS_DIR):
        return None
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


def recolectar_pendientes(ruta: str, locales: list[str], force: bool) -> list[tuple[str, str, str]]:
    """Lista (local, cam, fichero) de vídeos archivados sin marca (o todos si force)."""
    pend: list[tuple[str, str, str]] = []
    for loc in locales:
        base = os.path.join(ruta, "motor/videos_archivo", str(loc))
        if not os.path.isdir(base):
            continue
        for cam in sorted(os.listdir(base)):
            cdir = os.path.join(base, cam)
            if not os.path.isdir(cdir):
                continue
            for fichero in sorted(os.listdir(cdir)):
                if not fichero.lower().endswith(".mp4"):
                    continue
                if not force and os.path.exists(marcador(ruta, loc, cam, fichero)):
                    continue
                pend.append((str(loc), cam, fichero))
    return pend


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id", nargs="?", default=None)
    ap.add_argument("--ruta", default=PROYECTO)
    ap.add_argument("--face-every", type=int, default=2)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--todos", action="store_true")
    ap.add_argument("--parallel", type=int, default=6, help="jobs rescan en vuelo (4-8)")
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

    n_par = max(1, min(int(args.parallel), 16))
    pendientes = recolectar_pendientes(args.ruta, locales, args.force)
    print(f"[rescan-bridge] pendientes={len(pendientes)} parallel={n_par}", flush=True)

    # Bounded concurrency: en vuelo = {req_id: (loc, cam, fichero, t0)}.
    en_vuelo: dict[str, tuple[str, str, str, float]] = {}
    total_caras = 0
    total_videos = 0
    idx = 0

    while idx < len(pendientes) or en_vuelo:
        while idx < len(pendientes) and len(en_vuelo) < n_par:
            loc, cam, fichero = pendientes[idx]
            idx += 1
            req = build_request(loc, cam, fichero, args.face_every)
            escribir_peticion(req)
            en_vuelo[req["id"]] = (loc, cam, fichero, time.time())

        progreso = False
        for rid, (loc, cam, fichero, t0) in list(en_vuelo.items()):
            got = buscar_resultado(loc, cam, fichero)
            if got:
                result_dir, meta = got
                ficheros = aplicar(result_dir, loc, cam, fichero, args.ruta)
                escribir_marcador(args.ruta, loc, cam, fichero)
                caras = int(meta.get("caras") or 0)
                total_caras += caras
                total_videos += 1
                del en_vuelo[rid]
                progreso = True
                print(f"[rescan-bridge] {cam}/{fichero}: {caras} caras ({ficheros} ficheros)", flush=True)
            elif time.time() - t0 > args.timeout:
                print(f"[rescan-bridge] timeout en {loc}/{cam}/{fichero}", flush=True)
                del en_vuelo[rid]
                progreso = True

        if not progreso and (en_vuelo or idx < len(pendientes)):
            time.sleep(args.poll)

    print(f"[rescan-bridge] vídeos re-escaneados: {total_videos} | caras re-extraídas: {total_caras}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
