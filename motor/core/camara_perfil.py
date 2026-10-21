#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Perfil operativo de las cámaras del bridge `camaraip` (Ojos).

El bridge de camaraESP es la fuente de verdad. Este helper solo actúa sobre
URLs con `camera=<id>`; las RTSP de laboral devuelven ``None`` y cada script
conserva su comportamiento actual.

Sin dependencias externas. Cache en proceso de 30 s.
"""

from __future__ import annotations

import json
import os
import time
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

_CACHE: dict[str, tuple[float, dict | None]] = {}
_CACHE_TTL = 30.0
_DEFAULT_PROFILE_URL = "http://127.0.0.1:8111/camaraip/profile"


def camera_id_from_url(url: str | None) -> str | None:
    """Devuelve el ID camaraip de la URL, o ``None`` si no es del bridge."""
    if not url:
        return None
    try:
        parts = urlparse(str(url))
    except ValueError:
        return None
    host = (parts.hostname or "").lower()
    port = parts.port or 0
    path = parts.path or ""
    es_local = host in ("127.0.0.1", "localhost", "::1") and port in (0, 8111)
    es_camaraip = "/camaraip/" in path
    if not es_local and not es_camaraip:
        return None
    query = parse_qs(parts.query or "")
    values = query.get("camera") or []
    camera_id = values[0].strip() if values else ""
    return camera_id or None


def fetch_profile(url: str | None, timeout: float = 0.8) -> dict | None:
    """Perfil completo del bridge para una URL camaraip, o ``None``."""
    camera_id = camera_id_from_url(url)
    if camera_id is None:
        return None
    now = time.time()
    cached = _CACHE.get(camera_id)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return cached[1]

    base = os.environ.get("RF_CAMARA_PROFILE_URL") or _DEFAULT_PROFILE_URL
    sep = "&" if "?" in base else "?"
    endpoint = base + sep + "camera=" + camera_id
    data = None
    try:
        request = Request(endpoint, headers={"Accept": "application/json"})
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
        parsed = json.loads(raw.decode("utf-8", "replace"))
        if isinstance(parsed, dict) and isinstance(parsed.get("profile"), dict):
            data = parsed
    except Exception:
        data = None
    _CACHE[camera_id] = (now, data)
    return data


def profile_fps(url: str | None, fallback: float) -> float:
    """fps del perfil, o ``fallback`` si no es camaraip/no responde."""
    data = fetch_profile(url)
    if not data:
        return float(fallback)
    stream = (data.get("profile") or {}).get("stream") or {}
    try:
        perfil_fps = float(stream.get("fps"))
    except (TypeError, ValueError):
        perfil_fps = float(fallback)
    if perfil_fps <= 0:
        perfil_fps = float(fallback)

    # Preferir el fps medido por el bridge cuando ya hay frames: si el agente
    # todavía va a 2 fps, grabar a 5 aceleraría los clips.
    measured = (data.get("measured") or {}).get("fps")
    try:
        medido = float(measured)
    except (TypeError, ValueError):
        medido = 0.0
    if medido >= 1.0 and medido <= max(perfil_fps * 2.0, 10.0):
        return medido
    return perfil_fps


def profile_stream_size(url: str | None) -> tuple[int, int] | None:
    data = fetch_profile(url)
    if not data:
        return None
    stream = (data.get("profile") or {}).get("stream") or {}
    try:
        width = int(stream.get("width"))
        height = int(stream.get("height"))
    except (TypeError, ValueError):
        return None
    return (width, height) if width > 0 and height > 0 else None


def latest_jpeg_url(url: str | None) -> str | None:
    camera_id = camera_id_from_url(url)
    if camera_id is None:
        return None
    return "http://127.0.0.1:8111/camaraip/latest.jpg?camera=" + camera_id


def stream_url(url: str | None) -> str | None:
    camera_id = camera_id_from_url(url)
    if camera_id is None:
        return None
    return "http://127.0.0.1:8111/camaraip/stream?camera=" + camera_id
