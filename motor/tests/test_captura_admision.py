"""Tests de la separación captura/admisión (Fase 2) — motor/clasificador._store_add.

Verifica que una cara de baja calidad (marcada low_quality) SÍ se enrola al crear
una persona nueva/provisional (para poder reconciliarla), mientras que en el flujo
normal una cara por debajo de `face_min_side` NO entra en la galería (higiene).
"""
from __future__ import annotations

import numpy as np

from motor.clasificador import _store_add
from motor.core.config import Config
from motor.core.model import Face
from motor.core.store import FaceStore


def _face(bbox, emb):
    return Face(bbox=bbox, det_score=0.9,
                embedding=np.asarray(emb, dtype=np.float32), pose=(0.0, 0.0, 0.0))


def _store(tmp_path):
    return FaceStore(str(tmp_path / "face_enc_v2"))


def _cfg():
    cfg = Config()
    cfg.face_min_side = 52
    cfg.zones_enabled = False
    return cfg


def test_low_quality_enrola_cara_pequena(tmp_path):
    cfg = _cfg()
    store = _store(tmp_path)
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    f = _face((10, 10, 30, 30), [1.0, 0.0, 0.0])   # lado 20 < 52
    battery = [{"img": img, "faces": [f]}]
    members = [(f.embedding, 0, 0)]

    _store_add(store, "p_low", members, battery, cfg,
               new_person=True, foto_id="x", low_quality=True)
    assert store.count("p_low") == 1


def test_normal_no_enrola_cara_pequena(tmp_path):
    cfg = _cfg()
    store = _store(tmp_path)
    img = np.zeros((100, 100, 3), dtype=np.uint8)
    f = _face((10, 10, 30, 30), [1.0, 0.0, 0.0])   # lado 20 < 52
    battery = [{"img": img, "faces": [f]}]
    members = [(f.embedding, 0, 0)]

    _store_add(store, "p_normal", members, battery, cfg, new_person=True)
    assert store.count("p_normal") == 0
