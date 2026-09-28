"""Tests de ``audit/verificar_cara_a_cara.py`` (sin red, sin BD, sin modelos).

Se ejercita la parte PURA con embeddings sintéticos de 4 dimensiones:
misma persona con coseno ~0.9, persona distinta ortogonal (cos 0.0), y dos casos
de guardia (información/pose) y umbral inferior a ``match_threshold``.

La parte de medición (cv2/insightface) no se toca aquí: el módulo la importa de
forma perezosa y no se invoca.
"""
from __future__ import annotations

import math

import numpy as np

from motor.audit import verificar_cara_a_cara as vc
from motor.core.config import Config

DIM = 4


def _u(v) -> np.ndarray:
    """Normaliza un vector a norma 1."""
    a = np.asarray(v, dtype=np.float64)
    n = float(np.linalg.norm(a))
    return a / n if n > 0.0 else a


def _eje(i: int) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float64)
    v[i] = 1.0
    return v


def _rot(deg: float) -> np.ndarray:
    """Vector unitario en el plano (e0, e1) a ``deg`` grados de e0."""
    r = math.radians(deg)
    return _u([math.cos(r), math.sin(r), 0.0, 0.0])


def _rot23(deg: float) -> np.ndarray:
    """Vector unitario en el plano (e2, e3); ortogonal a ``_rot`` (cos 0.0)."""
    r = math.radians(deg)
    return _u([0.0, 0.0, math.cos(r), math.sin(r)])


def _escena():
    """Galerías de 2 personas x 2 fragmentos, cada query con la cara de su fragmento.

    ``f1``/``f2`` (Ana) distan 25° -> cos genuino ~0.906 (>= secure 0.55).
    ``g1``/``g2`` (Beto) ídem en el plano ortogonal -> impostor cos 0.0.
    """
    a1, a2 = _rot(0.0), _rot(25.0)
    b1, b2 = _rot23(0.0), _rot23(25.0)
    galerias = {
        "Ana": [("f1", a1), ("f2", a2)],
        "Beto": [("g1", b1), ("g2", b2)],
    }
    queries = [
        {"persona_real": "Ana", "fragmento": "f1", "foto_id": "a1", "vector": a1,
         "lado_cara": 200.0, "sharpness": 150.0, "pose_valida": True, "pose": "f"},
        {"persona_real": "Ana", "fragmento": "f2", "foto_id": "a2", "vector": a2,
         "lado_cara": 200.0, "sharpness": 150.0, "pose_valida": True, "pose": "f"},
        {"persona_real": "Beto", "fragmento": "g1", "foto_id": "b1", "vector": b1,
         "lado_cara": 200.0, "sharpness": 150.0, "pose_valida": True, "pose": "f"},
        {"persona_real": "Beto", "fragmento": "g2", "foto_id": "b2", "vector": b2,
         "lado_cara": 200.0, "sharpness": 150.0, "pose_valida": True, "pose": "f"},
    ]
    return galerias, queries


# ---------------------------------------------------------------------------
# evaluar_queries: LOFO + cascada actual
# ---------------------------------------------------------------------------
def test_evaluar_queries_tar_1_far_0():
    galerias, queries = _escena()
    res = vc.evaluar_queries(galerias, queries, Config())
    assert len(res) == 4
    for r in res:
        assert r["evaluable"] is True
        assert r["resultado_actual"] == "match"
        assert r["resultado_cara"] == "match"
        assert r["acierto"] is True
        assert r["falso_match"] is False
        assert r["top1"] == r["persona_real"]
    # leave-one-fragment-out: el genuino es el OTRO fragmento, nunca cos 1.0
    for r in res:
        assert 0.85 <= float(r["genuino"]) <= 0.95
        assert float(r["impostor"]) <= 0.01


def test_resumen_tar_uno_far_cero():
    galerias, queries = _escena()
    res = vc.evaluar_queries(galerias, queries, Config())
    inf = vc.resumen(res, galerias, Config())
    g = inf["global"]
    assert g["tar"] == 1.0
    assert g["far"] == 0.0
    assert g["n_evaluables"] == 4
    assert g["n_falsos_match"] == 0
    assert g["n_provisional"] == 0 and g["n_uncertain"] == 0 and g["n_new"] == 0
    assert "SÍ" in g["conclusion"]

    ana = inf["por_persona_real"]["Ana"]
    assert ana["n_fragmentos"] == 2
    assert ana["tar"] == 1.0
    assert ana["n_aciertos"] == 2

    cos = inf["cosenos"]
    assert cos["genuino"]["n"] == 4
    assert cos["genuino"]["mediana"] > 0.85
    assert cos["n_genuinos_ge_match"] == 4
    assert cos["n_impostores_ge_match"] == 0
    # sin pares impostores por encima del umbral, la matriz está vacía o baja
    assert all(p["max_cos"] <= 0.01 for p in inf["pares_cara_a_cara"])


# ---------------------------------------------------------------------------
# evaluar_queries: umbral inferior -> "new"; guardia -> "provisional"
# ---------------------------------------------------------------------------
def _query_cos_bajo(lado: float = 200.0) -> dict:
    """Query de Ana con coseno genuino 0.4 (por debajo de match 0.48)."""
    return {
        "persona_real": "Ana", "fragmento": "f2", "foto_id": "a2",
        "vector": _u([0.4, math.sqrt(1.0 - 0.4 * 0.4), 0.0, 0.0]),
        "lado_cara": lado, "sharpness": 150.0, "pose_valida": True, "pose": "f",
    }


def test_cos_bajo_queda_en_new():
    galerias = {"Ana": [("f1", _eje(0))]}
    res = vc.evaluar_queries(galerias, [_query_cos_bajo(200.0)], Config())
    r = res[0]
    assert abs(float(r["genuino"]) - 0.4) < 1e-6
    assert r["resultado_cara"] == "new"
    assert r["resultado_actual"] == "new"
    assert r["acierto"] is False


def test_lado_menor_que_guardia_queda_provisional():
    galerias = {"Ana": [("f1", _eje(0))]}
    res = vc.evaluar_queries(galerias, [_query_cos_bajo(50.0)], Config())
    r = res[0]
    # cos 0.4 sería "new", pero la guardia de tamaño manda: no decide.
    assert r["resultado_actual"] == "provisional"
    assert r["acierto"] is False


def test_pose_invalida_queda_provisional_aunque_cos_alto():
    galerias, queries = _escena()
    q = dict(queries[0])
    q["pose_valida"] = False
    res = vc.evaluar_queries(galerias, [q], Config())
    assert res[0]["resultado_actual"] == "provisional"


def test_banda_match_secure_es_uncertain():
    """Genuino en [match, secure) sin capas de apoyo -> uncertain, nunca match."""
    cfg = Config()
    # cos objetivo ~0.50: vector a acos(0.5)=60° de la galería de Ana.
    galerias = {"Ana": [("f1", _eje(0))]}
    q = {"persona_real": "Ana", "fragmento": "f2", "foto_id": "a2",
         "vector": _rot(60.0), "lado_cara": 200.0, "sharpness": 150.0,
         "pose_valida": True, "pose": "f"}
    r = vc.evaluar_queries(galerias, [q], cfg)[0]
    assert abs(float(r["genuino"]) - 0.5) < 1e-6
    assert r["resultado_actual"] == "uncertain"
    assert r["acierto"] is False


# ---------------------------------------------------------------------------
# Agrupación y cap
# ---------------------------------------------------------------------------
def _medida(persona: str, frag: str, foto: str, vec, ts: float = 0.0) -> dict:
    return {"persona_real": persona, "fragmento": frag, "foto_id": foto,
            "embedding": vec, "lado_cara": 200, "sharpness": 150.0,
            "pose": "f", "pose_valida": True, "ts": ts}


def test_construir_galerias_solo_query_si_multifragmento():
    medidas = [
        _medida("Ana", "f1", "a1", _eje(0), 0.0),
        _medida("Ana", "f2", "a2", _eje(1), 1.0),
        _medida("Solo", "s1", "s1", _eje(2), 0.0),
    ]
    galerias, queries = vc.construir_galerias_y_queries(medidas)
    assert set(galerias) == {"Ana", "Solo"}
    assert len(queries) == 2                      # Solo tiene 1 fragmento -> sin query
    assert {q["persona_real"] for q in queries} == {"Ana"}


def test_limitar_por_persona_reparte_entre_fragmentos():
    fotos = []
    for frag in ("f1", "f2"):
        for i in range(5):
            fotos.append({"persona_real": "Ana", "fragmento": frag,
                          "foto_id": f"{frag}_{i}", "ts": float(i)})
    sel = vc.limitar_por_persona(fotos, 4)
    assert len(sel) == 4
    frags = [f["fragmento"] for f in sel]
    assert frags.count("f1") == 2 and frags.count("f2") == 2   # round-robin
    # determinista
    assert [f["foto_id"] for f in sel] == [
        f["foto_id"] for f in vc.limitar_por_persona(fotos, 4)
    ]
    assert vc.limitar_por_persona(fotos, 0) == []


# ---------------------------------------------------------------------------
# utilidades puras
# ---------------------------------------------------------------------------
def test_stats_y_pct():
    st = vc._stats([0.1, 0.2, 0.3, 0.4])
    assert st["n"] == 4
    assert st["mediana"] is not None
    assert vc._pct(1, 4) == 0.25
    assert vc._pct(1, 0) is None
    assert vc._stats([None, None])["n"] == 0
