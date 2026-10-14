"""Tests de la detección en dos niveles (P3) — motor/procesa_video.py::_detect_faces.

Sin modelos: `analyze` se sustituye por un doble que registra el `det_size`
usado y devuelve caras prefijadas. Verifican que con la opción OFF no cambia
nada y que con ON solo se paga la pasada completa cuando la barata ve cara.
"""
from __future__ import annotations

import numpy as np

from motor import procesa_video as pv
from motor.core.config import Config

FRAME = np.zeros((64, 64, 3), dtype="uint8")


class _Recorder:
    def __init__(self, cheap_faces, full_faces):
        self.cheap_faces = cheap_faces
        self.full_faces = full_faces
        self.calls = []

    def __call__(self, img, det_size=(640, 640), min_score=0.5):
        self.calls.append(tuple(det_size))
        if det_size[0] < 1280:
            return self.cheap_faces
        return self.full_faces


def test_off_una_sola_pasada_completa(monkeypatch):
    rec = _Recorder(cheap_faces=[object()], full_faces=[object(), object()])
    monkeypatch.setattr(pv, "analyze", rec)
    cfg = Config()
    cfg.two_stage_det = False
    out = pv._detect_faces(FRAME, cfg)
    assert rec.calls == [(cfg.det_size, cfg.det_size)]
    assert len(out) == 2


def test_on_sin_cara_en_barata_no_paga_la_completa(monkeypatch):
    rec = _Recorder(cheap_faces=[], full_faces=[object()])
    monkeypatch.setattr(pv, "analyze", rec)
    cfg = Config()
    cfg.two_stage_det = True
    cfg.two_stage_det_size = 640
    out = pv._detect_faces(FRAME, cfg)
    assert rec.calls == [(640, 640)]      # la completa NO se ejecuta
    assert out == []


def test_on_con_cara_en_barata_ejecuta_la_completa(monkeypatch):
    rec = _Recorder(cheap_faces=[object()], full_faces=[object(), object(), object()])
    monkeypatch.setattr(pv, "analyze", rec)
    cfg = Config()
    cfg.two_stage_det = True
    cfg.two_stage_det_size = 640
    out = pv._detect_faces(FRAME, cfg)
    assert rec.calls == [(640, 640), (cfg.det_size, cfg.det_size)]
    assert len(out) == 3
