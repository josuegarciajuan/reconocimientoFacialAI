"""Tests de PROVENIENCIA de encodings (P1-P4: unir/separar exacto).

Cubre:
  - add() con `sources` y roundtrip (person_sources alineado).
  - Retrocompat: pickle V3 sin `sources` se lee con [None]*n.
  - move_by_source: mueve TODOS los encodings de una proveniencia y solo esos.
  - move_matching: fallback por coseno para encodings legacy.
  - merge/merge_undoable: conservan `sources` (P5).
  - _prune: mantiene `sources` alineado tras podar outliers.
  - move_foto (motor.core.provenance): vía "source" sin cargar el modelo; vía
    "missing" cuando la foto no existe (sin tocar BD/modelo).
"""
import pickle

import numpy as np

from motor.core.provenance import move_foto
from motor.core.store import FaceStore, SCHEMA, VERSION


def _e(k: int, noise: float = 0.0, seed: int = 0) -> np.ndarray:
    """Vector base e_k (ortonormal en 512-d) + ruido opcional."""
    v = np.zeros(512, dtype=np.float64)
    v[k] = 1.0
    if noise > 0:
        rng = np.random.default_rng(seed)
        v = v + noise * rng.standard_normal(512)
    return v / np.linalg.norm(v)


def _store(tmp_path, max_per_person=500) -> FaceStore:
    return FaceStore(str(tmp_path / "face_enc_v2"), max_per_person=max_per_person)


def _add(store, cod, embs, sources=None):
    store.add(cod, [np.asarray(e, dtype=np.float32) for e in embs],
              [80.0] * len(embs), ["f"] * len(embs), sources=sources)


# ---------------------------------------------------------------------------
# P1: esquema / retrocompat
# ---------------------------------------------------------------------------

def test_add_with_sources_roundtrip(tmp_path):
    store = _store(tmp_path)
    e0, e1 = _e(0), _e(1)
    _add(store, "A", [e0, e1, e0], sources=["foto1", "foto2", "foto1"])
    srcs = store.person_sources("A")
    assert srcs == ["foto1", "foto2", "foto1"]
    assert store.count("A") == 3


def test_add_without_sources_defaults_none(tmp_path):
    store = _store(tmp_path)
    _add(store, "A", [_e(0), _e(1)])
    assert store.person_sources("A") == [None, None]


def test_legacy_v3_pickle_without_sources_backcompat(tmp_path):
    """Un pickle V3 (sin `sources`) se lee con [None]*n y sigue siendo mutable."""
    path = str(tmp_path / "face_enc_v2")
    data = {"version": 3, "schema": SCHEMA, "persons": {
        "A": {"encodings": [_e(0).astype(np.float32), _e(1).astype(np.float32)],
              "quality": [80.0, 90.0], "poses": ["f", "pi"],
              "added_at": [1.0, 2.0], "appearance": None}}}
    with open(path, "wb") as fh:
        pickle.dump(data, fh)
    store = _store(tmp_path)
    assert store.person_sources("A") == [None, None]
    _add(store, "A", [_e(2)], sources=["fotoN"])
    assert store.person_sources("A") == [None, None, "fotoN"]


# ---------------------------------------------------------------------------
# P3: move_by_source (exacto) y move_matching (fallback)
# ---------------------------------------------------------------------------

def test_move_by_source_moves_all_and_only(tmp_path):
    store = _store(tmp_path)
    a1, a2 = _e(0, noise=0.01, seed=1), _e(0, noise=0.02, seed=2)
    b1 = _e(1, noise=0.01, seed=3)
    _add(store, "A", [a1, a1, a2], sources=["fotoX", "fotoX", "fotoY"])
    moved = store.move_by_source("A", "B", "fotoX")
    assert moved == 2
    assert store.count("A") == 1
    assert store.person_sources("A") == ["fotoY"]
    assert store.count("B") == 2
    assert store.person_sources("B") == ["fotoX", "fotoX"]


def test_move_by_source_unknown_source_noop(tmp_path):
    store = _store(tmp_path)
    _add(store, "A", [_e(0)], sources=["fotoZ"])
    assert store.move_by_source("A", "B", "fotoQ") == 0
    assert store.count("A") == 1
    assert store.count("B") == 0


def test_move_matching_fallback_cosine(tmp_path):
    store = _store(tmp_path)
    base = _e(0, noise=0.01, seed=1)
    close = _e(0, noise=0.02, seed=2)
    far = _e(1, noise=0.01, seed=3)
    _add(store, "A", [base, close, far], sources=[None, None, None])
    moved = store.move_matching("A", "B", [base], min_cosine=0.85)
    assert moved == 2          # base y close, no far
    assert store.count("B") == 2
    assert store.count("A") == 1


# ---------------------------------------------------------------------------
# P5: merge conserva proveniencia
# ---------------------------------------------------------------------------

def test_merge_conserves_sources(tmp_path):
    store = _store(tmp_path)
    _add(store, "A", [_e(0)], sources=["fotoA"])
    _add(store, "B", [_e(1)], sources=["fotoB"])
    store.merge("A", "B")
    assert store.person_sources("A") == ["fotoA", "fotoB"]
    assert store.count("B") == 0


def test_merge_undoable_conserves_sources(tmp_path):
    store = _store(tmp_path)
    _add(store, "A", [_e(0)], sources=["fotoA"])
    _add(store, "B", [_e(1), _e(1)], sources=["fotoB", "fotoB"])
    j = store.merge_undoable("A", "B")
    assert j["encodings_moved"] == 2
    assert store.person_sources("A") == ["fotoA", "fotoB", "fotoB"]
    store.restore_person("B", j["src_person"])   # rollback F6
    assert store.person_sources("B") == ["fotoB", "fotoB"]


# ---------------------------------------------------------------------------
# F1.4: _prune mantiene sources alineado
# ---------------------------------------------------------------------------

def test_prune_keeps_sources_aligned(tmp_path):
    store = _store(tmp_path, max_per_person=500)
    genuinas = [_e(0, noise=0.05, seed=i) for i in range(9)]
    embs = genuinas + [_e(7)]                     # e_7 ortogonal = outlier
    srcs = ["fotoA"] * 9 + ["fotoIntrusa"]
    _add(store, "A", embs, sources=srcs)
    srcs_out = store.person_sources("A")
    assert len(srcs_out) == len(store.person_encodings("A"))
    assert "fotoIntrusa" not in srcs_out          # el outlier fue podado
    assert srcs_out == ["fotoA"] * len(srcs_out)


# ---------------------------------------------------------------------------
# P4: move_foto (motor.core.provenance) — sin BD ni modelo
# ---------------------------------------------------------------------------

def test_move_foto_via_source_exacta(tmp_path, monkeypatch):
    from motor.core.config import Config
    store = _store(tmp_path)
    _add(store, "A", [_e(0), _e(0), _e(1)], sources=["foto10", "foto10", "foto11"])
    monkeypatch.setattr("motor.core.provenance.lookup_foto_source",
                        lambda ruta, fid: "foto10")
    cfg = Config()
    res = move_foto(store, str(tmp_path), cfg, 10, "A", "B")
    assert res["via"] == "source" and res["moved"] == 2
    assert store.person_sources("B") == ["foto10", "foto10"]
    assert store.person_sources("A") == ["foto11"]


def test_move_foto_same_person_noop(tmp_path, monkeypatch):
    from motor.core.config import Config
    store = _store(tmp_path)
    _add(store, "A", [_e(0)], sources=["foto10"])
    monkeypatch.setattr("motor.core.provenance.lookup_foto_source",
                        lambda ruta, fid: "foto10")
    cfg = Config()
    res = move_foto(store, str(tmp_path), cfg, 10, "A", "A")
    assert res["via"] == "noop" and res["moved"] == 0


def test_move_foto_foto_missing(tmp_path, monkeypatch):
    """Sin proveniencia y sin fichero de foto: noop 'missing' (no carga modelo)."""
    from motor.core.config import Config
    store = _store(tmp_path)
    _add(store, "A", [_e(0)], sources=[None])
    monkeypatch.setattr("motor.core.provenance.lookup_foto_source",
                        lambda ruta, fid: None)
    cfg = Config()
    res = move_foto(store, str(tmp_path), cfg, 999999, "A", "B")
    assert res["via"] == "missing" and res["moved"] == 0
