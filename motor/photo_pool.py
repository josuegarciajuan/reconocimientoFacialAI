#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Puente del pool para la foto HQ (M3 de SuperServer).

Lo usa `photo_worker.py` cuando el proyecto está en modo `superserver`: en vez
de calcular la HQ en la casa, deja la petición en el spool, espera el resultado
del nodo y aplica los MISMOS efectos que el daemon local:

  1. coloca `<out>.hq` en su ruta (atómico);
  2. borra el JSON del job y TODAS las fuentes PNG.

Si el modo es `local`, no se usa (el daemon procesa como siempre).
"""
from __future__ import annotations

import json
import os
import shutil
import time

MODE_FILE = "/var/lib/taildeck/projects/reconocimientoFacial.mode"
SPOOL_DIR = "/var/lib/taildeck/spool"
RETURNS_DIR = "/var/lib/taildeck/returns/reconocimientoFacial"


def modo() -> str:
    try:
        with open(MODE_FILE, encoding="utf-8") as fh:
            return "superserver" if fh.read().strip() == "superserver" else "local"
    except OSError:
        return "local"


def hq_name(out: str) -> str:
    return os.path.basename(out) + ".hq"


def build_request(out: str, frames: list[dict], rid: str | None = None) -> dict:
    rid = rid or f"req-{int(time.time())}-{os.getpid()}"
    return {
        "id": rid,
        "project": "reconocimientoFacial",
        "process": "hq_photo",
        "params": {"out": out, "frames": frames},
        "externalId": f"photo:{out}",
    }


def escribir_peticion(req: dict) -> str:
    os.makedirs(SPOOL_DIR, exist_ok=True)
    dst = os.path.join(SPOOL_DIR, f"{req['id']}.json")
    tmp = dst + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(req, fh, ensure_ascii=False)
    os.replace(tmp, dst)
    return dst


def esperar_hq(name: str, timeout_s: float, poll_s: float = 5.0) -> str | None:
    """Busca `result/<name>.hq` en los retornos del proyecto hasta el timeout."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if os.path.isdir(RETURNS_DIR):
            for d in sorted(os.listdir(RETURNS_DIR)):
                p = os.path.join(RETURNS_DIR, d, "result", name)
                if os.path.isfile(p):
                    return p
        time.sleep(poll_s)
    return None


def submit_and_apply(out: str, frames: list[dict], srcs: list[str], job_path: str,
                     timeout_s: float = 1800.0) -> bool:
    """Pide la HQ al pool y aplica los efectos en la casa. True si se aplicó."""
    if not out or not frames:
        return False
    req = build_request(out, frames)
    escribir_peticion(req)
    print(f"[photo-pool] petición {req['id']} para {req['externalId']}", flush=True)
    hq = esperar_hq(hq_name(out), timeout_s)
    if not hq:
        print(f"[photo-pool] timeout esperando {hq_name(out)}", flush=True)
        return False
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    tmp = out + ".hq.tmp"
    shutil.copyfile(hq, tmp)
    os.replace(tmp, out + ".hq")
    try:
        os.remove(job_path)
    except OSError:
        pass
    for s in set(srcs):
        try:
            os.remove(s)
        except OSError:
            pass
    print(f"[photo-pool] aplicado {hq_name(out)} (job+fuentes borrados)", flush=True)
    return True
