"""Tests del troceado por rango de frames — motor/procesa_video.py (P1).

Verifican la semántica del rango (`--from`/`--to`) SIN cargar modelos: se
sustituyen `analyze` y `PersonDetector` por stubs y se usa un vídeo sintético
sin caras. El índice de frame es ABSOLUTO, de modo que dos segmentos contiguos
cubren el vídeo exactamente y los `ts` son consistentes con una pasada completa.
"""
from __future__ import annotations

import os

import cv2
import numpy as np
import pytest

from motor import procesa_video as pv


class _NoPersonas:
    def process(self, frame):  # noqa: ANN001
        return []


@pytest.fixture()
def video_sintetico(tmp_path):
    """Crea <ruta>/motor/videos/1/9/<fichero>.mp4 con 20 frames y sin caras."""
    ruta = str(tmp_path)
    cam_dir = os.path.join(ruta, "motor", "videos", "1", "9")
    os.makedirs(cam_dir, exist_ok=True)
    fichero = "9_2026-01-01_10:00:00.000000.mp4"
    path = os.path.join(cam_dir, fichero)
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (64, 64))
    for i in range(20):
        w.write(((i % 256) * np.ones((64, 64, 3), dtype="uint8")).astype("uint8"))
    w.release()
    return ruta, fichero


def _stub(monkeypatch):
    monkeypatch.setattr(pv, "analyze", lambda *a, **k: [])
    monkeypatch.setattr(pv, "PersonDetector", lambda *a, **k: _NoPersonas())


def test_rango_cubre_segmento_exacto(video_sintetico, monkeypatch):
    ruta, fichero = video_sintetico
    _stub(monkeypatch)
    cfg = pv.Config()
    resumen: dict = {}
    n = pv.process_video("1", "9", fichero, ruta, cfg, face_every=2, lineas=[],
                         efectos=False, eventos=[], resumen=resumen,
                         frame_ini=3, frame_fin=8)
    assert n == 5
    assert resumen["frames"] == 5
    assert resumen["frame_ini"] == 3
    assert resumen["frame_fin"] == 8


def test_dos_segmentos_cubren_el_video(video_sintetico, monkeypatch):
    ruta, fichero = video_sintetico
    _stub(monkeypatch)
    cfg = pv.Config()
    r1: dict = {}
    r2: dict = {}
    a = pv.process_video("1", "9", fichero, ruta, cfg, face_every=2, lineas=[],
                         efectos=False, eventos=[], resumen=r1, frame_ini=0, frame_fin=8)
    b = pv.process_video("1", "9", fichero, ruta, cfg, face_every=2, lineas=[],
                         efectos=False, eventos=[], resumen=r2, frame_ini=8, frame_fin=None)
    assert a == 8
    assert b == 12
    assert r1["frame_fin"] == r2["frame_ini"] == 8
    assert a + b == 20  # cobertura exacta, sin solape ni hueco


def test_pasada_completa_sigue_funcionando(video_sintetico, monkeypatch):
    ruta, fichero = video_sintetico
    _stub(monkeypatch)
    cfg = pv.Config()
    resumen: dict = {}
    n = pv.process_video("1", "9", fichero, ruta, cfg, face_every=2, lineas=[],
                         efectos=False, eventos=[], resumen=resumen)
    assert n == 20
    assert resumen["frame_ini"] == 0
    assert resumen["frame_fin"] == 20
