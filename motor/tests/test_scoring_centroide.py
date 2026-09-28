"""Tests del scoring por CENTROIDE configurable (modo "max" intacto).

Cubre las funciones puras nuevas de ``motor/core/matching.py``:

- ``centroid_cosine``: varias filas, una fila, galería vacía, ponderación por
  calidad y centroide degenerado (vectores opuestos).
- ``scores_per_person_centroid``: agregación por persona y fallback global
  cuando no hay ninguna pose compatible (anti-fragmentación).
- ``face_scores_per_person``: dispatch max/centroid/blend y degradación segura
  de un modo desconocido a "max".
- ``Config.from_env``: la escala centroid_* solo se aplica si el modo != "max";
  en modo "max" los umbrales RF_* históricos quedan intactos.

No toca BD, red, cv2 ni insightface: usa un FaceStore sintético en tmp_path.
"""
from __future__ import annotations

import numpy as np

from motor.core.config import Config
from motor.core.matching import (centroid_cosine, face_scores_per_person,
                                 scores_per_person, scores_per_person_centroid,
                                 scores_per_person_pose_aware)
from motor.core.store import FaceStore

DIM = 4


def _u(v) -> np.ndarray:
    """Normaliza un vector a norma 1 (float64 para precisión en los asserts)."""
    a = np.asarray(v, dtype=np.float64)
    n = float(np.linalg.norm(a))
    return a / n if n > 0.0 else a


def _eje(k: int, dim: int = DIM) -> np.ndarray:
    v = np.zeros(dim, dtype=np.float64)
    v[k] = 1.0
    return v


def _rot(deg: float) -> np.ndarray:
    """Vector unitario en el plano (e0, e1) a ``deg`` grados de e0."""
    r = np.radians(deg)
    return _u([np.cos(r), np.sin(r), 0.0, 0.0])


def _store(tmp_path, name: str) -> FaceStore:
    return FaceStore(str(tmp_path / name), max_per_person=50)


# ---------------------------------------------------------------------------
# centroid_cosine
# ---------------------------------------------------------------------------

def test_centroid_cosine_varias_filas():
    """Dos vectores ortogonales: el centroide cae en la bisectriz (cos 1/sqrt2)."""
    g = np.stack([_eje(0), _eje(1)])
    esperado = 1.0 / np.sqrt(2.0)
    assert abs(centroid_cosine(_eje(0), g) - esperado) < 1e-6
    assert abs(centroid_cosine(_eje(1), g) - esperado) < 1e-6
    assert abs(centroid_cosine(_eje(2), g)) < 1e-6


def test_centroid_cosine_una_fila():
    """Con una sola fila el centroide es esa fila normalizada."""
    assert abs(centroid_cosine(_eje(0), np.stack([_eje(0)])) - 1.0) < 1e-6
    # fila sin normalizar: la función normaliza el centroide
    assert abs(centroid_cosine(_eje(0), np.asarray([[3.0, 0.0, 0.0, 0.0]])) - 1.0) < 1e-6
    # galería 1-D (d,) == una sola fila
    assert abs(centroid_cosine(_eje(0), _eje(0)) - 1.0) < 1e-6


def test_centroid_cosine_vacia():
    assert centroid_cosine(_eje(0), np.zeros((0, DIM))) == 0.0
    assert centroid_cosine(_eje(0), None) == 0.0


def test_centroid_cosine_ponderacion():
    """La ponderación por calidad desplaza el centroide hacia la fila de más peso."""
    g = np.stack([_eje(0), _eje(1)])
    q = _eje(1)
    uniforme = 1.0 / np.sqrt(2.0)
    assert abs(centroid_cosine(q, g) - uniforme) < 1e-6
    # pesos [3, 1] -> centroide (0.75, 0.25) normalizado; cos con e1 = 0.25/|.|
    ponderado = centroid_cosine(q, g, qualities=np.asarray([3.0, 1.0]))
    esperado = 0.25 / np.sqrt(0.75 ** 2 + 0.25 ** 2)
    assert abs(ponderado - esperado) < 1e-6
    assert ponderado < uniforme


def test_centroid_cosine_ponderacion_degradacion_segura():
    """Pesos a cero, negativos o de longitud incorrecta -> media uniforme."""
    g = np.stack([_eje(0), _eje(1)])
    q = _eje(0)
    uniforme = centroid_cosine(q, g)
    assert centroid_cosine(q, g, qualities=np.asarray([0.0, 0.0])) == uniforme
    assert centroid_cosine(q, g, qualities=np.asarray([-1.0, -1.0])) == uniforme
    assert centroid_cosine(q, g, qualities=np.asarray([1.0, 1.0, 1.0])) == uniforme


def test_centroid_cosine_degenerado():
    """Centroide de norma ~0 (vectores opuestos) -> 0.0, nunca NaN/inf."""
    g = np.stack([_eje(0), -_eje(0)])
    s = centroid_cosine(_eje(1), g)
    assert s == 0.0
    assert np.isfinite(s)


# ---------------------------------------------------------------------------
# scores_per_person_centroid
# ---------------------------------------------------------------------------

def test_scores_per_person_centroid_agrega_centroide(tmp_path):
    store = _store(tmp_path, "cent_agg")
    # A: dos plantillas a 25° -> centroide en la bisectriz (cos 12.5° con e0)
    store.add("A", [_eje(0), _rot(25.0)], [80.0, 80.0], ["f", "f"])
    # B: ortogonal -> 0
    store.add("B", [_eje(2)], [80.0], ["f"])
    q = _eje(0)
    sc = scores_per_person_centroid(q, store, Config())
    assert abs(sc["A"] - np.cos(np.radians(12.5))) < 1e-5
    assert abs(sc["B"]) < 1e-6


def test_scores_per_person_centroid_pondera_por_calidad(tmp_path):
    store = _store(tmp_path, "cent_qual")
    # C: la segunda plantilla tiene calidad 0 -> el centroide colapsa a e0
    store.add("C", [_eje(0), _rot(25.0)], [1.0, 0.0], ["f", "f"])
    q = _eje(0)
    sc = scores_per_person_centroid(q, store, Config())
    assert abs(sc["C"] - 1.0) < 1e-6


def test_scores_per_person_centroid_fallback_pose(tmp_path):
    """Sin pose compatible, la persona NO queda invisible: centroide global."""
    store = _store(tmp_path, "cent_pose")
    store.add("F", [_eje(0), _rot(25.0)], [80.0, 80.0], ["f", "f"])   # solo frontal
    cfg = Config(zones_enabled=True)
    q = _eje(0)
    sc = scores_per_person_centroid(q, store, cfg, pose="pi")         # perfil no compatible
    encs = store.person_encodings("F")
    quals = np.asarray(store.person("F")["quality"], dtype=np.float32)
    assert sc["F"] == centroid_cosine(q, encs, quals)
    assert sc["F"] > 0.0


# ---------------------------------------------------------------------------
# face_scores_per_person (dispatcher)
# ---------------------------------------------------------------------------

def _store_dispatch(tmp_path) -> FaceStore:
    store = _store(tmp_path, "dispatch")
    store.add("A", [_eje(0), _rot(25.0)], [80.0, 80.0], ["f", "f"])
    store.add("B", [_eje(2)], [80.0], ["f"])
    return store


def test_face_scores_max_coincide_con_comportamiento_actual(tmp_path):
    store = _store_dispatch(tmp_path)
    q = _u(_eje(0) + 0.1 * _eje(1))
    cfg = Config(face_score_mode="max")
    assert face_scores_per_person(q, store, cfg, None) == scores_per_person(q, store)
    # con pose y zones_enabled -> idéntico al ranking pose-consciente histórico
    cfg_z = Config(face_score_mode="max", zones_enabled=True)
    assert (face_scores_per_person(q, store, cfg_z, "f")
            == scores_per_person_pose_aware(q, store, cfg_z, "f"))


def test_face_scores_dispatch_centroid(tmp_path):
    store = _store_dispatch(tmp_path)
    q = _u(_eje(0) + 0.1 * _eje(1))
    cfg = Config(face_score_mode="centroid")
    assert (face_scores_per_person(q, store, cfg, None)
            == scores_per_person_centroid(q, store, cfg, None))


def test_face_scores_dispatch_blend(tmp_path):
    store = _store_dispatch(tmp_path)
    q = _u(_eje(0) + 0.1 * _eje(1))
    cfg = Config(face_score_mode="blend", face_centroid_w=0.7)
    blend = face_scores_per_person(q, store, cfg, None)
    cent = scores_per_person_centroid(q, store, cfg, None)
    maxs = scores_per_person(q, store)
    for cod in set(cent) | set(maxs):
        esperado = 0.7 * cent.get(cod, 0.0) + 0.3 * maxs.get(cod, 0.0)
        assert abs(blend[cod] - esperado) < 1e-6


def test_face_scores_blend_peso_fuera_de_rango_se_recorta(tmp_path):
    store = _store_dispatch(tmp_path)
    q = _eje(0)
    cfg = Config(face_score_mode="blend", face_centroid_w=2.0)   # -> 1.0
    assert (face_scores_per_person(q, store, cfg, None)
            == scores_per_person_centroid(q, store, cfg, None))


def test_face_scores_modo_desconocido_degrada_a_max(tmp_path):
    store = _store_dispatch(tmp_path)
    q = _eje(0)
    cfg = Config(face_score_mode="banana")
    assert face_scores_per_person(q, store, cfg, None) == scores_per_person(q, store)


# ---------------------------------------------------------------------------
# Config.from_env: activación/retrocompatibilidad de la escala centroide
# ---------------------------------------------------------------------------

def _cfg_con_env(tmp_path, texto: str) -> Config:
    (tmp_path / ".env").write_text(texto, encoding="utf-8")
    return Config.from_env(str(tmp_path))


def test_from_env_modo_centroid_aplica_umbrales(tmp_path):
    cfg = _cfg_con_env(tmp_path, "RF_FACE_SCORE_MODE=centroid\n")
    assert cfg.face_score_mode == "centroid"
    assert cfg.match_threshold == 0.40
    assert cfg.secure_threshold == 0.50
    assert cfg.margin == 0.05
    assert cfg.admission_cosine == 0.40
    assert cfg.gray_low == 0.25
    assert cfg.gray_high == 0.42
    assert cfg.new_low_floor == 0.20
    assert cfg.secure_threshold >= cfg.match_threshold + 0.03


def test_from_env_modo_centroid_permite_overrides(tmp_path):
    cfg = _cfg_con_env(tmp_path, "RF_FACE_SCORE_MODE=centroid\n"
                                 "RF_CENTROID_MATCH_THRESHOLD=0.44\n"
                                 "RF_CENTROID_ADMISSION_COSINE=0.36\n")
    assert cfg.match_threshold == 0.44
    assert cfg.admission_cosine == 0.36
    # invariante G2 reaplicado
    assert cfg.secure_threshold >= cfg.match_threshold + 0.03


def test_from_env_invariante_centroid_secure_mayor_match(tmp_path):
    cfg = _cfg_con_env(tmp_path, "RF_FACE_SCORE_MODE=centroid\n"
                                 "RF_CENTROID_MATCH_THRESHOLD=0.55\n"
                                 "RF_CENTROID_SECURE_THRESHOLD=0.50\n")
    assert cfg.match_threshold == 0.55
    assert abs(cfg.secure_threshold - 0.58) < 1e-9   # max(0.50, 0.55 + 0.03)


def test_from_env_modo_max_no_toca_umbrales_historicos(tmp_path):
    """En modo max (default) los centroid_* se ignoran por completo."""
    cfg = _cfg_con_env(tmp_path, "RF_MATCH_THRESHOLD=0.48\n"
                                 "RF_CENTROID_MATCH_THRESHOLD=0.99\n"
                                 "RF_CENTROID_ADMISSION_COSINE=0.99\n")
    assert cfg.face_score_mode == "max"
    assert cfg.match_threshold == 0.48
    assert cfg.admission_cosine == 0.48            # default histórico, sin override
    assert cfg.gray_low == 0.38
    assert cfg.new_low_floor == 0.30


def test_from_env_modo_invalido_degrada_a_max(tmp_path):
    cfg = _cfg_con_env(tmp_path, "RF_FACE_SCORE_MODE=banana\n"
                                 "RF_MATCH_THRESHOLD=0.48\n")
    assert cfg.face_score_mode == "max"
    assert cfg.match_threshold == 0.48


def test_cfg_snapshot_incluye_scoring_centroide():
    from motor.clasificador import _cfg_snapshot
    snap = _cfg_snapshot(Config(face_score_mode="centroid", face_centroid_w=0.6))
    assert snap["face_score_mode"] == "centroid"
    assert snap["face_centroid_w"] == 0.6
    assert "centroid_match_threshold" in snap
    assert "centroid_gray_low" in snap
