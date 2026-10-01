#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Puente del pool para `archiva_video` (M3 de SuperServer).

Lo lanza `detector.php` por vídeo cuando el proyecto está en modo `superserver`,
con la MISMA vida/marcador que el `archiva_video.py` clásico (el detector lo
vigila con `aux/archiva_<fichero>.txt` + `pgrep`). Hace:

  1. Deja una petición `archive` en el spool de SuperServer.
  2. Espera el MP4+poster del pool.
  3. Aplica EXACTAMENTE los efectos del proceso clásico: coloca el MP4 y el
     poster en `motor/videos_archivo/…`, registra el vídeo con
     `ws.php guardar_video` y borra el marker. NO borra el origen (igual que el
     proceso clásico sin `--borrar`).

Si el modo es `local` (o el flag no existe), ejecuta `archiva_video.py` tal cual.

Uso (lo lanza detector.php):
    <venv>/python motor/archiva_video_bridge.py <local> <cam> <fichero> \
        --ruta <RUTA_PROYECTO> --crf 20 --fps 10 --preset medium \
        [--tag "<pg-tag>"] [--timeout 3600]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.archiva_video import PROYECTO, fecha_base_video, php_ws  # noqa: E402
from motor.pool_ack import escribir_ack, job_dir_of               # noqa: E402
from motor.core.video import ruta_archivo, ruta_video  # noqa: E402

MODE_FILE = "/var/lib/taildeck/projects/reconocimientoFacial.mode"
SPOOL_DIR = "/var/lib/taildeck/spool"
RETURNS_DIR = "/var/lib/taildeck/returns/reconocimientoFacial"


def modo() -> str:
    try:
        with open(MODE_FILE, encoding="utf-8") as fh:
            return "superserver" if fh.read().strip() == "superserver" else "local"
    except OSError:
        return "local"


def nombre_mp4(fichero: str) -> str:
    return os.path.splitext(fichero)[0] + ".mp4"


def build_request(local_id: str, camara_id: str, fichero: str,
                  crf: int, fps: int, preset: str, rid: str | None = None) -> dict:
    rid = rid or f"req-{int(time.time())}-{os.getpid()}"
    return {
        "id": rid,
        "project": "reconocimientoFacial",
        "process": "archive",
        "params": {"local": local_id, "cam": camara_id, "fichero": fichero,
                   "crf": crf, "fps": fps, "preset": preset, "name": nombre_mp4(fichero)},
        "externalId": f"archive:{local_id}/{camara_id}/{fichero}",
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
    f = os.path.join(root, "archive.json")
    if not os.path.exists(f):
        return None
    try:
        with open(f, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def esperar_resultado(local_id: str, camara_id: str, name: str,
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
                        and meta.get("name") == name):
                    return full, meta
        time.sleep(poll_s)
    return None


def aplicar(result_dir: str, meta: dict, local_id: str, camara_id: str, fichero: str,
            ruta: str) -> None:
    root = _artifact_root(result_dir)
    name = str(meta.get("name") or nombre_mp4(fichero))

    # 1) Coloca el MP4 archivado en su ruta final.
    dst_mp4 = ruta_archivo(ruta, local_id, camara_id, name)
    src_mp4 = os.path.join(root, str(meta.get("rel") or ""))
    if not os.path.isfile(src_mp4):
        src_mp4 = os.path.join(root, "motor/videos_archivo", str(local_id), str(camara_id), name)
    if not os.path.isfile(src_mp4):
        raise FileNotFoundError(f"MP4 del pool no encontrado para {name}")
    os.makedirs(os.path.dirname(dst_mp4), exist_ok=True)
    shutil.move(src_mp4, dst_mp4)

    rel = os.path.relpath(dst_mp4, ruta).replace(os.sep, "/")
    if ruta_video(rel, ruta) is None:
        raise ValueError(f"ruta fuera del árbol de archivo: {rel}")

    # 2) Poster (miniatura) junto al MP4.
    poster_rel = ""
    poster_rel_pool = str(meta.get("poster_rel") or "")
    if poster_rel_pool:
        src_jpg = os.path.join(root, poster_rel_pool)
        if os.path.isfile(src_jpg):
            dst_jpg = os.path.join(ruta, poster_rel_pool)
            os.makedirs(os.path.dirname(dst_jpg), exist_ok=True)
            shutil.move(src_jpg, dst_jpg)
            if ruta_video(poster_rel_pool, ruta) is not None:
                poster_rel = poster_rel_pool

    # 3) Registro en BD (mismo ws.php que el proceso clásico).
    duracion = float(meta.get("duracion") or 0.0)
    fecha_ini = fecha_base_video(fichero) or datetime.now()
    fecha_fin = fecha_ini + timedelta(seconds=duracion)
    video_id = php_ws("guardar_video", local_id, camara_id, name, rel,
                      fecha_ini.strftime("%Y-%m-%d %H:%M:%S"),
                      fecha_fin.strftime("%Y-%m-%d %H:%M:%S"),
                      str(duracion), str(meta.get("peso") or 0), str(meta.get("fps") or 0),
                      str(meta.get("ancho") or 0), str(meta.get("alto") or 0), poster_rel)
    if not video_id or not str(video_id).isdigit():
        raise RuntimeError(f"registro en BD fallido para {dst_mp4} (respuesta: {video_id!r})")

    # 4) Marker de archivado (igual que el proceso clásico). El origen NO se borra.
    marker = os.path.join(ruta, "aux", "archiva_" + fichero + ".txt")
    if os.path.exists(marker):
        os.remove(marker)

    try:
        with open(os.path.join(result_dir, ".aplicado"), "w", encoding="utf-8") as fh:
            fh.write(str(time.time()))
    except OSError:
        pass

    print(f"[archive-bridge] aplicado {local_id}/{camara_id} {fichero}: "
          f"id={video_id} {meta.get('peso')}B poster={poster_rel!r}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("camara_id")
    ap.add_argument("fichero")
    ap.add_argument("--ruta", default=PROYECTO)
    ap.add_argument("--crf", type=int, default=None)
    ap.add_argument("--fps", type=int, default=None)
    ap.add_argument("--preset", default=None)
    ap.add_argument("--tag", default="", help="texto extra en la cmdline para que pgrep lo vea vivo")
    ap.add_argument("--timeout", type=float, default=3600.0)
    ap.add_argument("--poll", type=float, default=5.0)
    args = ap.parse_args()

    if modo() != "superserver":
        cmd = [sys.executable, os.path.join(PROYECTO, "motor/archiva_video.py"),
               args.local_id, args.camara_id, args.fichero, "--ruta", args.ruta]
        for flag, val in (("--crf", args.crf), ("--fps", args.fps), ("--preset", args.preset)):
            if val is not None:
                cmd += [flag, str(val)]
        return subprocess.call(cmd)

    from motor.core.video import VideoConfig
    cfg = VideoConfig()
    crf = args.crf if args.crf is not None else cfg.crf
    fps = args.fps if args.fps is not None else cfg.fps
    preset = args.preset if args.preset is not None else cfg.preset

    req = build_request(args.local_id, args.camara_id, args.fichero, crf, fps, preset)
    escribir_peticion(req)
    print(f"[archive-bridge] petición {req['id']} para {req['externalId']}", flush=True)

    got = esperar_resultado(args.local_id, args.camara_id, nombre_mp4(args.fichero),
                            args.timeout, args.poll)
    if not got:
        print(f"[archive-bridge] timeout esperando el resultado de {req['externalId']}", flush=True)
        return 1
    result_dir, meta = got
    aplicar(result_dir, meta, args.local_id, args.camara_id, args.fichero, args.ruta)
    escribir_ack(job_dir_of(result_dir), source="archiva_video_bridge")
    return 0


if __name__ == "__main__":
    sys.exit(main())
