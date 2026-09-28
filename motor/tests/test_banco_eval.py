"""Tests de audit/banco_eval.py (sin red ni BD, embeddings sintéticos)."""
from __future__ import annotations

from collections import Counter

import numpy as np

from motor.audit import banco_eval as be

DIM = 8


def _unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def _eje(i: int, dim: int = DIM) -> np.ndarray:
    v = np.zeros(dim, dtype=np.float64)
    v[i] = 1.0
    return v


ETIQUETAS = [
    {"id": 10, "cod_interno": "A", "persona": "Ana"},
    {"id": 20, "cod_interno": "B", "persona": "Beto"},
]


def _fotos(persona_id: int, n: int, cam: str = "cam1") -> list[dict]:
    return [
        {
            "foto_id": f"f{persona_id}_{i}",
            "persona_id": persona_id,
            "ruta": f"/fotos/{persona_id}_{i}.jpg",
            "ts": float(i),
            "cam": cam,
        }
        for i in range(n)
    ]


def _embeddings(base_idx: int, persona_id: int, n: int, seed: int) -> dict[str, np.ndarray]:
    base = _eje(base_idx)
    out = {}
    for i in range(n):
        rng = np.random.default_rng(seed + i)
        out[f"/fotos/{persona_id}_{i}.jpg"] = _unit(base + 0.02 * rng.standard_normal(DIM))
    return out


# ---------------------------------------------------------------------------
# construir_manifiesto
# ---------------------------------------------------------------------------
def test_particion_sin_leakage():
    fotos = _fotos(10, 5) + _fotos(20, 5)
    m = be.construir_manifiesto(fotos, ETIQUETAS, test_frac=0.3)
    ref = {x["ruta"] for x in m["referencia"]}
    q = [x["ruta"] for x in m["queries"]]
    assert not (set(q) & ref)                       # ninguna query en referencia
    assert len(ref) + len(q) == 10
    assert Counter(x["persona_real"] for x in m["referencia"]) == {"Ana": 3, "Beto": 3}
    assert Counter(x["persona_real"] for x in m["queries"]) == {"Ana": 2, "Beto": 2}
    assert m["resumen"]["n_insuficientes"] == 0


def test_particion_ordena_por_ts_y_no_solapa():
    fotos = list(reversed(_fotos(10, 4)))  # desordenadas
    m = be.construir_manifiesto(fotos, ETIQUETAS, test_frac=0.5)
    ref = [x for x in m["referencia"] if x["persona_real"] == "Ana"]
    q = [x for x in m["queries"] if x["persona_real"] == "Ana"]
    assert len(ref) == 2 and len(q) == 2
    # referencia = ts bajos, queries = ts altos
    assert max(x["ts"] for x in ref) < min(x["ts"] for x in q)


def test_persona_insuficiente_marcada():
    fotos = _fotos(10, 1) + _fotos(20, 4)
    m = be.construir_manifiesto(fotos, ETIQUETAS, test_frac=0.3)
    assert m["resumen"]["n_insuficientes"] == 1
    assert m["resumen"]["insuficientes"][0]["persona_real"] == "Ana"
    # la foto insuficiente no puede ser query
    assert all(x["persona_real"] != "Ana" for x in m["queries"])


def test_fotos_sin_etiqueta_ignoradas():
    fotos = _fotos(10, 3) + _fotos(999, 3)  # 999 no está en etiquetas
    m = be.construir_manifiesto(fotos, ETIQUETAS, test_frac=0.3)
    assert m["resumen"]["n_sin_etiqueta"] == 3
    assert all(x["persona_real"] == "Ana" for x in m["referencia"] + m["queries"])


# ---------------------------------------------------------------------------
# evaluar
# ---------------------------------------------------------------------------
def _manifest_2p() -> dict:
    fotos = _fotos(10, 5) + _fotos(20, 5)
    return be.construir_manifiesto(fotos, ETIQUETAS, test_frac=0.3)


def test_tar_far_sinteticos():
    m = _manifest_2p()
    embs = {}
    embs.update(_embeddings(0, 10, 5, seed=100))
    embs.update(_embeddings(1, 20, 5, seed=200))
    res = be.evaluar(m, embs, [0.35, 0.5, 0.99])
    for u in (0.35, 0.5, 0.99):
        assert res[u]["tar"] == 1.0
        assert res[u]["far"] == 0.0
        assert res[u]["tar_top1"] == 1.0
        assert res[u]["n_queries"] == 4
        assert res[u]["n_genuinas"] == 4


def test_far_detecta_impostor():
    m = _manifest_2p()
    embs = {}
    embs.update(_embeddings(0, 10, 5, seed=100))
    embs.update(_embeddings(1, 20, 5, seed=200))
    # forzamos una query de Ana a que coincida con la galería de Beto
    q_ana = next(x["ruta"] for x in m["queries"] if x["persona_real"] == "Ana")
    embs[q_ana] = _eje(1)
    res = be.evaluar(m, embs, [0.9])
    assert res[0.9]["far"] > 0.0
    assert res[0.9]["far"] == 0.25  # 1 de 4 queries
    assert res[0.9]["tar"] < 1.0


def test_dup_rate_con_dos_identidades():
    manifest = {
        "version": 1,
        "referencia": [
            {"ruta": "r1", "persona_real": "Ana", "persona_id": 1, "foto_id": "r1"},
            {"ruta": "r2", "persona_real": "Ana", "persona_id": 2, "foto_id": "r2"},
            {"ruta": "r3", "persona_real": "Beto", "persona_id": 3, "foto_id": "r3"},
        ],
        "queries": [
            {"ruta": "q1", "persona_real": "Ana", "foto_id": "q1"},
            {"ruta": "q2", "persona_real": "Ana", "foto_id": "q2"},
            {"ruta": "q3", "persona_real": "Beto", "foto_id": "q3"},
        ],
    }
    embs = {
        "r1": _eje(0), "r2": _eje(1), "r3": _eje(2),
        "q1": _eje(0), "q2": _eje(1), "q3": _eje(2),
    }
    res = be.evaluar(manifest, embs, [0.9])
    assert res[0.9]["tar"] == 1.0
    assert res[0.9]["far"] == 0.0
    # Ana repartida en 2 identidades -> 1 de 2 personas con duplicado
    assert res[0.9]["dup_rate"] == 0.5


def test_dup_rate_none_sin_persona_id():
    manifest = {
        "version": 1,
        "referencia": [{"ruta": "r1", "persona_real": "Ana"}],
        "queries": [{"ruta": "q1", "persona_real": "Ana"}],
    }
    res = be.evaluar(manifest, {"r1": _eje(0), "q1": _eje(0)}, [0.5])
    assert res[0.5]["dup_rate"] is None
    assert res[0.5]["tar"] == 1.0


def test_embeddings_faltantes_se_cuentan():
    manifest = {
        "version": 1,
        "referencia": [{"ruta": "r1", "persona_real": "Ana", "persona_id": 1}],
        "queries": [
            {"ruta": "q1", "persona_real": "Ana"},
            {"ruta": "q2", "persona_real": "Ana"},  # sin embedding
        ],
    }
    res = be.evaluar(manifest, {"r1": _eje(0), "q1": _eje(0)}, [0.9])
    assert res[0.9]["n_queries"] == 1
    assert res[0.9]["n_sin_embedding"] == 1


def test_manifest_vacio_no_explota():
    res = be.evaluar({"referencia": [], "queries": []}, {}, [0.5])
    assert res[0.5]["n_queries"] == 0
    assert res[0.5]["tar"] is None
    assert res[0.5]["far"] is None
