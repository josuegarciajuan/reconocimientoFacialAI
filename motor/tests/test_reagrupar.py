"""Tests de reagrupar.py — re-matching de la galería con la cascada (sin BD/red)."""
import numpy as np
import pytest

from motor.core.config import Config
from motor.core.store import FaceStore
from motor.reagrupar import (RepResolver, best_pair_cosine, coherencia_interna,
                             evaluar_par, load_embeddings)


def _rnd(seed):
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(512)
    return (v / np.linalg.norm(v)).astype(np.float32)


@pytest.fixture()
def store(tmp_path):
    s = FaceStore(str(tmp_path / "face_enc_v2"), max_per_person=10)
    base = _rnd(1)
    # persona X duplicada en A (frontal) y B (casi idéntica, misma persona)
    s.add("A", [base], [80.0], ["f"])
    b_emb = base + 0.05 * _rnd(99)
    b_emb = (b_emb / np.linalg.norm(b_emb)).astype(np.float32)
    s.add("B", [b_emb], [80.0], ["f"])
    # persona distinta
    s.add("C", [_rnd(2), _rnd(3)], [80.0, 70.0], ["pi", "pd"])
    return s


def test_best_pair_cosine_high_for_duplicate(store):
    embs = load_embeddings(store)
    s_ab = best_pair_cosine(embs["A"], embs["B"])
    s_ac = best_pair_cosine(embs["A"], embs["C"])
    assert s_ab > 0.8          # misma persona (coseno alto)
    assert s_ac < 0.3          # distinta


def test_evaluar_par_duplicate_is_match(store, tmp_path):
    cfg = Config(cascade_enabled=True, zones_enabled=True)   # umbrales configurados
    resolver = RepResolver(str(tmp_path), "1", cfg)          # sin fotos: sil=0.5
    embs = load_embeddings(store)
    s_ab = best_pair_cosine(embs["A"], embs["B"])
    r = evaluar_par(store, embs, resolver, cfg, "A", "B", s_ab)
    assert r["verdict"] in ("match", "uncertain")    # nunca "new" para la misma persona
    assert r["s_face"] > 0.8


def test_evaluar_par_distinta_is_not_match(store, tmp_path):
    cfg = Config(cascade_enabled=True, zones_enabled=True)
    resolver = RepResolver(str(tmp_path), "1", cfg)
    embs = load_embeddings(store)
    s_ac = best_pair_cosine(embs["A"], embs["C"])
    r = evaluar_par(store, embs, resolver, cfg, "A", "C", s_ac)
    # personas distintas: NUNCA match y S por debajo del umbral gris
    assert r["verdict"] != "match"
    assert r["S"] < cfg.gray_low


def test_evaluar_par_no_photos_degrades_gracefully(store, tmp_path):
    """Sin fotos representativas, la capa zonas usa sil=0.5 y el par sigue evaluable."""
    cfg = Config(cascade_enabled=True, zones_enabled=True)
    resolver = RepResolver(str(tmp_path), "1", cfg)
    embs = load_embeddings(store)
    s_ab = best_pair_cosine(embs["A"], embs["B"])
    r = evaluar_par(store, embs, resolver, cfg, "A", "B", s_ab)
    assert 0.0 <= r["S"] <= 1.0
    assert r["verdict"] in ("match", "uncertain", "new")


def test_coherencia_interna_detecta_mezcla(tmp_path):
    s = FaceStore(str(tmp_path / "f"), max_per_person=50)
    base = _rnd(1)
    # galería PURA: la misma persona (vectores casi idénticos)
    pura = [base]
    for i in range(2):
        v = base + 0.05 * _rnd(100 + i)
        pura.append((v / np.linalg.norm(v)).astype(np.float32))
    s.add("PURA", pura, [80.0] * 3, ["f"] * 3)
    # galería MEZCLADA: dos personas distintas (vectores ortogonales)
    s.add("MEZCLA", [_rnd(2), _rnd(3), _rnd(4), _rnd(5)], [80.0] * 4, ["f"] * 4)
    embs = load_embeddings(s)
    coh = coherencia_interna(embs)
    assert coh["PURA"] > 0.5
    assert coh["MEZCLA"] < 0.2     # media intra muy baja -> contaminada


def test_reporte_vacio_no_rompe(tmp_path):
    """Galería vacía: el reporte termina sin errores y sin candidatos."""
    cfg = Config(cascade_enabled=True, zones_enabled=True)
    s = FaceStore(str(tmp_path / "f"))
    from motor.reagrupar import reporte
    out = str(tmp_path / "out")
    res = reporte(str(tmp_path), "1", cfg, s, floor=cfg.match_threshold, out_dir=out)
    assert res == []
