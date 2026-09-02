"""Tests de la corrección robusta del clasificador (2026-09-02).

Cubre los defectos estructurales encontrados en producción:
  - C1: dos caras en el mismo crop NO se mezclan (índice de cara preservado).
  - C1/_store_add: solo entran en la galería las caras del sub-clúster.
  - C5: identidad exacta autónoma (no crea duplicados) y conflicto exacto
    (no auto-fusión).
  - P1: dedup persistente (sobrevive a un reinicio del proceso).
  - G2: invariante secure > match aplicado desde el .env.
"""
import json
import os

import numpy as np

from motor.clasificador import (_store_add, split_coherent_clusters,  # noqa: E402
                                _dedup_load, _dedup_record, _dedup_seen)
from motor.core.config import Config  # noqa: E402
from motor.core.matching import cosine, exact_band_persons  # noqa: E402
from motor.core.model import Face  # noqa: E402
from motor.core.store import FaceStore  # noqa: E402


def _e(k: int, noise: float = 0.0, seed: int = 0) -> np.ndarray:
    v = np.zeros(512, dtype=np.float64)
    v[k] = 1.0
    if noise > 0:
        rng = np.random.default_rng(seed)
        v = v + noise * rng.standard_normal(512)
    return v / np.linalg.norm(v)


def _face(emb: np.ndarray) -> Face:
    return Face(bbox=(0, 0, 60, 60), det_score=0.99,
                embedding=emb.astype(np.float32), pose=(0.0, 0.0, 0.0))


def _item(emb_or_faces, idx: int, ts: float = 0.0) -> dict:
    """Item con una cara o varias (mismo crop = 2 detecciones)."""
    faces = emb_or_faces if isinstance(emb_or_faces, list) else [_face(emb_or_faces)]
    img = np.full((30, 30, 3), 128, dtype=np.uint8)
    return {"file": f"cam_2026-09-02_10.00.00.000_00000.avi_{idx}.jpg",
            "path": f"/tmp/fake_cr_{idx}.jpg", "img": img,
            "faces": faces, "ts": float(idx) + ts}


def _face_list(battery):
    return [(f.embedding, idx, fidx)
            for idx, it in enumerate(battery)
            for fidx, f in enumerate(it["faces"])]


# ---------------------------------------------------------------------------
# C1: dos caras en el mismo crop -> sub-clústeres separados y SIN mezcla
# ---------------------------------------------------------------------------

def test_split_mismo_crop_dos_personas_no_mezcla():
    """Crop con dos personas (A y B) + repetición de A: el sub-clustering debe
    separar A (2 muestras) de B (1 muestra) usando el índice de cara exacto."""
    cfg = Config(cluster_confirm=0.60)
    a = _e(0)
    b = _e(1)                     # coseno(a,b) ~0
    assert cosine(a, b) < 0.05
    # battery: item0 con DOS caras (A en fidx0, B en fidx1); item1 con A
    item0 = _item([_face(a), _face(b)], 0)
    item1 = _item(a, 1)
    battery = [item0, item1]
    fl = _face_list(battery)      # [(A,0,0), (B,0,1), (A,1,0)]
    # union-find global con umbral bajo agruparía todo; forzamos cluster global
    subs = split_coherent_clusters([0, 1, 2], fl, battery, cfg)
    # reconstruir miembros por sub-clúster y comprobar coherencia interna
    assert len(subs) == 2, f"deben salir 2 sub-clústeres: {subs}"
    for s in subs:
        embs = [fl[i][0] for i in s]
        # todos los miembros confirman contra el representativo
        rep = embs[0]
        assert all(cosine(e, rep) >= cfg.cluster_confirm - 1e-9 for e in embs)
    # A (indices globales 0 y 2) nunca comparte sub-clúster con B (índice 1)
    for s in subs:
        assert not ({0, 2} <= set(s) and 1 in s), f"mezcla A+B en {s}"


def test_store_add_solo_caras_del_subcluster(tmp_path):
    """C1: _store_add con el sub-clúster de A NO puede enrolar la cara de B
    aunque B esté en el mismo item/crop."""
    cfg = Config(admission_cosine=0.50)
    store = FaceStore(str(tmp_path / "face_enc_v2"), max_per_person=50)
    a = _e(0)
    b = _e(1)
    battery = [_item([_face(a), _face(b)], 0)]     # mismo crop: A y B
    fl = _face_list(battery)                        # [(A,0,0),(B,0,1)]
    # sub-clúster SOLO de A (global index 0)
    _store_add(store, "A", [fl[0]], battery, cfg, new_person=True)
    assert store.count("A") == 1
    # el encoding guardado es el de A, no el de B
    enc = store.person_encodings("A")[0]
    assert cosine(enc, a) > 0.99
    assert cosine(enc, b) < 0.05


# ---------------------------------------------------------------------------
# C5: identidad exacta autónoma
# ---------------------------------------------------------------------------

def test_exact_band_un_candidato(tmp_path):
    cfg = Config(exact_match_cos=0.999)
    store = FaceStore(str(tmp_path / "face_enc_v2"), max_per_person=50)
    store.add("P1", [_e(0, noise=0.01, seed=1)], [80.0], ["f"])
    q = store.person_encodings("P1")[0].copy()      # idéntico al enrolado
    persons, best = exact_band_persons([q], store, cfg.exact_match_cos)
    assert persons == ["P1"]
    assert best >= 0.999


def test_exact_band_conflicto_no_auto_fusion(tmp_path):
    """Mismo embedding idéntico en 2 personas (contaminación): la banda exacta
    devuelve 2 candidatos -> el llamador no debe fusionar (conflicto)."""
    cfg = Config(exact_match_cos=0.999)
    store = FaceStore(str(tmp_path / "face_enc_v2"), max_per_person=50)
    shared = _e(5, noise=0.001, seed=1)
    store.add("P1", [shared.copy()], [80.0], ["f"])
    store.add("P2", [shared.copy()], [80.0], ["f"])
    persons, best = exact_band_persons([shared], store, cfg.exact_match_cos)
    assert len(persons) == 2
    assert best >= 0.999


# ---------------------------------------------------------------------------
# P1: dedup persistente (sobrevive a reinicio)
# ---------------------------------------------------------------------------

def test_dedup_persistente_sobrevive_reinicio(tmp_path):
    ruta = str(tmp_path)
    cfg = Config(dedup_dir="motor/dedup", dedup_window_hours=72.0)
    local = "1"
    # primera "vida" del proceso
    assert _dedup_seen(ruta, local, cfg, "hash_abc") is False
    _dedup_record(ruta, local, cfg, "hash_abc", "stem_1", "cam17")
    # simular reinicio: memoria vacía, recarga desde fichero
    from motor import clasificador as C
    C._DEDUP_MEM.clear()
    C._DEDUP_TS.clear()
    _dedup_load(ruta, local, cfg)
    assert _dedup_seen(ruta, local, cfg, "hash_abc") is True


# ---------------------------------------------------------------------------
# G2: invariante secure > match
# ---------------------------------------------------------------------------

def test_config_invariante_secure_mayor_match(tmp_path):
    """Si el .env define secure < match, from_env lo corrige (secure >= match+0.03).
    Producción llegó a correr secure=0.45 < match=0.48 (inconsistente)."""
    env = tmp_path / ".env"
    env.write_text("RF_MATCH_THRESHOLD=0.48\nRF_SECURE_THRESHOLD=0.45\n",
                   encoding="utf-8")
    cfg = Config.from_env(str(tmp_path))
    assert cfg.match_threshold == 0.48
    assert cfg.secure_threshold >= cfg.match_threshold + 0.03
