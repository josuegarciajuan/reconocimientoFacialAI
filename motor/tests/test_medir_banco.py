"""Tests de ``audit/medir_banco.py`` (sin red, sin BD, sin insightface).

Toda la parte medida se prueba con embeddings sintéticos de 4 dimensiones:
mismo sujeto con coseno ~0.9-1.0, impostor con coseno ~0.1, y un escenario
"contaminado" para observar la caída de TAR/FAR al subir el umbral.
"""
from __future__ import annotations

import math

import numpy as np

from motor.audit import medir_banco as mb

DIM = 4

ETIQUETAS = [
    {"id": 10, "cod_interno": "A", "persona": "Ana"},
    {"id": 20, "cod_interno": "B", "persona": "Beto"},
]

#: fuga entre las dos identidades: genera impostores con coseno ~0.1.
C = 0.1


def _u(v) -> np.ndarray:
    """Normaliza un vector a norma 1 (los embeddings reales ya vienen L2)."""
    a = np.asarray(v, dtype=np.float64)
    n = float(np.linalg.norm(a))
    return a / n if n > 0 else a


def _eje(i: int) -> np.ndarray:
    v = np.zeros(DIM, dtype=np.float64)
    v[i] = 1.0
    return v


def _ana(deg: float) -> np.ndarray:
    """Vector unitario en el plano (e0, e1) a ``deg`` grados de e0."""
    r = math.radians(deg)
    return _u([math.cos(r), math.sin(r), 0, 0])


def _beto(deg: float) -> np.ndarray:
    """Vector unitario en el plano (e2, e3) con fuga ``C`` en e0 (impostor ~0.1)."""
    r = math.radians(deg)
    s = math.sqrt(1 - C * C)
    return _u([C, 0, s * math.cos(r), s * math.sin(r)])


def _escena(contaminar: bool = False):
    """Escena sintética de 2 personas x 4 fotos (2 referencia + 2 query).

    Referencias a 0° y 50°, queries a ±25°: el mejor coseno genuino queda en
    ~0.90 (nunca 1.0 por coincidencia exacta) y el impostor en ~0.10.
    Devuelve ``(fotos, embeddings_por_ruta)``. ``ts`` 0-1 -> referencia,
    2-3 -> query (respeta la partición de ``construir_manifiesto``).
    """
    rA1, rA2 = _ana(0), _ana(50)
    qA1, qA2 = _ana(25), _ana(-25)
    rB1, rB2 = _beto(0), _beto(50)
    qB1, qB2 = _beto(25), _beto(-25)

    vecs = {
        "rA1": rA1, "rA2": rA2, "qA1": qA1, "qA2": qA2,
        "rB1": rB1, "rB2": rB2, "qB1": qB1, "qB2": qB2,
    }
    if contaminar:
        # Query de Ana con imax=0.6 (aceptada por umbrales bajos) y gmax~0.65.
        vecs["qA1"] = _u(0.6 * rB1 + 0.8 * _eje(1))

    fotos: list[dict] = []
    for pid, refs, queries in (
        (10, ["rA1", "rA2"], ["qA1", "qA2"]),
        (20, ["rB1", "rB2"], ["qB1", "qB2"]),
    ):
        for i, nombre in enumerate(refs):
            fotos.append({"foto_id": nombre, "persona_id": pid, "ruta": nombre,
                          "ts": float(i), "cam": "c1"})
        for i, nombre in enumerate(queries):
            fotos.append({"foto_id": nombre, "persona_id": pid, "ruta": nombre,
                          "ts": float(2 + i), "cam": "c1"})
    return fotos, vecs


# ---------------------------------------------------------------------------
# Manifiesto / partición
# ---------------------------------------------------------------------------
def test_particion_sin_leakage_con_construir_manifiesto():
    fotos, _ = _escena()
    m = mb.construir_manifiesto(fotos, ETIQUETAS, test_frac=0.3)
    ref = {x["ruta"] for x in m["referencia"]}
    q = [x["ruta"] for x in m["queries"]]
    assert not (set(q) & ref)                     # ninguna query está en referencia
    assert len(ref) == 4 and len(q) == 4
    assert {x["persona_real"] for x in m["queries"]} == {"Ana", "Beto"}


# ---------------------------------------------------------------------------
# Muestreo
# ---------------------------------------------------------------------------
def test_muestreo_round_robin_determinista():
    fotos = []
    for pid in (10, 20, 30):
        for i in range(5):
            fotos.append({"foto_id": f"f{pid}_{i}", "persona_id": pid, "ruta": f"r{pid}_{i}",
                          "ts": float(i), "cam": "c"})
    s1 = mb.muestrear(fotos, 7)
    s2 = mb.muestrear(fotos, 7)
    assert [f["foto_id"] for f in s1] == [f["foto_id"] for f in s2]
    assert len(s1) == 7
    # reparto equilibrado: round-robin -> 3,2,2 (diferencia <= 1)
    from collections import Counter
    cuenta = Counter(f["persona_id"] for f in s1)
    assert max(cuenta.values()) - min(cuenta.values()) <= 1
    # dentro de cada persona, las elegidas van en orden creciente de ts
    for pid in (10, 20, 30):
        ts = [f["ts"] for f in s1 if f["persona_id"] == pid]
        assert ts == sorted(ts)


def test_muestreo_cap_mayor_que_total():
    fotos = [{"foto_id": f"x{i}", "persona_id": 10, "ruta": f"x{i}",
              "ts": float(i), "cam": "c"} for i in range(3)]
    assert len(mb.muestrear(fotos, 10)) == 3
    assert mb.muestrear(fotos, 0) == []


# ---------------------------------------------------------------------------
# Umbrales y fecha
# ---------------------------------------------------------------------------
def test_parsear_umbrales_limpia_y_ordena():
    assert mb.parsear_umbrales("0.5, 0.3 ,x,0.5,,0.8") == [0.3, 0.5, 0.8]
    assert mb.parsear_umbrales([0.9, 0.1]) == [0.1, 0.9]
    assert mb.parsear_umbrales("") == []


def test_epoch_maneja_null_y_formato():
    assert mb._epoch("2026-08-17 12:00:00") > 0.0
    assert mb._epoch("NULL") == 0.0
    assert mb._epoch(None) == 0.0
    assert mb._epoch("no-es-fecha") == 0.0


# ---------------------------------------------------------------------------
# curva()
# ---------------------------------------------------------------------------
def test_curva_tar_alto_far_bajo_en_umbral_bajo_medio():
    fotos, embs = _escena()
    manifest = mb.construir_manifiesto(fotos, ETIQUETAS, 0.3)
    c = mb.curva(embs, manifest, [0.3, 0.5, 0.8, 0.95])
    for u in (0.3, 0.5, 0.8):
        assert c["puntos"][u]["tar"] == 1.0
        assert c["puntos"][u]["far"] == 0.0
        assert c["puntos"][u]["gap"] == 1.0
    # con genuinos ~0.9, un umbral 0.95 rechaza todo
    assert c["puntos"][0.95]["tar"] == 0.0
    assert c["puntos"][0.95]["far"] == 0.0


def test_curva_tar_y_far_no_crecen_al_subir_umbral():
    """Al subir el umbral, TAR y FAR son no crecientes (curva ROC).

    Nota: subir el umbral exige ``cos >= u``, así que FAR *no puede* subir; el
    contraste natural es TAR cae / FRR (= 1 - TAR) sube. El escenario
    contaminado incluye una impostora aceptada a umbrales bajos para ver la
    caída estricta de FAR.
    """
    fotos, embs = _escena(contaminar=True)
    manifest = mb.construir_manifiesto(fotos, ETIQUETAS, 0.3)
    us = [0.3, 0.5, 0.8, 0.95]
    c = mb.curva(embs, manifest, us)
    tares = [c["puntos"][u]["tar"] for u in us]
    fares = [c["puntos"][u]["far"] for u in us]
    frrs = [c["puntos"][u]["frr"] for u in us]
    assert tares == sorted(tares, reverse=True)   # no creciente
    assert fares == sorted(fares, reverse=True)   # no creciente
    assert frrs == sorted(frrs)                   # FRR = 1 - TAR sí sube
    assert tares[0] > tares[-1]                   # TAR cae de verdad
    assert fares[0] > fares[2]                    # FAR cae de 0.25 a 0.0
    assert frrs[0] < frrs[-1]


def test_curva_manifiesto_vacio_no_explota():
    c = mb.curva({}, {"referencia": [], "queries": []}, [0.5])
    assert c["puntos"][0.5]["tar"] is None
    assert c["puntos"][0.5]["far"] is None
    assert c["puntos"][0.5]["gap"] is None
    assert c["umbral_equilibrado"] is None


# ---------------------------------------------------------------------------
# umbral equilibrado
# ---------------------------------------------------------------------------
def test_elegir_equilibrado_respeta_far_max():
    puntos = {
        0.40: {"tar": 1.0, "far": 0.20, "gap": 0.80},   # mejor gap pero far alto
        0.50: {"tar": 0.9, "far": 0.08, "gap": 0.82},
        0.60: {"tar": 0.8, "far": 0.05, "gap": 0.75},
    }
    assert mb.elegir_equilibrado(puntos, far_max=0.10) == 0.50


def test_elegir_equilibrado_fallback_sin_elegibles():
    puntos = {
        0.30: {"tar": 1.0, "far": 0.50, "gap": 0.90},
        0.40: {"tar": 0.7, "far": 0.40, "gap": 0.70},
    }
    # ninguno cumple far<=0.10 -> se cae al de mayor gap
    assert mb.elegir_equilibrado(puntos, far_max=0.10) == 0.30


def test_elegir_equilibrado_empate_prefiere_umbral_alto():
    puntos = {
        0.50: {"tar": 1.0, "far": 0.0, "gap": 1.0},
        0.80: {"tar": 1.0, "far": 0.0, "gap": 1.0},
    }
    assert mb.elegir_equilibrado(puntos, far_max=0.10) == 0.80


def test_curva_umbral_equilibrado():
    fotos, embs = _escena()
    manifest = mb.construir_manifiesto(fotos, ETIQUETAS, 0.3)
    c = mb.curva(embs, manifest, [0.3, 0.5, 0.8, 0.95])
    eq = c["umbral_equilibrado"]
    assert eq is not None
    assert c["puntos"][eq]["far"] <= c["far_max_equilibrado"]
    assert c["puntos"][eq]["gap"] == max(
        p["gap"] for u, p in c["puntos"].items()
        if p["far"] is not None and p["far"] <= c["far_max_equilibrado"]
    )
