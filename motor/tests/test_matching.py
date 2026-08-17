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
