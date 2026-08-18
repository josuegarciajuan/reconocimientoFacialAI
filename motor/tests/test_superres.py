"""Tests de superres.py: fallback LANCZOS4, salvaguardas de tamaño y no-rotura sin SR."""
import numpy as np

from motor.core.config import Config
from motor.core.superres import enhance, _model_path, get_model


def tiny_bgr(w: int = 48, h: int = 56) -> np.ndarray:
    rng = np.random.default_rng(42)
    return rng.integers(0, 255, (h, w, 3), dtype=np.uint8)


def test_sr_disabled_fallback_upscales():
    cfg = Config()
    cfg.sr_enabled = False
    out = enhance(tiny_bgr(), cfg)
    assert out.dtype == np.uint8
    assert out.ndim == 3 and out.shape[2] == 3
    assert max(out.shape[:2]) >= cfg.sr_target_side


def test_large_input_not_touched():
    cfg = Config()
    big = np.zeros((600, 600, 3), dtype=np.uint8)
    assert enhance(big, cfg).shape == big.shape


def test_sr_unavailable_falls_back(monkeypatch):
    cfg = Config()
    monkeypatch.setattr("motor.core.superres.get_model", lambda name="compact": None)
    out = enhance(tiny_bgr(), cfg)
    assert out.dtype == np.uint8
    assert max(out.shape[:2]) >= cfg.sr_target_side


def test_enhance_never_none():
    cfg = Config()
    cfg.sr_enabled = False
    out = enhance(np.zeros((10, 10, 3), dtype=np.uint8), cfg)
    assert out is not None


def test_model_registry_known():
    from motor.core.superres import MODELS
    assert "compact" in MODELS and "x4plus" in MODELS


def test_sr_smoke_if_weights_present():
    """SR x4 real solo si los pesos ya están descargados (evita descargas en CI)."""
    import os
    import pytest

    if not os.path.exists(_model_path("compact")):
        pytest.skip("pesos realesr-general-x4v3 no presentes")
    cfg = Config()
    cfg.sr_model = "compact"
    model = get_model("compact")
    assert model is not None
    out = enhance(tiny_bgr(48, 56), cfg)
    assert out.shape[0] >= 56 * 4 and out.shape[1] >= 48 * 4  # h>=224, w>=192
