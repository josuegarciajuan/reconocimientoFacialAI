"""Tests de la Fase 2 "guardia de embedding" (decisión y admisión blindadas).

Cubre, sin red ni BD:
  - `quality.pose_valida`: poses fuera de rango / no finitas no son fiables.
  - `clasificador.hay_info_suficiente`: la guardia de información por tamaño.
  - `clasificador.admitir_encoding`: margen de admisión sobre la mejor persona
    externa (evita contaminar galerías con caras que se parecen a todas).
  - `router.route`: con `silueta_confirm_enabled=False` la silueta no enruta.
  - `fusion.decide_situational`: en banda [match, secure) la silueta
    desactivada ya no confirma -> "uncertain" en lugar de "match".
"""
from __future__ import annotations

from motor.clasificador import admitir_encoding, hay_info_suficiente
from motor.core.config import Config
from motor.core.fusion import CascadeContext, decide_situational
from motor.core.matching import LayerScore
from motor.core.quality import pose_valida
from motor.core.router import Situation, route


class _PoseFace:
    """Cara mínima para `pose_valida` (solo yaw/pitch/roll)."""

    def __init__(self, yaw: float = 0.0, pitch: float = 0.0, roll: float = 0.0):
        self.yaw = yaw
        self.pitch = pitch
        self.roll = roll


# ------------------------------------------------------------------ pose_valida

def test_pose_valida_dentro_de_rango():
    cfg = Config()
    assert pose_valida(_PoseFace(yaw=30.0, pitch=10.0, roll=5.0), cfg) is True
    # justo en el límite: sigue siendo válida
    assert pose_valida(_PoseFace(yaw=100.0, pitch=45.0, roll=60.0), cfg) is True


def test_pose_valida_yaw_excedido():
    cfg = Config()
    assert pose_valida(_PoseFace(yaw=100.1), cfg) is False
    assert pose_valida(_PoseFace(yaw=-120.0), cfg) is False


def test_pose_valida_pitch_excedido():
    cfg = Config()
    assert pose_valida(_PoseFace(pitch=45.1), cfg) is False
    assert pose_valida(_PoseFace(roll=60.1), cfg) is False


def test_pose_valida_no_finita():
    cfg = Config()
    assert pose_valida(_PoseFace(yaw=float("nan")), cfg) is False
    assert pose_valida(_PoseFace(pitch=float("inf")), cfg) is False
    assert pose_valida(_PoseFace(roll=float("-inf")), cfg) is False


# -------------------------------------------------------------- hay_info_suficiente

def test_hay_info_suficiente_alguna_cara_grande():
    assert hay_info_suficiente([50, 60, 96], 96) is True
    assert hay_info_suficiente([96], 96) is True


def test_hay_info_suficiente_todas_pequenas():
    assert hay_info_suficiente([50, 60, 95], 96) is False
    assert hay_info_suficiente([], 96) is False


# ---------------------------------------------------------------- admitir_encoding

def _cfg_adm(**kw) -> Config:
    base = dict(admission_cosine=0.48, admission_margin=0.05)
    base.update(kw)
    return Config(**base)


def test_admitir_margen_suficiente():
    assert admitir_encoding(0.60, 0.45, _cfg_adm(), new_person=False) is True


def test_admitir_margen_insuficiente():
    # supera admission_cosine pero la ventaja sobre el externo es < margen
    assert admitir_encoding(0.60, 0.58, _cfg_adm(), new_person=False) is False


def test_admitir_cos_propio_bajo():
    assert admitir_encoding(0.40, 0.10, _cfg_adm(), new_person=False) is False


def test_admitir_new_person_siempre():
    # La galería se construye desde cero: se admite sin mirar márgenes.
    assert admitir_encoding(0.0, 0.99, _cfg_adm(), new_person=True) is True


# ------------------------------------------------------------------ router.route

def test_route_perfil_sin_silueta_si_confirm_desactivada():
    cfg = Config(silueta_enabled=True, silueta_confirm_enabled=False)
    for pose in ("pi", "pd", "m45i", "aba"):
        plan = route(Situation(pose=pose, sharpness=90.0), cfg)
        assert "silueta" not in plan.co_authority
        assert "silueta" not in plan.support


def test_route_perfil_con_silueta_si_confirm_activada():
    cfg = Config(silueta_enabled=True, silueta_confirm_enabled=True)
    plan = route(Situation(pose="pi", sharpness=90.0), cfg)
    assert "silueta" in plan.co_authority


# ------------------------------------------------ fusion: silueta sin voto en [match, secure)

def _silueta_fuerte():
    # silueta que ANTES (confirm habilitada) confirmaba el match
    return CascadeContext(silueta=lambda cod: LayerScore(score=0.95, confidence=0.95))


def test_fusion_silueta_desactivada_no_confirma_gris():
    """Banda [match, secure): con confirm desactivada, la silueta no confirma
    aunque su score sea alto -> el veredicto es "uncertain" (nunca "match")."""
    cfg = Config(torso_enabled=False, vlm_enabled=False, openai_enabled=False,
                 silueta_enabled=True, silueta_confirm_enabled=False)
    res = decide_situational(
        {"A": 0.50, "B": 0.10}, _silueta_fuerte(), cfg,
        LayerScore(score=0.50, confidence=0.80),
        situation=Situation(pose="pi", sharpness=80.0))
    assert res.verdict == "uncertain"
    assert "silueta" not in res.layer_scores


def test_fusion_silueta_activada_si_confirma_gris():
    """Contraste: con confirm habilitada, la misma silueta confirma -> "match"."""
    cfg = Config(torso_enabled=False, vlm_enabled=False, openai_enabled=False,
                 silueta_enabled=True, silueta_confirm_enabled=True)
    res = decide_situational(
        {"A": 0.50, "B": 0.10}, _silueta_fuerte(), cfg,
        LayerScore(score=0.50, confidence=0.80),
        situation=Situation(pose="pi", sharpness=80.0))
    assert res.verdict == "match"
    assert res.person == "A"
