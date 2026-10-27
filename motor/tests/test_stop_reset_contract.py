# -*- coding: utf-8 -*-
"""Contrato de los scripts de parada/reset (regresión 2026-10-27).

No ejecuta paradas reales: valida sintaxis y que los patrones críticos sigan
presentes. Los scripts se prueban en seco con `--dry-run` en el despliegue.
"""
from __future__ import annotations

import py_compile
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEPLOY = ROOT / "deploy"
SCRIPTS = ["rf_power.sh", "rf_stop.sh", "td_cancel.sh", "reset_datos.sh", "reset_all.sh"]


def test_bash_syntax() -> None:
    for name in SCRIPTS:
        subprocess.run(["bash", "-n", str(DEPLOY / name)], check=True)


def test_python_syntax() -> None:
    py_compile.compile(str(DEPLOY / "taildeck_cancel.py"), doraise=True)


def test_stop_covers_bridges_and_pipeline() -> None:
    text = (DEPLOY / "rf_stop.sh").read_text(encoding="utf-8")
    for token in (
        "pool_bridge.py",
        "clasificador_bridge.py",
        "archiva_video_bridge.py",
        "reprocesar_bridge.py",
        "pipeline_service.py",
        "rf-reprocesa",
        "rf-live",
        "td_cancel.sh",
    ):
        assert token in text, f"rf_stop.sh no cubre {token}"


def test_power_off_delegates_to_stop() -> None:
    text = (DEPLOY / "rf_power.sh").read_text(encoding="utf-8")
    assert "rf_stop.sh" in text
    assert "rf-pipeline" in text


def test_reset_fails_closed_without_project() -> None:
    text = (DEPLOY / "reset_datos.sh").read_text(encoding="utf-8")
    assert "RF_SUPERSERVER_PROJECT vacío" in text
    # Ya no se asume el proyecto laboral en silencio.
    assert "se asume 'reconocimientoFacial'" not in text


def test_reset_keeps_live_and_does_not_restart_in_no_start() -> None:
    text = (DEPLOY / "reset_datos.sh").read_text(encoding="utf-8")
    assert "LIVE_SERVICE=rf-live" in text
    assert "rf-live NO va aquí" in text
    assert "systemctl enable --now \"${LIVE_SERVICE}\"" in text


def test_cancel_is_project_scoped() -> None:
    text = (DEPLOY / "taildeck_cancel.py").read_text(encoding="utf-8")
    assert 'j.get("project") == project' in text
    assert "--purge-returns" in text
    assert "taildeck.service" in text  # documentado como intocable
