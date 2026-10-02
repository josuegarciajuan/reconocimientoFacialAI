#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cola de aplicación local para `classify` (F5) — sin puertos nuevos.

El bridge (productor) deja una petición en `<root>/<local>/in/`; el aplicador
persistente (`clasificador.py --serve`) la procesa y escribe su confirmación en
`<root>/<local>/done/`. El bridge espera esa confirmación. Todo por ficheros,
igual que el spool: la casa escribe, el proceso residente lee.
"""
from __future__ import annotations

import json
import os
import time

ROOT = "/var/lib/taildeck/clasificador"
ALIVE_TTL_S = 15.0


def queue_dirs(ruta: str, local_id) -> tuple[str, str]:
    base = os.path.join(ruta, "motor/clasificador_daemon", str(local_id))
    return os.path.join(base, "in"), os.path.join(base, "done")


def _paths(ruta: str, local_id) -> dict:
    base = os.path.join(ruta, "motor/clasificador_daemon", str(local_id))
    return {
        "base": base,
        "in": os.path.join(base, "in"),
        "done": os.path.join(base, "done"),
        "alive": os.path.join(base, ".alive"),
        "pid": os.path.join(base, ".pid"),
    }


def write_request(ruta: str, local_id, batch_id: str, cam, faces: dict,
                  busto: dict | None = None) -> str | None:
    """Escribe la petición de aplicación de un lote (atómico)."""
    p = _paths(ruta, local_id)
    try:
        os.makedirs(p["in"], exist_ok=True)
        dst = os.path.join(p["in"], f"{batch_id}.json")
        tmp = dst + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"batch": batch_id, "cam": str(cam), "faces": faces,
                       "busto": busto or {}, "ts": time.time()}, fh)
        os.replace(tmp, dst)
        return dst
    except OSError:
        return None


def list_requests(ruta: str, local_id) -> list[dict]:
    p = _paths(ruta, local_id)
    out = []
    try:
        for name in sorted(os.listdir(p["in"])):
            if not name.endswith(".json"):
                continue
            path = os.path.join(p["in"], name)
            try:
                with open(path, encoding="utf-8") as fh:
                    out.append({"path": path, "data": json.load(fh)})
            except (OSError, ValueError):
                continue
    except OSError:
        pass
    return out


def remove_request(path: str) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def done_path(ruta: str, local_id, batch_id: str) -> str:
    return os.path.join(_paths(ruta, local_id)["done"], f"{batch_id}.done.json")


def write_done(ruta: str, local_id, batch_id: str, payload: dict) -> str | None:
    p = _paths(ruta, local_id)
    try:
        os.makedirs(p["done"], exist_ok=True)
        dst = done_path(ruta, local_id, batch_id)
        tmp = dst + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp, dst)
        return dst
    except OSError:
        return None


def leer_done(ruta: str, local_id, batch_id: str) -> dict | None:
    path = done_path(ruta, local_id, batch_id)
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def esperar_done(ruta: str, local_id, batch_id: str, timeout_s: float, poll_s: float = 0.5) -> dict | None:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        got = leer_done(ruta, local_id, batch_id)
        if got is not None:
            return got
        time.sleep(poll_s)
    return None


def heart_beat(ruta: str, local_id) -> None:
    """Marca del aplicador vivo (lo llama el bucle --serve)."""
    p = _paths(ruta, local_id)
    try:
        os.makedirs(p["base"], exist_ok=True)
        with open(p["alive"], "w", encoding="utf-8") as fh:
            fh.write(str(time.time()))
    except OSError:
        pass


def write_pid(ruta: str, local_id) -> None:
    """Escribe el PID del aplicador (autoridad de 'vivo'). El bridge lo consulta
    para NO caer a `--once` mientras haya un aplicador corriendo (evita dobles
    escritores de la galería), aunque un lote largo supere el TTL del latido."""
    p = _paths(ruta, local_id)
    try:
        os.makedirs(p["base"], exist_ok=True)
        with open(p["pid"], "w", encoding="utf-8") as fh:
            fh.write(str(os.getpid()))
    except OSError:
        pass


def _pid_alive(path: str) -> bool:
    try:
        with open(path, encoding="utf-8") as fh:
            pid = int(fh.read().strip())
        return pid > 0 and os.path.isdir(f"/proc/{pid}")
    except (OSError, ValueError):
        return False


def daemon_alive(ruta: str, local_id, ttl_s: float = ALIVE_TTL_S) -> bool:
    """Vivo si el PID del aplicador existe; si no hay pidfile, por latido fresco."""
    p = _paths(ruta, local_id)
    if _pid_alive(p["pid"]):
        return True
    try:
        return (time.time() - os.path.getmtime(p["alive"])) < ttl_s
    except OSError:
        return False
