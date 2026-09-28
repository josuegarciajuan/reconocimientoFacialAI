"""Tests de ``audit/calibrar_fino.py`` (sin red, sin BD, sin insightface, sin cv2).

Se ejercita la parte PURA con embeddings sintéticos de 4 dimensiones:

- misma persona con coseno alto (~0.90) y persona distinta ortogonal (cos 0.0),
- TTA por espejo (una query mala que el espejo rescata),
- barrido de umbrales TAR/FAR/FRR, elección por Youden y por FAR<=0.05,
- evaluación LOFO y optimización de la variante ganadora.

La parte de medición (cv2/insightface) no se toca: el módulo la importa de forma
perezosa y no se invoca.
"""
from __future__ import annotations

import json
import math

import numpy as np

from motor.audit import calibrar_fino as cf

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


def _medida(persona: str, frag, foto: str, vec, flip=None, **extra) -> dict:
    m = {
        "persona_real": persona,
        "fragmento": str(frag),
        "foto_id": foto,
        "embedding": vec,
        "flip": flip,
        "lado_cara": 200,
        "sharpness": 150.0,
        "pose": "f",
        "pose_valida": True,
    }
    m.update(extra)
    return m


# ---------------------------------------------------------------------------
# rango_umbrales
# ---------------------------------------------------------------------------
def test_rango_umbrales_incluye_extremos():
    us = cf.rango_umbrales(0.20, 0.70, 0.01)
    assert len(us) == 51
    assert us[0] == 0.20 and us[-1] == 0.70
    assert us == sorted(us)


def test_rango_umbrales_invalidos():
    assert cf.rango_umbrales(0.5, 0.2, 0.01) == []
    assert cf.rango_umbrales(0.2, 0.7, 0.0) == []
    assert cf.rango_umbrales(0.2, 0.7, -0.1) == []


# ---------------------------------------------------------------------------
# score_variantes
# ---------------------------------------------------------------------------
def test_score_variantes_max_top3_centroid():
    M = [_eje(0), _rot(25.0)]
    q = _eje(0)
    res = cf.score_variantes(q, None, M)
    assert abs(res["max"] - 1.0) < 1e-9
    esperado_top3 = (1.0 + math.cos(math.radians(25.0))) / 2.0
    assert abs(res["top3mean"] - esperado_top3) < 1e-9
    # centroide dentro del cono: cos(q, centroid) > cos(q, miembro a 25) y < 1
    assert math.cos(math.radians(12.5)) <= res["centroid"] < 1.0


def test_score_variantes_flipmax_rescata_query_mala():
    M = [_eje(0)]
    q_mala = _eje(1)          # cos 0 con la galería
    q_flip = _eje(0)          # cos 1 con la galería
    res = cf.score_variantes(q_mala, q_flip, M)
    assert res["max"] == 0.0
    assert res["flipmax"] == 1.0
    # sin espejo, flipmax degenera a max
    res_sin = cf.score_variantes(q_mala, None, M)
    assert res_sin["flipmax"] == res_sin["max"] == 0.0


def test_score_variantes_fliptop3_es_max_por_elemento():
    M = [_eje(0), _rot(25.0)]
    q = _eje(1)
    qf = _eje(0)
    res = cf.score_variantes(q, qf, M)
    sims = np.array([0.0, math.sin(math.radians(25.0))])
    sims_f = np.array([1.0, math.cos(math.radians(25.0))])
    esperado = float(np.maximum(sims, sims_f).mean())
    assert abs(res["fliptop3"] - esperado) < 1e-9


def test_score_variantes_flipcentroid():
    M = [_eje(0), _eje(1)]
    q = _eje(0)
    qf = _eje(1)
    res = cf.score_variantes(q, qf, M)
    # q+qf normalizado es la diagonal media; el centroide de G también -> cos 1
    assert abs(res["flipcentroid"] - 1.0) < 1e-9
    # sin espejo, flipcentroid == centroid
    res_sin = cf.score_variantes(q, None, M)
    assert res_sin["flipcentroid"] == res_sin["centroid"]


def test_score_variantes_galeria_vacia_o_dim_incompatible():
    vacio = cf.score_variantes(_eje(0), None, [])
    assert set(vacio) == set(cf.VARIANTES)
    assert all(v == -1.0 for v in vacio.values())
    # galería de dimensión 2 contra query de 4 -> no comparable
    mal = cf.score_variantes(_eje(0), None, [[1.0, 0.0]])
    assert all(v == -1.0 for v in mal.values())


def test_score_variantes_g_flip_no_afecta_a_las_seis_variantes():
    """La API exige G_flip, pero las seis variantes usan TTA solo de query."""
    M = [_eje(0), _rot(25.0)]
    q, qf = _eje(0), _eje(2)
    base = cf.score_variantes(q, qf, M, None)
    otro = cf.score_variantes(q, qf, M, [_eje(3), _eje(1)])
    for v in cf.VARIANTES:
        assert base[v] == otro[v]


def test_score_variantes_acepta_matriz_numpy_y_lista():
    M = np.asarray([_eje(0), _rot(25.0)])
    a = cf.score_variantes(_eje(0), None, M)
    b = cf.score_variantes(_eje(0), None, [_eje(0), _rot(25.0)])
    assert a == b


# ---------------------------------------------------------------------------
# metricas_umbral
# ---------------------------------------------------------------------------
def test_metricas_umbral_tar_far_frr():
    ok = [True, True, False, False]
    scores = [0.8, 0.3, 0.9, 0.2]
    d = cf.metricas_umbral(ok, scores, [0.5])[0.5]
    assert d["tar"] == 0.25          # solo la 1ª genérica >= 0.5
    assert d["far"] == 0.25          # solo la 3ª impostora >= 0.5
    assert d["frr"] == 0.75          # 1 - TAR
    assert d["n_aciertos"] == 1 and d["n_falsos"] == 1
    assert d["n_queries"] == 4


def test_metricas_umbral_monotono():
    ok = [True, True, False, False]
    scores = [0.8, 0.3, 0.9, 0.2]
    us = [0.1, 0.3, 0.5, 0.85, 0.95]
    puntos = cf.metricas_umbral(ok, scores, us)
    tares = [puntos[u]["tar"] for u in us]
    fares = [puntos[u]["far"] for u in us]
    assert tares == sorted(tares, reverse=True)
    assert fares == sorted(fares, reverse=True)
    assert tares[0] == 0.5 and tares[-1] == 0.0


def test_metricas_umbral_sin_datos():
    d = cf.metricas_umbral([], [], [0.5])[0.5]
    assert d["tar"] is None and d["far"] is None and d["frr"] is None
    assert d["n_queries"] == 0


# ---------------------------------------------------------------------------
# elegir_youden / elegir_far_max
# ---------------------------------------------------------------------------
def test_elegir_youden_maximiza_tar_menos_far():
    puntos = {
        0.40: {"tar": 1.0, "far": 0.20},
        0.50: {"tar": 0.90, "far": 0.08},
        0.60: {"tar": 0.80, "far": 0.05},
    }
    y = cf.elegir_youden(puntos)
    assert y["umbral"] == 0.50
    assert abs(y["j"] - 0.82) < 1e-9


def test_elegir_youden_empate_prefiere_umbral_alto():
    puntos = {
        0.50: {"tar": 1.0, "far": 0.0},
        0.80: {"tar": 1.0, "far": 0.0},
    }
    assert cf.elegir_youden(puntos)["umbral"] == 0.80


def test_elegir_youden_sin_datos():
    assert cf.elegir_youden({0.5: {"tar": None, "far": None}}) is None


def test_elegir_far_max_respeta_tope_y_tar_min():
    puntos = {
        0.40: {"tar": 1.0, "far": 0.20},
        0.50: {"tar": 0.90, "far": 0.08},
        0.60: {"tar": 0.80, "far": 0.05},
    }
    p = cf.elegir_far_max(puntos, far_max=0.05)
    assert p["umbral"] == 0.60 and p["tar"] == 0.80
    assert cf.elegir_far_max(puntos, far_max=0.05, tar_min=0.90) is None
    assert cf.elegir_far_max(puntos, far_max=0.01) is None


# ---------------------------------------------------------------------------
# evaluar_medidas (LOFO)
# ---------------------------------------------------------------------------
def _escena_separada():
    """Ana (frags 1,2) y Beto (frags 3,4) en planos ortogonales; cos genuino ~0.906."""
    return [
        _medida("Ana", 1, "a1", _rot(0.0)),
        _medida("Ana", 2, "a2", _rot(25.0)),
        _medida("Beto", 3, "b1", _rot23(0.0)),
        _medida("Beto", 4, "b2", _rot23(25.0)),
    ]


def test_evaluar_medidas_lofo_sin_fuga():
    resultados, n_no_eval = cf.evaluar_medidas(_escena_separada())
    assert n_no_eval == 0
    assert len(resultados) == 4
    for r in resultados:
        gen = r["scores"]["max"]["genuino"]
        assert 0.85 < gen < 0.95          # es el OTRO fragmento, nunca cos 1.0
        imp = r["scores"]["max"]["impostor"]
        assert abs(imp) < 1e-9            # Beto ortogonal
        assert r["scores"]["max"]["top1_correcto"] is True


def test_evaluar_medidas_persona_un_solo_fragmento_no_evaluable():
    medidas = _escena_separada() + [_medida("Solo", 9, "s1", _eje(2))]
    resultados, n_no_eval = cf.evaluar_medidas(medidas)
    assert n_no_eval == 1
    assert {r["persona_real"] for r in resultados} == {"Ana", "Beto"}


def test_evaluar_medidas_medoidmax_diagnostico():
    resultados, _ = cf.evaluar_medidas(_escena_separada())
    r0 = next(r for r in resultados if r["persona_real"] == "Ana")
    # genuino ~0.906 y mejor ajeno 0 -> medoidmax ~0.906
    assert r0["medoidmax"] is not None
    assert abs(r0["medoidmax"] - r0["scores"]["max"]["genuino"]) < 1e-6


# ---------------------------------------------------------------------------
# resumir
# ---------------------------------------------------------------------------
def _resumen_escena(medidas):
    resultados, _ = cf.evaluar_medidas(medidas)
    return cf.resumir(resultados, cf.rango_umbrales(0.20, 0.70, 0.05))


def test_resumir_ganadora_y_tar_090_far_005():
    inf = _resumen_escena(_escena_separada())
    assert inf["n_queries"] == 4
    assert inf["ganadora"] in cf.VARIANTES
    g = inf["por_variante"][inf["ganadora"]]["umbral_youden"]
    assert g["tar"] == 1.0 and g["far"] == 0.0 and g["j"] == 1.0
    assert inf["hay_tar090_far005"]["existe"] is True
    assert inf["hay_tar090_far005"]["variante"] in cf.VARIANTES
    assert inf["hay_tar090_far005"]["tar"] >= 0.90

    # TAR por persona con la ganadora: las dos personas al 100%
    assert inf["por_persona_real"]["Ana"]["tar"] == 1.0
    assert inf["por_persona_real"]["Beto"]["tar"] == 1.0
    assert inf["queries_fallidas"] == []


def test_resumir_confusion_marca_fallo_impostor():
    """Beto tiene una foto idéntica a la cara de Ana -> el top-1 de Ana es incorrecto."""
    medidas = _escena_separada() + [
        _medida("Beto", 5, "b3", _eje(0)),   # clon de la cara de Ana
    ]
    resultados, _ = cf.evaluar_medidas(medidas)
    inf = cf.resumir(resultados, cf.rango_umbrales(0.50, 0.99, 0.01))
    # hay fallos por top-1 incorrecto (el clon de Ana capta el top-1)
    fallidas = inf["queries_fallidas"]
    assert fallidas, "el escenario de confusión debe generar fallos"
    assert any(q["motivo"] == "top1_incorrecto" for q in fallidas)
    confusion = [q for q in fallidas if q["top1"] is not None
                 and q["top1"] != q["persona_real"]]
    assert confusion, "debe haber alguna query cuyo top-1 sea otra persona"
    assert all(q["mejor_impostor"] is not None for q in confusion)


def test_resumir_json_sin_embeddings():
    inf = _resumen_escena(_escena_separada())
    texto = json.dumps(inf, ensure_ascii=False)
    # no se serializan vectores, solo cosenos/umbrales/conteos
    assert '"embedding"' not in texto
    assert '"flip":' not in texto


def test_resumir_sin_queries_no_explota():
    inf = cf.resumir([], [0.5])
    assert inf["n_queries"] == 0
    assert inf["ganadora"] is None
    assert inf["hay_tar090_far005"]["existe"] is False
    for v in cf.VARIANTES:
        assert inf["por_variante"][v]["umbral_youden"] is None


# ---------------------------------------------------------------------------
# utilidades
# ---------------------------------------------------------------------------
def test_a_matriz_normaliza_filas_y_maneja_vacio():
    M = cf._a_matriz([_eje(0), [3.0, 0.0, 0.0, 0.0]])
    assert M.shape == (2, 4)
    assert np.allclose(np.linalg.norm(M, axis=1), 1.0)
    assert cf._a_matriz([]).shape == (0, 0)
    assert cf._a_matriz(_eje(0)).shape == (1, 4)


def test_flip_de_cae_al_nativo():
    m = {"embedding": _eje(0), "flip": None}
    assert cf._flip_de(m) is m["embedding"]
    m2 = {"embedding": _eje(0), "flip": _eje(1)}
    assert cf._flip_de(m2) is m2["flip"]
