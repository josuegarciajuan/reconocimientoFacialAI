"""Tests de la capa de apariencia/torso (F1, L1b)."""
import numpy as np
import pytest
import cv2

from motor.core.appearance import (Appearance, appearance_similarity,
                                   freshness, layer_score, torso_descriptor)


def _solid_img(color, h=128, w=64):
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = color
    return img


def test_descriptor_shape_and_norm():
    img = _solid_img((60, 120, 180))
    d = torso_descriptor(img, (0, 0, 64, 128))
    assert d.shape == (144,)
    # el bloque de histograma está sum-normalizado (intersección 0..1)
    assert abs(float(d[:96].sum()) - 1.0) < 1e-4
    assert d[96:].min() >= 0.0 and d[96:].max() <= 1.0


def test_descriptor_same_color_high_similarity():
    a = torso_descriptor(_solid_img((60, 120, 180)), (0, 0, 64, 128))
    b = torso_descriptor(_solid_img((62, 118, 182)), (0, 0, 64, 128))
    assert appearance_similarity(a, b) > 0.9


def test_descriptor_different_color_low_similarity():
    a = torso_descriptor(_solid_img((60, 120, 180)), (0, 0, 64, 128))
    b = torso_descriptor(_solid_img((200, 30, 30)), (0, 0, 64, 128))
    assert appearance_similarity(a, b) < 0.5


def test_bbox_clamped_out_of_frame():
    img = _solid_img((10, 10, 10), h=50, w=50)
    d = torso_descriptor(img, (-20, -20, 200, 200))   # fuera del frame
    assert d.shape == (144,)


def test_freshness_ttl():
    now = 1_000_000.0
    assert freshness(now, now, ttl_days=30) == 1.0
    assert freshness(now - 15 * 86400, now, ttl_days=30) == pytest.approx(0.5)
    assert freshness(now - 40 * 86400, now, ttl_days=30) == 0.0


def test_layer_score_uses_freshness():
    now = 1_000_000.0
    q = torso_descriptor(_solid_img((60, 120, 180)), (0, 0, 64, 128))
    gal = [
        Appearance(torso_descriptor(_solid_img((60, 120, 180)), (0, 0, 64, 128)),
                   ts=now - 15 * 86400),        # media vida
        Appearance(torso_descriptor(_solid_img((200, 30, 30)), (0, 0, 64, 128)),
                   ts=now),                     # fresco pero distinto
    ]
    s, c, avail = layer_score(q, gal, now=now, ttl_days=30)
    assert avail
    assert 0.0 < c <= 1.0
    # la frescura debe castigar la coincidencia con el descriptor viejo
    s_fresh, c_fresh, _ = layer_score(q, [gal[1]], now=now, ttl_days=30)
    assert c_fresh < c   # la coincidencia fresca (pero distinta) pesa menos que la vieja (igual)


def test_layer_score_no_gallery_unavailable():
    q = torso_descriptor(_solid_img((60, 120, 180)), (0, 0, 64, 128))
    s, c, avail = layer_score(q, [], ttl_days=30)
    assert not avail and c == 0.0


def test_save_load_crop_roundtrip(tmp_path):
    """El descriptor del crop guardado a disco debe ser reproducible."""
    img = _solid_img((60, 120, 180))
    p = tmp_path / "torso.jpg"
    cv2.imwrite(str(p), img)
    loaded = cv2.imread(str(p))
    d1 = torso_descriptor(img, (0, 0, 64, 128))
    d2 = torso_descriptor(loaded, (0, 0, 64, 128))
    assert appearance_similarity(d1, d2) > 0.99
