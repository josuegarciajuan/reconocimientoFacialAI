"""Tests de ``reparacion/aplicar_reparacion.py`` (sin BD, sin red).

Escenario: store ``face_enc_v2`` real en ``tmp_path`` con Ana fragmentada
(A1/A2 fusionables, A3 bloqueada) y Beto (B1) con un encoding contaminado de Ana
que tiene proveniencia ``contam_1``. La propuesta se genera con el propio
proponedor (integración real), no a mano.

Cubre: dry-run no cambia bytes ni crea backup; ``--si`` fusiona, mueve por
source, mueve carpetas y escribe backup + journal; omisión de sources
compartidos; propuesta vacía.
"""
from __future__ import annotations

import json
import os

import numpy as np

from motor.core.store import FaceStore
from motor.reparacion import aplicar_reparacion as ap
from motor.reparacion import proponer_reparacion as pr

DIM = 32
LOCAL = "1"


def _unit(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n > 0 else v


def _eje(i: int, dim: int = DIM) -> np.ndarray:
    v = np.zeros(dim, dtype=np.float64)
    v[i] = 1.0
    return v


def _cerca(base: np.ndarray, rng: np.random.Generator, jitter: float) -> np.ndarray:
    return _unit(base + jitter * rng.standard_normal(base.shape))


def _store_path(ruta: str) -> str:
    return os.path.join(ruta, "motor", "bbdd_reconocimiento", LOCAL, "face_enc_v2")


def _add(store: FaceStore, cod: str, embs, sources) -> None:
    store.add(cod, [np.asarray(e, dtype=np.float32) for e in embs],
              [90.0] * len(embs), ["f"] * len(embs), sources=sources)


def _construir_store(ruta: str, shared_source: bool = False) -> FaceStore:
    """Store con Ana (A1,A2,A3) y Beto (B1 con intruso de Ana)."""
    path = _store_path(ruta)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    store = FaceStore(path, max_per_person=500)
    rng = np.random.default_rng(20260928)
    e0, e1 = _eje(0), _eje(1)
    _add(store, "A1", [_cerca(e0, rng, 0.004) for _ in range(4)],
         [f"a1_{i}" for i in range(4)])
    _add(store, "A2", [_cerca(e0, rng, 0.004) for _ in range(3)],
         [f"a2_{i}" for i in range(3)])
    _add(store, "A3", [_cerca(e0, rng, 0.004) for _ in range(2)],
         [f"a3_{i}" for i in range(2)])
    if shared_source:
        # el source del intruso también etiqueta un encoding legítimo de Beto
        _add(store, "B1",
             [_cerca(e1, rng, 0.02), _cerca(e0, rng, 0.09), _cerca(e1, rng, 0.02)],
             ["shared", "shared", "b1_ok"])
    else:
        _add(store, "B1",
             [_cerca(e1, rng, 0.02), _cerca(e0, rng, 0.09)],
             ["b1_0", "contam_1"])
    return store


ETIQUETAS = [
    {"id": 1, "cod_interno": "A1", "persona": "Ana"},
    {"id": 2, "cod_interno": "A2", "persona": "Ana"},
    {"id": 3, "cod_interno": "A3", "persona": "Ana"},
    {"id": 4, "cod_interno": "B1", "persona": "Beto"},
]
BLOQUEADOS = [["A1", "A3"], ["A2", "A3"]]


def _propuesta(tmp_path, ruta: str, store: FaceStore, shared: bool = False) -> str:
    prop = pr.construir_propuesta(store, ETIQUETAS, BLOQUEADOS,
                                  merge_min_cos=0.9, contam_min_cos=0.45)
    p = tmp_path / "propuesta.json"
    p.write_text(json.dumps(prop), encoding="utf-8")
    return str(p)


def _backup_dirs(ruta: str) -> list[str]:
    base = os.path.join(ruta, "motor", "backups", "reparacion")
    if not os.path.isdir(base):
        return []
    return [os.path.join(base, d) for d in os.listdir(base)]


# ---------------------------------------------------------------------------
# Dry-run
# ---------------------------------------------------------------------------
def test_dry_run_no_cambia_bytes_ni_crea_backup(tmp_path, capsys):
    ruta = str(tmp_path)
    store = _construir_store(ruta)
    prop_path = _propuesta(tmp_path, ruta, store)
    path = _store_path(ruta)
    antes = open(path, "rb").read()

    rc = ap.main(["--propuesta", prop_path, "--ruta", ruta, "--local", LOCAL, "--dry-run"])
    assert rc == 0
    salida = capsys.readouterr().out
    assert "MERGE" in salida and "MOVE" in salida
    assert open(path, "rb").read() == antes
    assert _backup_dirs(ruta) == []
    assert not os.path.exists(path + ".tmp")


def test_sin_si_es_dry_run(tmp_path):
    ruta = str(tmp_path)
    store = _construir_store(ruta)
    prop_path = _propuesta(tmp_path, ruta, store)
    path = _store_path(ruta)
    antes = open(path, "rb").read()

    # sin --si ni --dry-run -> dry-run por defecto
    rc = ap.main(["--propuesta", prop_path, "--ruta", ruta, "--local", LOCAL])
    assert rc == 0
    assert open(path, "rb").read() == antes


# ---------------------------------------------------------------------------
# Aplicación real
# ---------------------------------------------------------------------------
def test_si_fusiona_mueve_y_respalda(tmp_path, capsys):
    ruta = str(tmp_path)
    store = _construir_store(ruta)
    # carpetas a mover
    cam = tmp_path / "motor" / "caras" / LOCAL / "camX"
    (cam / "A2").mkdir(parents=True)
    (cam / "A2" / "x.jpg").write_bytes(b"x")
    port = tmp_path / "motor" / "portraits" / LOCAL / "A2"
    port.mkdir(parents=True)
    (port / "p.jpg").write_bytes(b"p")

    prop_path = _propuesta(tmp_path, ruta, store)
    rc = ap.main(["--propuesta", prop_path, "--ruta", ruta, "--local", LOCAL, "--si"])
    assert rc == 0
    capsys.readouterr()

    s2 = FaceStore(_store_path(ruta))
    assert s2.person("A2") is None
    assert s2.count("A1") == 8          # 4 + 3 fusionados + 1 contaminado movido
    assert s2.count("A3") == 2          # excluida: intacta
    assert s2.count("B1") == 1          # se fue el intruso
    assert s2.person_sources("B1") == ["b1_0"]

    # carpetas movidas
    assert (cam / "A1" / "x.jpg").exists() and not (cam / "A2").exists()
    assert (tmp_path / "motor" / "portraits" / LOCAL / "A1" / "p.jpg").exists()

    # backup + journal
    dirs = _backup_dirs(ruta)
    assert len(dirs) == 1
    assert os.path.exists(os.path.join(dirs[0], "face_enc_v2.bak"))
    jpath = os.path.join(dirs[0], "journal.jsonl")
    assert os.path.exists(jpath)
    entradas = [json.loads(l) for l in open(jpath, encoding="utf-8") if l.strip()]
    ops = [e.get("op") for e in entradas]
    assert "inicio" in ops and "fin" in ops
    assert all(e.get("resultado") == "ok" for e in entradas
               if e.get("tipo") in {"merge", "move_source"})
    assert entradas[-1]["verificacion"]["ok"] is True
    # rollback documentado
    assert any("rollback_store" in e for e in entradas if e.get("op") == "inicio")


def test_source_compartido_se_omite(tmp_path, capsys):
    """Un source que etiqueta encodings no contaminados no se mueve."""
    ruta = str(tmp_path)
    store = _construir_store(ruta, shared_source=True)
    prop_path = _propuesta(tmp_path, ruta, store, shared=True)
    # el grupo contaminado debe tener source 'shared'
    prop = json.load(open(prop_path, encoding="utf-8"))
    grupo = [g for g in prop["contaminaciones"] if g["cod_origen"] == "B1"][0]
    assert grupo["encodings"][0]["source"] == "shared"

    rc = ap.main(["--propuesta", prop_path, "--ruta", ruta, "--local", LOCAL, "--si"])
    assert rc == 0
    capsys.readouterr()

    s2 = FaceStore(_store_path(ruta))
    # merge sí; el move del source compartido se omite -> B1 conserva sus 3
    assert s2.count("A1") == 7
    assert s2.count("B1") == 3
    assert "shared" in (s2.person_sources("B1") or [])

    dirs = _backup_dirs(ruta)
    entradas = [json.loads(l) for l in open(os.path.join(dirs[0], "journal.jsonl"),
                                            encoding="utf-8") if l.strip()]
    assert any(e.get("resultado") == "omitido_source_compartido" for e in entradas)


# ---------------------------------------------------------------------------
# Propuesta vacía
# ---------------------------------------------------------------------------
def test_propuesta_vacia_no_toca_nada(tmp_path):
    ruta = str(tmp_path)
    _construir_store(ruta)
    path = _store_path(ruta)
    antes = open(path, "rb").read()

    res = ap.aplicar_propuesta({}, ruta, LOCAL, aplicar=True, usar_db=False)
    assert res["aplicado"] is False
    assert res["motivo"] == "propuesta_vacia"
    assert open(path, "rb").read() == antes
    assert _backup_dirs(ruta) == []


# ---------------------------------------------------------------------------
# Remapeo del origen contaminado cuando su galería se fusiona con otra
# ---------------------------------------------------------------------------
def _construir_store_b2(ruta: str) -> FaceStore:
    """Beto repartido en B1(3) y B2(2, con el intruso de Ana); Ana fragmentada."""
    path = _store_path(ruta)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    store = FaceStore(path, max_per_person=500)
    rng = np.random.default_rng(5)
    e0, e1 = _eje(0), _eje(1)
    _add(store, "A1", [_cerca(e0, rng, 0.004) for _ in range(4)],
         [f"a1_{i}" for i in range(4)])
    _add(store, "A2", [_cerca(e0, rng, 0.004) for _ in range(3)],
         [f"a2_{i}" for i in range(3)])
    _add(store, "A3", [_cerca(e0, rng, 0.004) for _ in range(2)],
         [f"a3_{i}" for i in range(2)])
    _add(store, "B1", [_cerca(e1, rng, 0.02) for _ in range(3)],
         [f"b1_{i}" for i in range(3)])
    _add(store, "B2", [_cerca(e1, rng, 0.02), _cerca(e0, rng, 0.09)],
         ["b2_0", "contam_2"])
    return store


ETIQUETAS_B2 = ETIQUETAS + [{"id": 5, "cod_interno": "B2", "persona": "Beto"}]


def test_remapea_origen_contaminado_tras_merge(tmp_path, capsys):
    ruta = str(tmp_path)
    store = _construir_store_b2(ruta)
    prop = pr.construir_propuesta(store, ETIQUETAS_B2, BLOQUEADOS,
                                  merge_min_cos=0.9, contam_min_cos=0.45)
    # la contaminación se detecta en B2 (antes de fusionarse con B1)
    assert any(g["cod_origen"] == "B2" and g["destino_cod"] == "A1"
               for g in prop["contaminaciones"])
    p = tmp_path / "prop.json"
    p.write_text(json.dumps(prop), encoding="utf-8")

    rc = ap.main(["--propuesta", str(p), "--ruta", ruta, "--local", LOCAL, "--si"])
    assert rc == 0
    capsys.readouterr()

    s2 = FaceStore(_store_path(ruta))
    assert s2.person("B2") is None
    assert s2.count("A1") == 8          # merge Ana + intruso de B2 (remapeado a B1)
    assert s2.count("B1") == 4          # 3 + 2 de B2 - 1 intruso movido
    assert s2.person_sources("B1") == [f"b1_{i}" for i in range(3)] + ["b2_0"]


def test_dry_run_de_propuesta_da_plan_esperado(tmp_path):
    ruta = str(tmp_path)
    store = _construir_store(ruta)
    prop = pr.construir_propuesta(store, ETIQUETAS, BLOQUEADOS,
                                  merge_min_cos=0.9, contam_min_cos=0.45)
    res = ap.aplicar_propuesta(prop, ruta, LOCAL, aplicar=False, log=lambda *_: None)
    tipos = [o["tipo"] for o in res["ops"]]
    assert tipos == ["merge", "move_source"]
    mv = [o for o in res["ops"] if o["tipo"] == "move_source"][0]
    assert mv["src"] == "B1" and mv["dst"] == "A1" and mv["source"] == "contam_1"
