"""Tests del enrutado situacional (motor/core/router.py).

El router decide qué capas son AUTORIDAD (deciden), CO-AUTORIDAD (deben
confirmar por acuerdo) y de APOYO (corroboran/vetan) según la situación del
query (pose + nitidez + presencia de cara/torso).
"""
import pytest

from motor.core.config import Config
from motor.core.router import Situation, route


def _cfg(**kw):
    return Config(**kw)


def test_frontal_nitida_early_exit():
    """Frontal nítida: la cara decide sola y NO se escalan capas caras."""
    cfg = _cfg()
    plan = route(Situation(pose="f", sharpness=120.0), cfg)
    assert plan.authority == ("cara",)
    assert plan.co_authority == ()
    assert plan.early_exit is True
    assert plan.support == ()


def test_frontal_borrosa_silueta_apoyo():
    cfg = _cfg()
    plan = route(Situation(pose="f", sharpness=20.0), cfg)
    assert plan.authority == ("cara",)
    assert plan.early_exit is False
    assert "silueta" in plan.support


def test_perfil_silueta_co_autoridad():
    cfg = _cfg()
    for pose in ("pi", "pd"):
        plan = route(Situation(pose=pose, sharpness=90.0), cfg)
        assert plan.authority == ("cara",)
        assert "silueta" in plan.co_authority


def test_angulos_raros_silueta_co_autoridad():
    cfg = _cfg()
    for pose in ("m45i", "m45d", "arr", "aba"):
        plan = route(Situation(pose=pose, sharpness=90.0), cfg)
        assert "silueta" in plan.co_authority


def test_pose_desconocida_apoyo_silueta_torso():
    cfg = _cfg(torso_enabled=True)
    plan = route(Situation(pose=None, sharpness=60.0, has_torso=True), cfg)
    assert plan.authority == ("cara",)
    assert plan.early_exit is False
    assert "silueta" in plan.support
    assert "torso" in plan.support


def test_sin_cara_autoridad_torso_vlm():
    """Sin cara (espaldas): torso+LLM mandan; nunca se decide con cara."""
    cfg = _cfg(torso_enabled=True)
    plan = route(Situation(pose=None, sharpness=0.0, has_face=False), cfg)
    assert plan.authority == ("torso", "vlm")


def test_silueta_deshabilitada_sin_co_autoridad():
    cfg = _cfg(silueta_enabled=False)
    plan = route(Situation(pose="pi", sharpness=90.0), cfg)
    assert plan.co_authority == ()


def test_min_sharpness_es_el_limite():
    cfg = _cfg(min_sharpness=55.0)
    p_bajo = route(Situation(pose="f", sharpness=54.0), cfg)
    p_alto = route(Situation(pose="f", sharpness=55.0), cfg)
    assert p_bajo.early_exit is False
    assert p_alto.early_exit is True
