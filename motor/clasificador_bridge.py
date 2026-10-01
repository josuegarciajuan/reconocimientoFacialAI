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
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.pool_ack import escribir_ack, job_dir_of, fingerprint  # noqa: E402

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


def _batch_id(nombres: list[str]) -> str:
    """Id estable del lote a partir de sus ficheros (mismo contenido → mismo id)."""
    h = hashlib.sha1("\n".join(nombres).encode("utf-8", "replace")).hexdigest()
    return h[:12]


def build_request(local_id: str, camara_id: str, carpeta: str,
                  batch_id: str | None = None,
                  fingerprint_val: str | None = None, rid: str | None = None) -> dict:
    rid = rid or f"req-{int(time.time())}-{os.getpid()}"
    ext = f"classify:{local_id}/{camara_id}" + (f"/{batch_id}" if batch_id else "")
    return {
        "id": rid,
        "project": "reconocimientoFacial",
        "process": "classify",
        "params": {"local": local_id, "cam": camara_id, "dir": carpeta, "batch": batch_id},
        "externalId": ext,
        "fingerprint": fingerprint_val,
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


def _leer_faces(d: str, local_id: str, camara_id: str, batch_id: str | None) -> dict | None:
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
    if batch_id is not None and data.get("batch") != batch_id:
        return None
    return data.get("faces") or {}


def esperar_faces(local_id: str, camara_id: str, batch_id: str | None,
                  timeout_s: float, poll_s: float = 5.0):
    """Espera el faces.json del LOTE y devuelve (faces, job_dir) o None."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if os.path.isdir(RETURNS_DIR):
            for d in sorted(os.listdir(RETURNS_DIR)):
                full = os.path.join(RETURNS_DIR, d)
                if not os.path.isdir(full):
                    continue
                faces = _leer_faces(full, local_id, camara_id, batch_id)
                if faces is not None:
                    return faces, full
        time.sleep(poll_s)
    return None


def _rmtree(path: str) -> None:
    try:
        shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass


def _aplicar_local(ruta: str, local_id, camara_id, batch_id: str, faces: dict, timeout: float) -> int:
    """Aplica el lote con el aplicador persistente si está vivo; si no, `--once`."""
    try:
        from motor import clasificador_queue as q
        if q.daemon_alive(ruta, local_id):
            if q.write_request(ruta, local_id, batch_id, camara_id, faces):
                got = q.esperar_done(ruta, local_id, batch_id, timeout)
                if got is not None:
                    return int(got.get("rc") or 0)
                print("[classify-bridge] timeout del aplicador; fallback a --once", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[classify-bridge] aplicador persistente no disponible: {e}", flush=True)

    tmp = os.path.join(ruta, "motor/caras", f".faces_{local_id}_{camara_id}_{batch_id}.json")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(faces, fh)
        cmd = [sys.executable, os.path.join(PROYECTO, "motor/clasificador.py"),
               str(local_id), str(camara_id), "--ruta", ruta, "--once", "--faces-json", tmp]
        return subprocess.call(cmd)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _procesar_lote(local_id: str, camara_id: str, ruta: str, dir_in: str,
                   chunk: list[str], timeout: float, poll: float) -> bool:
    """Prepara el lote (enlaces), lo delega y aplica la decisión local. True si ok."""
    batch_id = _batch_id(chunk)
    bdir = os.path.join(ruta, "motor/caras", f".batch_{local_id}_{camara_id}_{batch_id}")
    _rmtree(bdir)
    os.makedirs(bdir, exist_ok=True)
    for f in chunk:
        src = os.path.join(dir_in, f)
        try:
            os.link(src, os.path.join(bdir, f))       # sin copiar contenido
        except OSError:
            shutil.copy2(src, os.path.join(bdir, f))
    req = build_request(local_id, camara_id, bdir, batch_id=batch_id,
                        fingerprint_val=fingerprint([os.path.join(bdir, f) for f in chunk]))
    escribir_peticion(req)
    print(f"[classify-bridge] petición {req['id']} para {req['externalId']} ({len(chunk)} crops)", flush=True)

    got = esperar_faces(local_id, camara_id, batch_id, timeout, poll)
    if not got:
        print(f"[classify-bridge] timeout esperando faces de {req['externalId']}", flush=True)
        _rmtree(bdir)
        return False
    faces, job_dir = got

    rc = _aplicar_local(ruta, local_id, camara_id, batch_id, faces, timeout)
    if rc == 0:
        escribir_ack(job_dir_of(job_dir), source="clasificador_bridge")
    print(f"[classify-bridge] {camara_id} lote {batch_id}: decisión local aplicada (rc={rc})", flush=True)
    _rmtree(bdir)
    return rc == 0


def procesar_cam(local_id: str, camara_id: str, ruta: str, timeout: float, poll: float,
                 batch_size: int = 50) -> int:
    dir_in = os.path.join(ruta, "motor/caras/sinclasificar", str(local_id), str(camara_id))
    if not os.path.isdir(dir_in):
        return 0
    crops = [f for f in sorted(os.listdir(dir_in)) if f.lower().endswith(IMG_EXTS)]
    if not crops:
        return 0

    dir_in = os.path.abspath(dir_in)
    root_abs = os.path.abspath(ruta)
    if not dir_in.startswith(root_abs + os.sep):
        return 0

    n = max(1, int(batch_size))
    aplicados = 0
    for i in range(0, len(crops), n):
        if _procesar_lote(local_id, camara_id, ruta, dir_in, crops[i:i + n], timeout, poll):
            aplicados += 1
    print(f"[classify-bridge] {camara_id}: {aplicados} lote(s) aplicados", flush=True)
    return aplicados


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("camara_id")
    ap.add_argument("token", nargs="?", default=None, help="token de Jos_Thread (se ignora)")
    ap.add_argument("--ruta", default=PROYECTO)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--timeout", type=float, default=3600.0)
    ap.add_argument("--poll", type=float, default=5.0)
    ap.add_argument("--batch", type=int, default=50, help="crops por lote (F4)")
    args, _desconocidos = ap.parse_known_args()  # tolera el token final de Jos_Thread

    cameras = [c.strip() for c in str(args.camara_id).split(",") if c.strip()]

    if modo() != "superserver":
        cmd = [sys.executable, os.path.join(PROYECTO, "motor/clasificador.py"),
               args.local_id, args.camara_id, "--ruta", args.ruta]
        if args.once:
            cmd.append("--once")
        return subprocess.call(cmd)

    # F5: si el aplicador persistente (systemd) está vivo se usa; si no, `--once`.
    try:
        from motor import clasificador_queue as q
        if q.daemon_alive(args.ruta, args.local_id):
            print("[classify-bridge] aplicador persistente disponible (F5)", flush=True)
        else:
            print("[classify-bridge] aplicador persistente no disponible; se usará --once", flush=True)
    except Exception:  # noqa: BLE001
        pass

    for cam in cameras:
        try:
            procesar_cam(args.local_id, cam, args.ruta, args.timeout, args.poll, args.batch)
        except Exception as e:  # noqa: BLE001 — nunca rompe el bucle de cámaras
            print(f"[classify-bridge] error en cam {cam}: {e}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
