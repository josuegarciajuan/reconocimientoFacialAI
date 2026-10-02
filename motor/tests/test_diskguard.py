"""F20: guardia de disco (niveles ok/warn/block y fail-safe del snapshot)."""
import pytest

from motor.core import backup as B
from motor.core import diskguard as D


def _fake_usage(pct):
    def _u(ruta):
        return {"total": 100, "used": int(pct), "free": 100 - int(pct), "pct": float(pct)}
    return _u


@pytest.mark.parametrize("pct,level", [(50, "ok"), (85, "warn"), (94.9, "warn"), (95, "block"), (99, "block")])
def test_niveles(monkeypatch, pct, level):
    monkeypatch.setattr(D, "disk_usage", _fake_usage(pct))
    assert D.check("/x")["level"] == level


def test_umbrales_por_entorno(monkeypatch):
    monkeypatch.setenv("RF_DISK_SOFT_PCT", "70")
    monkeypatch.setenv("RF_DISK_HARD_PCT", "80")
    monkeypatch.setattr(D, "disk_usage", _fake_usage(75))
    g = D.check("/x")
    assert g["level"] == "warn" and g["soft"] == 70 and g["hard"] == 80


def test_backup_bloquea_en_disco_lleno(monkeypatch, tmp_path):
    monkeypatch.setattr(B, "disk_check", lambda ruta: {"level": "block", "pct": 97.0, "hard": 95.0, "soft": 85.0, "free": 1})
    with pytest.raises(RuntimeError, match="disco lleno"):
        B.new_backup_dir(str(tmp_path), "merge")


def test_backup_crea_dir_en_warn(monkeypatch, tmp_path):
    monkeypatch.setattr(B, "disk_check", lambda ruta: {"level": "warn", "pct": 88.0, "hard": 95.0, "soft": 85.0, "free": 5})
    d = B.new_backup_dir(str(tmp_path), "merge")
    assert d and "merge" in d
