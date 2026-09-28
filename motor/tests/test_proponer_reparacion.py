"""Tests de ``reparacion/proponer_reparacion.py`` (SOLO LECTURA, sin red ni BD).

Escenario sintético:

- Persona real **Ana** fragmentada en A1 (4 encodings), A2 (3) y A3 (2). A3
  co-ocurre con A1 y A2 (par bloqueado) -> queda **excluida** de la fusión.
- Persona real **Beto** con una galería B1 que contiene 2 encodings propios
  (e1) y 1 intruso de Ana (e0, con proveniencia ``contam_1``).
- A1/A2 son muy cohesivos entre sí (jitter pequeño) para que el intruso no
  arrastre falsos positivos en la dirección contraria.
"""
from __future__ import annotations

import json
import pickle

import numpy as np

from motor.reparacion import proponer_reparacion as pr

DIM = 16


def _unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def _eje(i: int, dim: int = DIM) -> np.ndarray:
    v = np.zeros(dim, dtype=np.float64)
    v[i] = 1.0
    return v


def _cerca(base: np.ndarray, rng: np.random.Generator, jitter: float) -> np.ndarray:
    return _unit(base + jitter * rng.standard_normal(base.shape))


def _store_sintetico() -> dict:
    """Dict face_enc_v2 con Ana fragmentada (A3 bloqueada) y Beto contaminado."""
    rng = np.random.default_rng(20260928)
    e0, e1 = _eje(0), _eje(1)
    persons = {
        "A1": [_cerca(e0, rng, 0.004) for _ in range(4)],
        "A2": [_cerca(e0, rng, 0.004) for _ in range(3)],
        "A3": [_cerca(e0, rng, 0.004) for _ in range(2)],
        "B1": [_cerca(e1, rng, 0.02) for _ in range(2)] + [_cerca(e0, rng, 0.09)],
    }
    sources = {
        "A1": [f"a1_{i}" for i in range(4)],
        "A2": [f"a2_{i}" for i in range(3)],
        "A3": [f"a3_{i}" for i in range(2)],
        "B1": ["b1_0", "b1_1", "contam_1"],
    }
    return {
        "version": 4,
        "schema": "face_enc_v2",
        "persons": {
            cod: {
                "encodings": list(encs),
                "quality": [90.0] * len(encs),
                "poses": ["f"] * len(encs),
                "added_at": [1.0] * len(encs),
                "sources": list(sources[cod]),
                "sil": [None] * len(encs),
            }
            for cod, encs in persons.items()
        },
    }


ETIQUETAS_RAW = [
    {"id": 1, "cod_interno": "A1", "persona": "Ana"},
    {"id": 2, "cod_interno": "A2", "persona": "Ana"},
    {"id": 3, "cod_interno": "A3", "persona": "Ana"},
    {"id": 4, "cod_interno": "B1", "persona": "Beto"},
]

# A3 co-ocurre con A1 y A2 -> personas distintas -> no puede fusionarse.
BLOQUEADOS = [["A1", "A3"], ["A2", "A3"]]


def _dump(store: dict, path) -> None:
    with open(path, "wb") as fh:
        pickle.dump(store, fh)


def _etiquetas():
    return pr.normalizar_etiquetas(ETIQUETAS_RAW)


# ---------------------------------------------------------------------------
# Normalización de bloqueados
# ---------------------------------------------------------------------------
def test_normalizar_bloqueados():
    b = pr._normalizar_bloqueados([["A", "B"], ["B", "A"], ("C", "D"), ["E", "E"], None])
    assert b == {frozenset(("A", "B")), frozenset(("C", "D"))}
    assert pr._normalizar_bloqueados(None) == set()


def test_cargar_bloqueados(tmp_path):
    p = tmp_path / "bloq.json"
    p.write_text(json.dumps([["X", "Y"]]), encoding="utf-8")
    assert pr._cargar_bloqueados(str(p)) == {frozenset(("X", "Y"))}
    assert pr._cargar_bloqueados(str(tmp_path / "nada.json")) == set()


# ---------------------------------------------------------------------------
# Fusiones
# ---------------------------------------------------------------------------
def test_proponer_merges_destino_y_fuentes():
    store = _store_sintetico()
    merges = pr.proponer_merges(store, _etiquetas(), BLOQUEADOS)
    assert len(merges) == 1
    m = merges[0]
    assert m["persona"] == "Ana"
    assert m["destino"] == "A1"                 # 4 encodings (el mayor)
    assert m["cods_fuente"] == ["A2"]
    assert m["n_encodings"] == 7


def test_proponer_merges_excluye_bloqueado():
    store = _store_sintetico()
    merges = pr.proponer_merges(store, _etiquetas(), BLOQUEADOS)
    m = merges[0]
    excluidos = [e["cod"] for e in m["excluidos"]]
    assert excluidos == ["A3"]
    # el excluido nunca aparece como fuente ni como destino
    assert "A3" not in m["cods_fuente"] and m["destino"] != "A3"


def test_proponer_merges_cohesion_alta():
    store = _store_sintetico()
    m = pr.proponer_merges(store, _etiquetas(), BLOQUEADOS)[0]
    assert m["cohesion"]["max"] > 0.99
    assert m["cohesion"]["mediana"] > 0.99
    assert m["cohesion"]["n_pares"] == 1


def test_proponer_merges_reparte_en_componentes():
    """Dos pares bloqueados -> dos componentes (no se excluye a nadie)."""
    rng = np.random.default_rng(7)
    e0 = _eje(0)
    persons = {
        cod: [_cerca(e0, rng, 0.004) for _ in range(n)]
        for cod, n in (("A1", 4), ("A2", 3), ("A3", 2), ("A4", 1))
    }
    store = {"version": 4, "schema": "face_enc_v2",
             "persons": {c: {"encodings": v} for c, v in persons.items()}}
    etiquetas = [{"id": i + 1, "cod_interno": c, "persona": "Ana"} for i, c in enumerate(persons)]
    merges = pr.proponer_merges(store, etiquetas, [["A1", "A2"], ["A3", "A4"]])
    pares = {(m["destino"], tuple(m["cods_fuente"])) for m in merges}
    assert pares == {("A1", ("A3",)), ("A2", ("A4",))}
    assert all(not m["excluidos"] for m in merges)


# ---------------------------------------------------------------------------
# Contaminación
# ---------------------------------------------------------------------------
def test_proponer_contaminacion_detecta_con_source():
    store = _store_sintetico()
    contams = pr.proponer_contaminacion(store, _etiquetas(), contam_min_cos=0.45)
    grupos = [g for g in contams if g["cod_origen"] == "B1"]
    assert len(grupos) == 1
    g = grupos[0]
    assert g["persona_destino"] == "Ana"
    assert g["destino_cod"] == "A1"
    assert g["accion"] == "mover"
    assert g["n"] == 1 and g["n_sin_fuente"] == 0
    e = g["encodings"][0]
    assert e["source"] == "contam_1"
    assert e["cos"] >= 0.45
    assert e["vecino_cod"] in {"A1", "A2", "A3"}


def test_proponer_contaminacion_no_marca_a_ana():
    """Los fragmentos de Ana no deben aparecer como contaminados por Beto."""
    store = _store_sintetico()
    contams = pr.proponer_contaminacion(store, _etiquetas(), contam_min_cos=0.45)
    assert all(g["cod_origen"] not in {"A1", "A2"} for g in contams)


def test_proponer_contaminacion_sin_fuente():
    """Un encoding contaminado sin ``source`` se reporta en ``sin_fuente``."""
    rng = np.random.default_rng(3)
    e0, e1 = _eje(0), _eje(1)
    store = {"version": 4, "schema": "face_enc_v2", "persons": {
        "C1": {"encodings": [_cerca(e0, rng, 0.004) for _ in range(3)],
               "sources": ["c0", "c1", "c2"]},
        "D1": {"encodings": [_cerca(e1, rng, 0.02), _cerca(e0, rng, 0.09)],
               "sources": ["d0", None]},
    }}
    etiquetas = [
        {"id": 1, "cod_interno": "C1", "persona": "Carla"},
        {"id": 2, "cod_interno": "D1", "persona": "Dora"},
    ]
    contams = pr.proponer_contaminacion(store, etiquetas, contam_min_cos=0.45)
    g = [x for x in contams if x["cod_origen"] == "D1"][0]
    assert g["persona_destino"] == "Carla"
    assert g["destino_cod"] == "C1"
    assert g["n_sin_fuente"] == 1
    assert g["sin_fuente"][0]["source"] is None
    assert g["sin_fuente"][0]["idx"] == 1


def test_proponer_contaminacion_persona_desconocida_purga():
    """Vecino externo sin etiqueta -> acción purgar (sin cod destino)."""
    rng = np.random.default_rng(11)
    e0, e1 = _eje(0), _eje(1)
    store = {"version": 4, "schema": "face_enc_v2", "persons": {
        "E1": {"encodings": [_cerca(e1, rng, 0.02), _cerca(e0, rng, 0.09)],
               "sources": ["e0", "e_contam"]},
        "Z9": {"encodings": [_cerca(e0, rng, 0.004) for _ in range(3)],
               "sources": [None, None, None]},
    }}
    etiquetas = [{"id": 1, "cod_interno": "E1", "persona": "Eva"}]
    contams = pr.proponer_contaminacion(store, etiquetas, contam_min_cos=0.45)
    g = [x for x in contams if x["cod_origen"] == "E1"][0]
    assert g["persona_destino"] is None
    assert g["destino_cod"] is None
    assert g["accion"] == "purgar"


# ---------------------------------------------------------------------------
# Propuesta completa + JSON-safe
# ---------------------------------------------------------------------------
def test_construir_propuesta_resumen_y_json():
    store = _store_sintetico()
    prop = pr.construir_propuesta(store, ETIQUETAS_RAW, BLOQUEADOS,
                                  merge_min_cos=0.9, contam_min_cos=0.45)
    assert set(prop) == {"merges", "contaminaciones", "resumen"}
    r = prop["resumen"]
    assert r["n_merges"] == 1
    assert r["n_excluidos"] == 1
    assert r["n_encodings_movibles"] == 1
    assert prop["merges"][0]["cohesion_ok"] is True
    txt = json.dumps(prop, ensure_ascii=False)
    assert "NaN" not in txt and "Infinity" not in txt


def test_construir_propuesta_vacia():
    store = {"version": 4, "schema": "face_enc_v2", "persons": {}}
    prop = pr.construir_propuesta(store, [], None)
    assert prop["merges"] == [] and prop["contaminaciones"] == []
    assert prop["resumen"]["n_merges"] == 0


# ---------------------------------------------------------------------------
# Read-only: bytes del store invariantes
# ---------------------------------------------------------------------------
def test_proponer_no_modifica_el_store(tmp_path):
    path = tmp_path / "face_enc_v2"
    _dump(_store_sintetico(), path)
    antes = path.read_bytes()

    store = pr.cargar_store(str(path))
    etiquetas = pr.cargar_etiquetas(_dump_etiquetas(tmp_path))
    prop = pr.construir_propuesta(store, etiquetas, BLOQUEADOS)

    assert prop["resumen"]["n_merges"] == 1
    assert path.read_bytes() == antes
    assert not (tmp_path / "face_enc_v2.lock").exists()
    assert not (tmp_path / "face_enc_v2.tmp").exists()


def _dump_etiquetas(tmp_path) -> str:
    p = tmp_path / "etiquetas.json"
    p.write_text(json.dumps(ETIQUETAS_RAW), encoding="utf-8")
    return str(p)


def test_cli_json_no_escribe(tmp_path, capsys):
    path = tmp_path / "face_enc_v2"
    _dump(_store_sintetico(), path)
    etq = _dump_etiquetas(tmp_path)
    bloq = tmp_path / "bloq.json"
    bloq.write_text(json.dumps(BLOQUEADOS), encoding="utf-8")
    antes = path.read_bytes()

    rc = pr.main(["--store", str(path), "--etiquetas", etq,
                  "--bloqueados", str(bloq), "--json"])
    assert rc == 0
    salida = json.loads(capsys.readouterr().out)
    assert salida["resumen"]["n_merges"] == 1
    assert path.read_bytes() == antes
