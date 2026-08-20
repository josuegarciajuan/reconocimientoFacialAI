"""Tests de superres.py: sin top-up forzado, salvaguardas, no-rotura sin SR, GFPGAN y frame_face."""
import numpy as np

from motor.core.config import Config
from motor.core.superres import enhance, frame_face, zoom_photo, _model_path, get_model


def tiny_bgr(w: int = 48, h: int = 56) -> np.ndarray:
    rng = np.random.default_rng(42)
    return rng.integers(0, 255, (h, w, 3), dtype=np.uint8)


def test_sr_disabled_returns_input_unchanged():
    cfg = Config()
    cfg.sr_enabled = False
    src = tiny_bgr()
    out = enhance(src, cfg)
    assert out.dtype == np.uint8
    assert out.ndim == 3 and out.shape[2] == 3
    # ya NO se reescala a sr_target_side: la salida queda al tamaño nativo
    assert out.shape == src.shape


def test_large_input_not_touched():
    cfg = Config()
    big = np.zeros((600, 600, 3), dtype=np.uint8)
    assert enhance(big, cfg).shape == big.shape


def test_sr_unavailable_returns_input_unchanged(monkeypatch):
    cfg = Config()
    monkeypatch.setattr("motor.core.superres.get_model", lambda name="compact": None)
    src = tiny_bgr()
    out = enhance(src, cfg)
    assert out.dtype == np.uint8
    assert out.shape == src.shape


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


# ---------------------------------------------------------------- frame_face

def test_frame_face_fills_target():
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    bbox = (100, 120, 140, 170)          # cara 40x50 centrada
    crop = frame_face(img, bbox, 0.70, 8)
    cw, ch = crop.shape[1], crop.shape[0]
    assert abs(cw - round(40 / 0.70)) <= 2   # ~57 px (ancho de la cara / face_fill)
    assert abs(ch - round(50 / 0.70)) <= 2   # ~71 px
    assert crop.shape == (ch, cw, 3)


def test_frame_face_min_pad():
    img = np.zeros((200, 200, 3), dtype=np.uint8)
    bbox = (90, 90, 100, 102)            # cara 10x12 muy pequeña
    crop = frame_face(img, bbox, 0.70, 8)
    assert crop.shape[1] >= 10 + 2 * 8   # nunca más pequeño que cara + min_pad
    assert crop.shape[0] >= 12 + 2 * 8


def test_frame_face_clamps_border():
    img = np.zeros((150, 200, 3), dtype=np.uint8)
    bbox = (0, 0, 40, 50)                # pegada a la esquina
    crop = frame_face(img, bbox, 0.70, 8)
    cw, ch = crop.shape[1], crop.shape[0]
    assert cw <= 200 and ch <= 150       # nunca se sale del rango
    assert crop.shape == (ch, cw, 3)


def test_frame_face_large_bbox_returns_full():
    img = np.zeros((80, 90, 3), dtype=np.uint8)
    bbox = (5, 5, 85, 75)                # cara casi llena la imagen
    crop = frame_face(img, bbox, 0.70, 8)
    assert crop.shape == img.shape       # no puede agrandar: devuelve la imagen


def test_zoom_photo_native_sr_size():
    """zoom_photo devuelve el tamaño nativo del SR x4 (crop x4), sin top-up."""
    cfg = Config()
    cfg.sr_enabled = False               # fallback determinista (sin dependencia de SR)
    cfg.sr_face_enabled = False          # sin GFPGAN en CI (evita descarga/carga)
    img = np.zeros((150, 150, 3), dtype=np.uint8)
    bbox = (62, 68, 95, 102)             # cara 33x34
    out = zoom_photo(img, bbox, cfg)
    assert out.dtype == np.uint8
    assert out.ndim == 3 and out.shape[2] == 3
    # sin top-up: el encuadre queda ~ cara/face_fill (no se hincha a 512)
    assert max(out.shape[:2]) < 100


def test_zoom_photo_face_fill_kept():
    """Tras zoom_photo la proporción de la cara en el encuadre se conserva (~face_fill)."""
    cfg = Config()
    cfg.sr_enabled = False
    cfg.sr_face_enabled = False          # sin GFPGAN en CI
    img = np.zeros((300, 300, 3), dtype=np.uint8)
    bbox = (100, 120, 140, 170)          # cara 40x50
    out = zoom_photo(img, bbox, cfg)
    # el encuadre es proporcional a la cara: el crop antes del SR mide fw/face_fill
    fw, fh = 40, 50
    exp_w = max(round(fw / 0.70), fw + 16)
    exp_h = max(round(fh / 0.70), fh + 16)
    scale = max(out.shape[:2]) / max(exp_h, exp_w)
    assert abs(out.shape[1] / exp_w - scale) < 0.01 or abs(out.shape[0] / exp_h - scale) < 0.01


def test_restore_face_without_gfpgan_returns_native():
    """restore_face con GFPGAN deshabilitado devuelve la imagen nativa (sin top-up)."""
    cfg = Config()
    cfg.sr_enabled = False
    cfg.sr_face_enabled = False
    src = tiny_bgr()
    from motor.core.superres import restore_face
    out = restore_face(src, cfg)
    assert out is not None
    assert out.shape == src.shape


# ---------------------------------------------------------------- merge_frames (MF-SR)

def _fake_face(bbox):
    return type("F", (), {"bbox": bbox})()


def test_merge_frames_requires_two_frames():
    from motor.core.superres import merge_frames
    cfg = Config()
    img = tiny_bgr(80, 80)
    face = _fake_face((20, 20, 60, 60))
    assert merge_frames([(img, face)], face.bbox, cfg) is None


def test_merge_frames_median_of_identical():
    from motor.core.superres import merge_frames
    cfg = Config()
    rng = np.random.default_rng(7)
    img = rng.integers(0, 255, (80, 80, 3), dtype=np.uint8)
    face = _fake_face((20, 20, 60, 60))
    out = merge_frames([(img, face), (img, face)], face.bbox, cfg)
    assert out is not None
    assert out.dtype == np.uint8
    assert out.ndim == 3 and out.shape[2] == 3


def test_merge_frames_reduces_noise():
    """La mediana de N frames ruidosos tiene menos varianza que un frame suelto."""
    from motor.core.superres import merge_frames
    cfg = Config()
    rng = np.random.default_rng(3)
    base = np.full((80, 80, 3), 100, dtype=np.uint8)
    noisy = [np.clip(base + rng.integers(-30, 30, base.shape), 0, 255).astype(np.uint8)
             for _ in range(5)]
    face = _fake_face((20, 20, 60, 60))
    out = merge_frames([(n, face) for n in noisy], face.bbox, cfg)
    assert out is not None
    single_std = float(np.std(noisy[0].astype(np.float32)))
    out_std = float(np.std(out.astype(np.float32)))
    assert out_std < single_std
