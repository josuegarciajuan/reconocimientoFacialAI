#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Identidad de instancia para los puentes de SuperServer.

`RF_SUPERSERVER_PROJECT` vive en el `.env` del proyecto. Los servicios lanzados
por PHP no exportan ese `.env` al entorno, así que lo leemos directamente de la
raíz del proyecto. El valor por defecto mantiene el comportamiento laboral.
"""
from __future__ import annotations

import os

from motor.core.env import get

DEFAULT_PROJECT = "reconocimientoFacial"


def project_id(ruta: str | None = None) -> str:
    if os.environ.get("RF_SUPERSERVER_PROJECT"):
        return os.environ["RF_SUPERSERVER_PROJECT"].strip()
    root = ruta or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return get(root, "RF_SUPERSERVER_PROJECT", DEFAULT_PROJECT).strip() or DEFAULT_PROJECT


def mode_file(ruta: str | None = None) -> str:
    return f"/var/lib/taildeck/projects/{project_id(ruta)}.mode"


def returns_dir(ruta: str | None = None) -> str:
    return f"/var/lib/taildeck/returns/{project_id(ruta)}"
