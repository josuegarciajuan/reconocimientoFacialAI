"""Identidad de proyecto SuperServer por instancia (.env)."""
import os

from motor.core.instance import DEFAULT_PROJECT, mode_file, project_id, returns_dir


def test_default_project(monkeypatch, tmp_path):
    monkeypatch.delenv("RF_SUPERSERVER_PROJECT", raising=False)
    assert project_id(str(tmp_path)) == DEFAULT_PROJECT


def test_project_from_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("RF_SUPERSERVER_PROJECT", raising=False)
    (tmp_path / ".env").write_text("RF_SUPERSERVER_PROJECT=ojos\n", encoding="utf-8")
    assert project_id(str(tmp_path)) == "ojos"
    assert mode_file(str(tmp_path)) == "/var/lib/taildeck/projects/ojos.mode"
    assert returns_dir(str(tmp_path)) == "/var/lib/taildeck/returns/ojos"


def test_env_var_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("RF_SUPERSERVER_PROJECT", "ojos")
    (tmp_path / ".env").write_text("RF_SUPERSERVER_PROJECT=reconocimientoFacial\n", encoding="utf-8")
    assert project_id(str(tmp_path)) == "ojos"
