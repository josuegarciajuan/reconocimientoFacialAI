"""Tests de matching.py (decisión ganador/segundo con umbrales)."""
import numpy as np

from motor.core.config import Config
from motor.core.matching import MatchResult, cosine, decide, match_group
from motor.core.store import FaceStore


def rnd_emb(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(512)
    return v / np.linalg.norm(v)


def test_cosine_identical_is_one():
    v = rnd_emb(1)
    assert cosine(v, v) == 1.0


def test_cosine_orthogonal_is_zero():
    v = rnd_emb(1)
    w = rnd_emb(2)
    w -= v * float(np.dot(v, w))  # ortogonalizar
    w /= np.linalg.norm(w)
    assert abs(cosine(v, w)) < 1e-6


def test_decide_empty_is_new():
    cfg = Config()
    assert decide({}, cfg).verdict == "new"


def test_decide_secure_match():
    cfg = Config(secure_threshold=0.5, match_threshold=0.35, margin=0.05)
    r = decide({"A": 0.6, "B": 0.1}, cfg)
    assert r.verdict == "match" and r.person == "A"


def test_decide_match_with_margin():
    cfg = Config(secure_threshold=0.5, match_threshold=0.35, margin=0.05)
    r = decide({"A": 0.42, "B": 0.20}, cfg)
    assert r.verdict == "match" and r.person == "A"


def test_decide_uncertain_when_close():
    cfg = Config(secure_threshold=0.5, match_threshold=0.35, margin=0.05)
    r = decide({"A": 0.40, "B": 0.38}, cfg)
    assert r.verdict == "uncertain" and r.person == "A"


def test_decide_new_below_threshold():
    cfg = Config(secure_threshold=0.5, match_threshold=0.35, margin=0.05)
    r = decide({"A": 0.20, "B": 0.15}, cfg)
    assert r.verdict == "new" and r.person is None


def test_match_group_aggregates(tmp_path):
    cfg = Config()
    store = FaceStore(str(tmp_path / "face_enc_v2"), max_per_person=10)
    # persona A con 3 encodings cercanos entre sí (semilla 1)
    store.add("A", [rnd_emb(1), rnd_emb(11), rnd_emb(111)], [80.0, 80.0, 80.0], ["f", "f", "f"])
    # persona B con encodings distintos
    store.add("B", [rnd_emb(2), rnd_emb(22)], [80.0, 80.0], ["f", "f"])
    # query = embedding cercano a A (seed 1 perturbado)
    q = rnd_emb(1) + 0.1 * rnd_emb(99)
    q /= np.linalg.norm(q)
    r = match_group([q], store, cfg)
    assert r.person == "A"
    assert r.verdict in ("match", "uncertain")


def test_default_thresholds_calibrated():
    """Los umbrales por defecto deben ser los calibrados con datos reales (2026-08-18):
    coseno genuino de videovigilancia ~0.32-0.38. Si alguien los sube, los pares reales
    (p. ej. KaiZA3↔nRLmEs = 0.385) vuelven a fragmentarse."""
    cfg = Config()
    assert cfg.secure_threshold == 0.40
    assert cfg.match_threshold == 0.30
    assert cfg.margin == 0.03
    assert cfg.group_threshold == 0.30


def test_decide_real_pair_secure_margin():
    """Par real KaiZA3↔nRLmEs (coseno 0.385 vs 2º 0.318): con umbrales calibrados
    debe ser match seguro por margen."""
    cfg = Config()
    r = decide({"nRLmEs": 0.385, "0EQGx": 0.318}, cfg)
    assert r.verdict == "match" and r.person == "nRLmEs"


def test_decide_real_pair_uncertain_assigns_best():
    """Par real 1oN9gY↔eYPdoo (0.319 vs 0.300): por debajo de secure pero sobre match;
    si el margen no llega a 0.03, queda uncertain pero asignado a la mejor persona
    (el clasificador la une aunque no refine la plantilla)."""
    cfg = Config()
    r = decide({"eYPdoo": 0.319, "LcBiC": 0.300}, cfg)
    assert r.verdict == "uncertain" and r.person == "eYPdoo"


def test_match_group_uses_max_not_mean(tmp_path):
    """Una cara fuerte del grupo no debe diluirse por caras débiles de la misma batería.
    Con media el grupo quedaría por debajo del umbral (new); con max debe hacer match."""
    # vectores ortonormales e0, e1 en R^2 embebido en 512-d
    base = np.zeros(512, dtype=np.float64)
    base[0] = 1.0
    e1 = np.zeros(512, dtype=np.float64)
    e1[1] = 1.0

    cfg = Config(secure_threshold=0.5, match_threshold=0.35, margin=0.05)
    store = FaceStore(str(tmp_path / "face_enc_v2_max"), max_per_person=10)
    store.add("A", [base.astype(np.float32)], [80.0], ["f"])

    # cara fuerte: 0.60 con A  -> max del grupo = 0.60 (match seguro)
    q_strong = (0.60 * base + 0.80 * e1).astype(np.float32)
    q_strong /= np.linalg.norm(q_strong)
    # cara débil: 0.08 con A -> con media el grupo quedaría en (0.60+0.08)/2 = 0.34 < 0.35
    q_weak = (0.08 * base + 0.9968 * e1).astype(np.float32)
    q_weak /= np.linalg.norm(q_weak)

    r = match_group([q_strong, q_weak], store, cfg)
    assert r.verdict == "match" and r.person == "A"

    # comprobación de la premisa: con media NO habría match (0.34 < match_threshold)
    assert (0.60 + 0.08) / 2.0 < cfg.match_threshold
