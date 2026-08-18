"""Tests de la fusión ponderada y escalada (F3)."""
import numpy as np

from motor.core.config import Config
from motor.core.fusion import CascadeContext, run_cascade, fuse
from motor.core.matching import LayerScore, select_candidates


def test_fuse_weighted():
    layers = {
        "cara": LayerScore(score=0.50, confidence=0.80),
        "torso": LayerScore(score=0.70, confidence=0.50),
    }
    weights = {"cara": 0.60, "torso": 0.15}
    S, conf = fuse(layers, weights)
    # S = (0.80*0.60*0.50 + 0.50*0.15*0.70) / (0.80*0.60 + 0.50*0.15)
    num = 0.80 * 0.60 * 0.50 + 0.50 * 0.15 * 0.70
    den = 0.80 * 0.60 + 0.50 * 0.15
    assert abs(S - num / den) < 1e-9
    assert 0.0 <= conf <= 1.0


def test_fuse_redistributes_when_unavailable():
    """Capa sin señal (c=0 / available=False) queda fuera y no arrastra la fusión."""
    layers = {
        "cara": LayerScore(score=0.55, confidence=0.90),
        "torso": LayerScore(score=0.0, confidence=0.0, available=False),
    }
    S, _ = fuse(layers, {"cara": 0.60, "torso": 0.15})
    assert abs(S - 0.55) < 1e-9


def test_fuse_no_signal_returns_zero():
    S, conf = fuse({"cara": LayerScore(available=False)}, {"cara": 0.6})
    assert S == 0.0 and conf == 0.0


def test_select_candidates_top1_top2_and_band():
    scores = {"A": 0.50, "B": 0.49, "C": 0.30, "D": 0.10}
    cfg = Config(escalate_band=0.02)
    cands = select_candidates(scores, cfg)
    assert cands[0] == "A"
    assert set(cands) >= {"A", "B"}          # top-1 + top-2 siempre
    assert "C" not in cands


def test_select_candidates_band_includes_close():
    scores = {"A": 0.50, "B": 0.46, "C": 0.44}
    cfg = Config(escalate_band=0.07)
    cands = select_candidates(scores, cfg)
    assert set(cands) == {"A", "B", "C"}     # dentro de la banda (>= 0.43)


def test_early_exit_high_confidence_match():
    cfg = Config(cascade_enabled=True, torso_enabled=True,
                 early_exit_conf=0.97, gray_high=0.42)
    ctx = CascadeContext(torso=lambda cod: LayerScore(score=0.98, confidence=1.0))
    res = run_cascade({"A": 0.35, "B": 0.20}, ctx, cfg,
                      LayerScore(score=0.35, confidence=0.5))
    assert res.verdict == "match" and res.person == "A"


def test_safety_invariant_face_secure_never_new():
    """Cara segura (>=secure con c alta) nunca se degrada a new."""
    cfg = Config(cascade_enabled=True, torso_enabled=True, vlm_enabled=True,
                 secure_threshold=0.40, face_conf_secure_floor=0.60,
                 gray_low=0.28, gray_high=0.42, new_confidence_min=0.45)
    # capas superiores dicen "claramente distinta" con confianza muy alta
    ctx = CascadeContext(
        torso=lambda cod: LayerScore(score=0.10, confidence=0.98),
        vlm=lambda cod: LayerScore(score=0.05, confidence=0.99),
    )
    res = run_cascade({"A": 0.55, "B": 0.10}, ctx, cfg,
                      LayerScore(score=0.55, confidence=0.80))
    assert res.verdict != "new"                # nunca new
    assert res.verdict in ("match", "uncertain")


def test_escalate_when_gray_then_match_with_vlm():
    """Cara en gris + torso en gris -> escala a VLM -> match."""
    cfg = Config(cascade_enabled=True, torso_enabled=True, vlm_enabled=True,
                 gray_low=0.28, gray_high=0.42, early_exit_conf=0.97)
    calls = {"vlm": 0}

    def torso(cod):
        return LayerScore(score=0.45, confidence=0.40)   # en gris

    def vlm(cod):
        calls["vlm"] += 1
        return LayerScore(score=0.90, confidence=0.60)

    ctx = CascadeContext(torso=torso, vlm=vlm)
    res = run_cascade({"A": 0.33, "B": 0.30}, ctx, cfg,
                      LayerScore(score=0.33, confidence=0.45))
    assert calls["vlm"] == 1
    assert res.verdict == "match" and res.person == "A"


def test_all_gray_ends_uncertain():
    cfg = Config(cascade_enabled=True, torso_enabled=True,
                 gray_low=0.28, gray_high=0.42)
    ctx = CascadeContext(torso=lambda cod: LayerScore(score=0.40, confidence=0.30))
    res = run_cascade({"A": 0.33, "B": 0.31}, ctx, cfg,
                      LayerScore(score=0.33, confidence=0.35))
    assert res.verdict == "uncertain"


def test_clear_new_with_high_confidence():
    cfg = Config(cascade_enabled=True, torso_enabled=True,
                 gray_low=0.28, gray_high=0.42, new_confidence_min=0.45)
    ctx = CascadeContext(torso=lambda cod: LayerScore(score=0.05, confidence=0.60))
    res = run_cascade({"A": 0.15, "B": 0.12}, ctx, cfg,
                      LayerScore(score=0.15, confidence=0.55))
    assert res.verdict == "new" and res.person is None


def test_cascade_with_numpy_imports():
    """Importación de numpy no rompe el módulo (regresión)."""
    layers = {"cara": LayerScore(score=0.4, confidence=0.5)}
    S, _ = fuse(layers, {"cara": 0.6})
    assert isinstance(S, float)
