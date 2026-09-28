"""Tests de audit/auditar_identidades.py (sin red ni BD).

Store sintético: persona real A con 3 fragmentos (A3 totalmente contaminado con
encodings de B) y persona real B con 2 fragmentos, más un cod sin etiquetar.
"""
from __future__ import annotations

import pickle

import numpy as np
import pytest

from motor.audit import auditar_identidades as ai

DIM = 16


def _unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def _eje(i: int, dim: int = DIM) -> np.ndarray:
    v = np.zeros(dim, dtype=np.float64)
    v[i] = 1.0
    return v


def _cerca(base: np.ndarray, rng: np.random.Generator, jitter: float = 0.05) -> np.ndarray:
    return _unit(base + jitter * rng.standard_normal(base.shape))


def _store_sintetico() -> dict:
    """A (A1,A2 sanos + A3 contaminado con B) y B (B1,B2); Z9 sin etiquetar."""
    rng = np.random.default_rng(20260928)
    e0, e1, e2 = _eje(0), _eje(1), _eje(2)
    persons = {
        "A1": [_cerca(e0, rng) for _ in range(4)],
        "A2": [_cerca(e0, rng) for _ in range(3)],
        "A3": [_cerca(e1, rng) for _ in range(3)],   # contaminado: encodings de B
        "B1": [_cerca(e1, rng) for _ in range(3)],
        "B2": [_cerca(e1, rng) for _ in range(2)],
        "Z9": [_cerca(e2, rng) for _ in range(1)],   # sin etiqueta
    }
    return {
        "version": 4,
        "schema": "face_enc_v2",
        "persons": {
            cod: {
                "encodings": list(encs),
                "quality": [90.0] * len(encs),
                "poses": ["f"] * len(encs),
                "sources": [f"src_{cod}_{i}" for i in range(len(encs))],
            }
            for cod, encs in persons.items()
        },
    }


ETIQUETAS_RAW = [
    {"id": 1, "cod_interno": "A1", "persona": "Ana"},
    {"id": 11, "cod_interno": "A1", "persona": "Ana"},
    {"id": 2, "cod_interno": "A2", "persona": "Ana"},
    {"id": 3, "cod_interno": "A3", "persona": "Ana"},
    {"id": 4, "cod_interno": "B1", "persona": "Beto"},
    {"id": 5, "cod_interno": "B2", "persona": "Beto"},
]


def _matrices(store: dict) -> dict[str, np.ndarray]:
    return {cod: np.asarray(p["encodings"], dtype=np.float64)
            for cod, p in store["persons"].items()}


def _dump(store: dict, path) -> None:
    with open(path, "wb") as fh:
        pickle.dump(store, fh)


# ---------------------------------------------------------------------------
# Carga de etiquetas
# ---------------------------------------------------------------------------
def test_parsear_etiquetas_multiples_ids(tmp_path):
    id2cod, realof, clusters = ai.parsear_etiquetas(ETIQUETAS_RAW)
    assert id2cod[11] == "A1" and id2cod[1] == "A1"
    assert realof["A3"] == "Ana"
    assert clusters["Ana"] == ["A1", "A2", "A3"]
    assert clusters["Beto"] == ["B1", "B2"]


def test_cargar_etiquetas_fichero(tmp_path):
    p = tmp_path / "etiquetas.json"
    p.write_text(
        '[{"id": 7, "cod_interno": "X", "persona": "Pepe"}]', encoding="utf-8"
    )
    id2cod, realof, clusters = ai.cargar_etiquetas(str(p))
    assert id2cod == {7: "X"} and realof == {"X": "Pepe"}
    assert clusters == {"Pepe": ["X"]}


def test_cargar_etiquetas_ausente():
    assert ai.cargar_etiquetas("/no/existe.json") == ({}, {}, {})
    assert ai.parsear_etiquetas(None) == ({}, {}, {})


# ---------------------------------------------------------------------------
# carga de store
# ---------------------------------------------------------------------------
def test_cargar_store_ausente():
    assert ai.cargar_store("/no/existe.pkl")["persons"] == {}


def test_cargar_store_fichero_vacio(tmp_path):
    p = tmp_path / "vacio.pkl"
    p.write_bytes(b"")
    assert ai.cargar_store(str(p))["persons"] == {}


def test_cargar_store_schema_incorrecto(tmp_path):
    p = tmp_path / "otro.pkl"
    _dump({"version": 1, "schema": "otra_cosa", "persons": {}}, p)
    with pytest.raises(ValueError):
        ai.cargar_store(str(p))


# ---------------------------------------------------------------------------
# nearest_external
# ---------------------------------------------------------------------------
def test_nearest_external_excluye_el_propio_cod():
    store = _store_sintetico()
    mats = _matrices(store)
    _, realof, _ = ai.parsear_etiquetas(ETIQUETAS_RAW)
    best_cos, best_cod = ai.nearest_external(mats["A1"], "A1", realof, mats)
    assert len(best_cod) == mats["A1"].shape[0]
    assert all(c != "A1" for c in best_cod)
    assert all(c is not None for c in best_cod)
    assert np.isfinite(best_cos).all()


def test_nearest_external_sin_otros_cods():
    M = np.eye(4)
    best_cos, best_cod = ai.nearest_external(M, "solo", {}, {})
    assert np.all(best_cos == -np.inf)
    assert all(c is None for c in best_cod)


# ---------------------------------------------------------------------------
# informe
# ---------------------------------------------------------------------------
def _informe() -> dict:
    store = _store_sintetico()
    etiquetas = ai.parsear_etiquetas(ETIQUETAS_RAW)
    return ai.informe(store, etiquetas, max_per_person=4)


def test_resumen():
    inf = _informe()
    r = inf["resumen"]
    assert r["n_personas"] == 6
    assert r["n_encodings_total"] == 16
    assert r["n_con_1_encoding"] == 1          # Z9
    assert r["n_en_tope"] == 1                 # A1 (4 >= 4)
    assert r["n_sin_etiquetar"] == 1           # Z9
    assert "Z9" not in inf["por_persona_real"]


def test_fragmentacion_por_persona_real():
    inf = _informe()
    a = inf["por_persona_real"]["Ana"]
    assert a["n_fragmentos"] == 3
    assert a["n_encodings"] == 10
    assert set(a["fragmentos"]) == {"A1", "A2", "A3"}
    # pares A1-A2 (alto), A1-A3 y A2-A3 (contaminados, bajos)
    pares = a["pares"]
    assert pares["n"] == 3
    assert pares["mejor_coseno"]["max"] > 0.9
    assert pares["mejor_coseno"]["min"] < 0.35
    for u in ("0.35", "0.48", "0.55"):
        assert pares["bajo_umbral"][u] == 2
    b = inf["por_persona_real"]["Beto"]
    assert b["n_fragmentos"] == 2
    assert b["n_encodings"] == 5


def test_deteccion_contaminacion():
    inf = _informe()
    hig = inf["higiene_por_cod"]
    assert hig["A3"]["votos_contaminacion"] == 3        # todos sus encodings son de B
    assert hig["A1"]["votos_contaminacion"] == 0        # su vecino externo es A2/A3 (misma persona)
    assert hig["A3"]["vecino_externo"]["persona_real"] == "Beto"
    assert hig["A3"]["vecino_externo"]["cos"] > 0.9
    assert hig["A1"]["en_tope"] is True
    assert hig["A2"]["en_tope"] is False


def test_top_impostor():
    inf = _informe()
    imp = inf["impostores"]
    assert imp, "debe haber al menos un par impostor"
    top = imp[0]
    assert {top["persona_a"], top["persona_b"]} == {"Ana", "Beto"}
    assert top["cos"] > 0.9
    # A3 (contaminado) debe aparecer en el top
    assert "A3" in {top["cod_a"], top["cod_b"]}
    # los pares van ordenados de mayor a menor
    coss = [x["cos"] for x in imp]
    assert coss == sorted(coss, reverse=True)


def test_informe_store_vacio():
    inf = ai.informe(ai._store_vacio(), None)
    assert inf["resumen"]["n_personas"] == 0
    assert inf["por_persona_real"] == {}
    assert inf["impostores"] == []
    assert inf["higiene_por_cod"] == {}


def test_informe_json_serializable():
    import json

    inf = _informe()
    # no debe fallar ni contener NaN/Inf
    txt = json.dumps(inf, ensure_ascii=False)
    assert "NaN" not in txt and "Infinity" not in txt


# ---------------------------------------------------------------------------
# read-only
# ---------------------------------------------------------------------------
def test_no_modifica_el_store(tmp_path):
    path = tmp_path / "face_enc_v2.pkl"
    _dump(_store_sintetico(), path)
    antes = path.read_bytes()

    store = ai.cargar_store(str(path))
    inf = ai.informe(store, ai.parsear_etiquetas(ETIQUETAS_RAW))
    assert inf["resumen"]["n_personas"] == 6

    assert path.read_bytes() == antes
    assert not (tmp_path / "face_enc_v2.pkl.lock").exists()
    assert not (tmp_path / "face_enc_v2.pkl.tmp").exists()
