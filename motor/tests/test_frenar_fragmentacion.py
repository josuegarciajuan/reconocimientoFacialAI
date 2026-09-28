"""Tests del freno anti-fragmentación de identidades (2026-09-28).

Incidente: cada verdict `new`/`uncertain`/`review` creaba una identidad nueva
(BD + galería `face_enc_v2`), y con caras pequeñas + umbral bajo se generaron
>120 identidades en una hora. Este guard impide que un veredicto que NO es un
`match` confirmado cree identidad persistente mientras `autoenroll_new` esté
desactivado (default).

Cubre:
  - `debe_crear_identidad`: tabla de verdad del guard (función pura).
  - `Config.autoenroll_new`: default del dataclass (False).
  - `Config.from_env`: default y override por `RF_AUTOENROLL_NEW`.
"""
from __future__ import annotations

import pytest

from motor.clasificador import debe_crear_identidad
from motor.core.config import Config


# ---------------------------------------------------------------------------
# debe_crear_identidad: tabla de verdad
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("verdict,person,autoenroll,esperado", [
    # match confirmado (verdict match + persona): SIEMPRE crea identidad
    ("match", "P123", False, True),
    ("match", "P123", True, True),
    # no-match con default: NUNCA crea identidad persistente
    ("new", None, False, False),
    ("uncertain", None, False, False),
    ("review", None, False, False),
    ("new", "P123", False, False),
    ("uncertain", "P123", False, False),
    ("review", "P123", False, False),
    # match SIN persona no es un match confirmado -> False con default
    ("match", None, False, False),
    # autoenroll_new=True recupera el comportamiento anterior (alta de persona)
    ("new", None, True, True),
    ("uncertain", None, True, True),
    ("review", None, True, True),
    ("match", None, True, True),
])
def test_debe_crear_identidad_tabla(verdict, person, autoenroll, esperado):
    cfg = Config(autoenroll_new=autoenroll)
    assert debe_crear_identidad(verdict, person, cfg) is esperado


def test_debe_crear_identidad_no_muta_estado():
    """Función pura: no depende de estado global ni modifica la config."""
    cfg = Config(autoenroll_new=False)
    antes = dict(cfg.__dict__)
    debe_crear_identidad("uncertain", None, cfg)
    assert cfg.__dict__ == antes


# ---------------------------------------------------------------------------
# Default del dataclass
# ---------------------------------------------------------------------------

def test_default_dataclass_autoenroll_false():
    """El default del dataclass debe ser False (freno activo de fábrica)."""
    assert Config().autoenroll_new is False


# ---------------------------------------------------------------------------
# Config.from_env: default y override RF_AUTOENROLL_NEW
# ---------------------------------------------------------------------------

def _cfg_con_env(tmp_path, texto: str) -> Config:
    (tmp_path / ".env").write_text(texto, encoding="utf-8")
    return Config.from_env(str(tmp_path))


def test_from_env_default_autoenroll_false(tmp_path):
    cfg = _cfg_con_env(tmp_path, "")
    assert cfg.autoenroll_new is False


@pytest.mark.parametrize("valor", ["1", "true", "TRUE", "yes", "on", "si"])
def test_from_env_autoenroll_true(tmp_path, valor):
    cfg = _cfg_con_env(tmp_path, f"RF_AUTOENROLL_NEW={valor}\n")
    assert cfg.autoenroll_new is True


def test_from_env_autoenroll_explicito_false(tmp_path):
    cfg = _cfg_con_env(tmp_path, "RF_AUTOENROLL_NEW=0\n")
    assert cfg.autoenroll_new is False
