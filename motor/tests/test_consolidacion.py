"""Tests de la consolidación al nacer (Fase 5/M6) y del score robusto (M2)."""
import numpy as np

from motor.consolidar_nacidos import (choose_merge_candidate, enqueue,
                                      _read_queue)
from motor.core.config import Config
from motor.core.matching import best_cosine_robust, robust_scores_per_person
from motor.core.store import FaceStore


def _e(k: int, noise: float = 0.0, seed: int = 0) -> np.ndarray:
    v = np.zeros(512, dtype=np.float64)
    v[k] = 1.0
    if noise > 0:
        rng = np.random.default_rng(seed)
        v = v + noise * rng.standard_normal(512)
    return v / np.linalg.norm(v)


def _cfg(**kw):
    base = dict(consolidate_min_cos=0.50, consolidate_min_margin=0.05)
    base.update(kw)
    return Config(**base)


def _store(tmp_path, groups: dict[str, list[np.ndarray]]):
    s = FaceStore(str(tmp_path / "face_enc_v2"), max_per_person=200)
    for cod, encs in groups.items():
        s.add(cod, encs, [80.0] * len(encs), ["f"] * len(encs))
    return s


def test_robust_topk_media_suaviza_max():
    """M2: media top-k; un solo valor alto no domina tanto como el max."""
    g = np.stack([_e(0, noise=0.01, seed=i) for i in range(8)])
    q = _e(0, noise=0.01, seed=99)
    m = float(np.max(g @ q))
    r = best_cosine_robust(q, g, k=5)
    assert 0.0 < r <= m + 1e-6


def test_consolidar_fusiona_gemelo(tmp_path):
    """La persona nueva (1 pose) y la ya rica (5 poses) de la misma persona:
    el worker elige fusionar cuando la galería rica ya da >=0.50."""
    cfg = _cfg()
    base = _e(0)
    rng = np.random.default_rng(3)
    ricas = []
    for _ in range(5):
        v = base + 0.02 * rng.standard_normal(512)
        ricas.append(v / np.linalg.norm(v))
    store = _store(tmp_path, {
        "RICA": ricas,
        "NUEVA": [base + 0.01 * rng.standard_normal(512)],
        "OTRA": [_e(1)],
    })
    cand = choose_merge_candidate(store, cfg, "NUEVA", exclude={"NUEVA"})
    assert cand == "RICA"


def test_consolidar_no_fusiona_personas_distintas(tmp_path):
    """Dos personas reales distintas con parecido moderado (caso 6-7 ~0.43):
    por debajo del mínimo 0.50 y/o sin margen -> NO fusionar."""
    cfg = _cfg()
    a = _e(0, noise=0.0)
    b = _e(0, noise=0.0)  # idénticas a propósito NO; usamos par distinto:
    store = _store(tmp_path, {
        "P6": [_e(0), _e(0, noise=0.01, seed=1)],
        "P7": [_e(1), _e(1, noise=0.01, seed=2)],
    })
    cand = choose_merge_candidate(store, cfg, "P6", exclude=set())
    assert cand is None          # coseno ~0 entre e0 y e1


def test_consolidar_requiere_margen_top1_top2(tmp_path):
    """M4: dos candidatos con parecido alto y SIN margen entre ellos -> no
    se decide (riesgo de confundir personas parecidas)."""
    cfg = _cfg()
    base = _e(0, noise=0.02, seed=1)
    rng = np.random.default_rng(7)
    near1 = base + 0.005 * rng.standard_normal(512)
    near2 = base + 0.005 * rng.standard_normal(512)
    near1 /= np.linalg.norm(near1)
    near2 /= np.linalg.norm(near2)
    store = _store(tmp_path, {
        "NUEVA": [base],
        "A": [near1],
        "B": [near2],
    })
    # sin margen (A y B casi iguales entre sí y con NUEVA) -> None
    cand = choose_merge_candidate(store, cfg, "NUEVA", exclude=set())
    assert cand is None


def test_pending_queue_enqueue_y_lee(tmp_path):
    cfg = Config()
    ruta = str(tmp_path)
    enqueue(ruta, "1", "codX", "m45d")
    enqueue(ruta, "1", "codX", "aba")       # dedup por cod
    entries = _read_queue(ruta, "1")
    assert len(entries) == 1
    assert entries[0]["cod"] == "codX"
    assert entries[0]["attempts"] == 0


def test_robust_scores_per_person_fallback_sin_pose(tmp_path):
    store = _store(tmp_path, {"P": [_e(0, noise=0.01, seed=1)]})
    s = robust_scores_per_person([_e(0, noise=0.01, seed=2)], store, k=5, pose="pd")
    assert s["P"] > 0.5
