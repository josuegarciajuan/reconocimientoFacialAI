"""F20: guardia de disco para operaciones que escriben backups.

Evita que una consolidación llene el disco. Niveles:

  * ``ok``    : por debajo del umbral blando → adelante.
  * ``warn``  : ≥ ``RF_DISK_SOFT_PCT`` (85 %) → se avisa pero se continúa.
  * ``block`` : ≥ ``RF_DISK_HARD_PCT`` (95 %) → fail-safe: NO se crea el snapshot.

Los umbrales se pueden ajustar por entorno (``RF_DISK_SOFT_PCT`` /
``RF_DISK_HARD_PCT``) sin tocar código.
"""
from __future__ import annotations

import os
import shutil

DEFAULT_SOFT_PCT = 85.0
DEFAULT_HARD_PCT = 95.0


def _env_pct(name: str, default: float) -> float:
    try:
        v = float(os.environ.get(name, ""))
    except (TypeError, ValueError):
        return default
    return v if 0.0 < v <= 100.0 else default


def thresholds() -> tuple[float, float]:
    """Devuelve ``(soft, hard)`` en porcentaje de uso."""
    return (_env_pct("RF_DISK_SOFT_PCT", DEFAULT_SOFT_PCT),
            _env_pct("RF_DISK_HARD_PCT", DEFAULT_HARD_PCT))


def disk_usage(ruta: str) -> dict:
    """Uso del disco que contiene ``ruta`` (crea el dir si hace falta)."""
    os.makedirs(ruta, exist_ok=True)
    u = shutil.disk_usage(ruta)
    pct = (u.used / u.total * 100.0) if u.total else 0.0
    return {"total": u.total, "used": u.used, "free": u.free, "pct": pct}


def check(ruta: str, soft: float | None = None, hard: float | None = None) -> dict:
    """Nivel de guardia para ``ruta``: ``{level, pct, soft, hard, free}``."""
    s_def, h_def = thresholds()
    soft = s_def if soft is None else soft
    hard = h_def if hard is None else hard
    d = disk_usage(ruta)
    if d["pct"] >= hard:
        level = "block"
    elif d["pct"] >= soft:
        level = "warn"
    else:
        level = "ok"
    return {"level": level, "pct": d["pct"], "soft": soft, "hard": hard, "free": d["free"]}
