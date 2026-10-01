#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ack casa→plano de control (F2) y huella de entradas.

Tras aplicar los efectos de un job en la casa, el bridge escribe
`<SPOOL_DIR>/acks/<jobId>.json`. El plano de control lo recoge por la MISMA vía
que el spool (sin abrir puertos) y marca el job como `applied`.

`fingerprint(paths)` resume (ruta, tamaño, mtime) de las entradas para que un
resultado antiguo no se confunda con una petición nueva.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

SPOOL_DIR = "/var/lib/taildeck/spool"
ACK_DIR = os.path.join(SPOOL_DIR, "acks")


def fingerprint(paths, extra: str = "") -> str:
    """Huella estable de una lista de rutas (ruta + tamaño + mtime_ns)."""
    h = hashlib.sha256()
    for p in sorted(str(x) for x in (paths or [])):
        h.update(p.encode("utf-8", "replace"))
        try:
            st = os.stat(p)
            h.update(f"|{st.st_size}|{st.st_mtime_ns}".encode())
        except OSError:
            h.update(b"|missing")
    h.update(("|" + str(extra)).encode("utf-8", "replace"))
    return h.hexdigest()[:32]


def ack_path(job_id: str) -> str:
    return os.path.join(ACK_DIR, f"{job_id}.json")


def escribir_ack(job_id: str, status: str = "applied", source: str | None = None) -> str | None:
    """Marca un job como aplicado en la casa. Devuelve la ruta o None."""
    if not job_id:
        return None
    try:
        os.makedirs(ACK_DIR, exist_ok=True)
        dst = ack_path(str(job_id))
        tmp = dst + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({
                "jobId": str(job_id),
                "status": status,
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "source": source,
            }, fh, ensure_ascii=False)
        os.replace(tmp, dst)
        return dst
    except OSError:
        return None


def job_dir_of(path: str) -> str | None:
    """Job id a partir de un path de retorno `.../<project>/<jobId>[/result/...]`.

    El directorio de retorno es `<RETURNS_DIR>/<project>/<jobId>`; `result` es un
    subdirectorio. Se usa el penúltimo componente que no sea `result`.
    """
    p = os.path.abspath(path)
    parts = p.split(os.sep)
    if "result" in parts:
        i = parts.index("result")
        return parts[i - 1] if i - 1 >= 0 else None
    return parts[-1] if parts else None
