"""Carga del `.env` del proyecto (fuera de git) para los scripts del motor.

Regla de seguridad (AGENTS.md): el `.env` contiene secretos (RF_DB_PASS,
RF_LLM_API_KEY...) y NUNCA se commitea. Este módulo es el punto único de
lectura para que los daemons/scripts del motor no reimplementen el parseo.
"""
from __future__ import annotations

import os


def load_env(ruta: str | None = None) -> dict[str, str]:
    """Parsea `<ruta>/.env` y devuelve dict[str, str] (valores sin comillas)."""
    ruta = ruta or _default_ruta()
    env: dict[str, str] = {}
    f = os.path.join(ruta, ".env")
    if os.path.isfile(f):
        with open(f, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _default_ruta() -> str:
    """Raíz del proyecto: padre de motor/ (donde vive .env)."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def get(ruta: str | None, key: str, default: str = "") -> str:
    return load_env(ruta).get(key, default)


def get_int(ruta: str | None, key: str, default: int) -> int:
    try:
        return int(load_env(ruta).get(key, str(default)))
    except (TypeError, ValueError):
        return default


def get_float(ruta: str | None, key: str, default: float) -> float:
    try:
        return float(load_env(ruta).get(key, str(default)))
    except (TypeError, ValueError):
        return default


def get_bool(ruta: str | None, key: str, default: bool) -> bool:
    """Lee un booleano del `.env` (acepta 1/0, true/false, yes/no, on/off, si/no)."""
    raw = load_env(ruta).get(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on", "si", "sí")
