"""Tests de zonas/ángulos (F2, L1c): pose-compatibilidad y silueta."""
import numpy as np

from motor.core.zones import (pose_compatible, pose_confidence,
                              silhouette_descriptor, silhouette_sim)


class _Face:
    def __init__(self, landmarks=None, bbox=(10, 10, 60, 70)):
        self.landmarks = landmarks
        self.bbox = bbox


def _fake_landmarks(seed=1):
    rng = np.random.default_rng(seed)
    # 106 landmarks en un cuadrado aprox. cara
    lm = rng.uniform(0, 100, (106, 2)).astype(np.float32)
    lm[0] = [10, 10]      # frente
    lm[8] = [50, 90]      # mentón
    lm[33] = [30, 40]     # ojo izq
    lm[87] = [70, 40]     # ojo der
    lm[52] = [50, 55]     # nariz
    lm[98] = [50, 10]     # frente alta
    lm[61], lm[72] = [40, 65], [60, 65]   # boca
    lm[4], lm[103] = [15, 20], [85, 20]   # sienes
    return lm


def test_pose_compatible():
    assert pose_compatible("f", "f")
    assert pose_compatible("f", "m45i")
    assert pose_compatible("pi", "pi")
    assert pose_compatible("pi", "m45i")
    assert not pose_compatible("pi", "pd")
    assert not pose_compatible("pi", "f")
    assert pose_compatible(None, "f")        # sin etiqueta: no descartar


def test_pose_confidence_values():
    assert pose_confidence("f", "f") == 1.0
    assert pose_confidence("f", "m45d") == 0.6
    assert pose_confidence("pi", "pd") == 0.0


def test_silhouette_descriptor_no_landmarks():
    f = _Face(landmarks=None)
    d = silhouette_descriptor(f)
    assert d.size == 0


def test_silhouette_self_similar():
    lm = _fake_landmarks(1)
    f = _Face(landmarks=lm)
    d = silhouette_descriptor(f)
    assert d.size > 0
    assert silhouette_sim(d, d) > 0.99


def test_silhouette_scale_invariant():
    """La silueta debe ser invariante a la escala (normalizada por inter-pupilar)."""
    lm = _fake_landmarks(1)
    lm_big = lm * 2.0
    a = silhouette_descriptor(_Face(landmarks=lm))
    b = silhouette_descriptor(_Face(landmarks=lm_big))
    assert silhouette_sim(a, b) > 0.95


def test_silhouette_different_shapes_low_sim():
    lm1 = _fake_landmarks(1)
    lm2 = _fake_landmarks(2)
    lm2[8] = [50, 140]                       # mentón mucho más bajo
    a = silhouette_descriptor(_Face(landmarks=lm1))
    b = silhouette_descriptor(_Face(landmarks=lm2))
    assert silhouette_sim(a, b) < 0.99


def test_silhouette_mismatched_shapes_zero():
    assert silhouette_sim(np.zeros(0), np.zeros(0)) == 0.0
