"""Tests del orquestador de vídeo troceado — motor/video_orchestrator.py (P1).

Solo los helpers puros (sin canal distribuido, sin BD, sin modelos): contrato de
parámetros, id de ejecución, lectura de frames y decodificación del tar de crops.
"""
from __future__ import annotations

import base64
import io
import os
import re
import tarfile

import cv2
import numpy as np

from motor import video_orchestrator as vo


def _video(path, n=20, fps=10.0):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    w = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (64, 64))
    for i in range(n):
        w.write(((i % 256) * np.ones((64, 64, 3))).astype("uint8"))
    w.release()


def test_exec_id_valido_y_determinista():
    a = vo._exec_id("1", "9", "9_2026-01-01_10:00:00.000000.mp4")
    b = vo._exec_id("1", "9", "9_2026-01-01_10:00:00.000000.mp4")
    c = vo._exec_id("1", "9", "otro.mp4")
    assert a == b
    assert a != c
    assert re.match(r"^[A-Za-z0-9._-]{1,64}$", a)


def test_frame_info(tmp_path):
    p = os.path.join(str(tmp_path), "v.mp4")
    _video(p, n=20, fps=10.0)
    total, fps = vo.frame_info(p)
    assert total == 20
    assert abs(fps - 10.0) < 0.6


def test_build_params_segmenta_por_segundos(tmp_path, monkeypatch):
    ruta = str(tmp_path)
    fichero = "9_2026-01-01_10:00:00.000000.mp4"
    _video(os.path.join(ruta, "motor", "videos", "1", "9", fichero), n=50, fps=10.0)
    monkeypatch.setattr(vo, "lineas_payload", lambda cam: [{"id": "5"}])
    monkeypatch.setenv("RF_DIST_SEGMENT_SEC", "1")   # 1 s @10fps = 10 frames/seg
    params = vo.build_params("1", "9", fichero, ruta)
    assert params["total_frames"] == 50
    assert params["segment_frames"] == 10
    assert params["home_path"] == os.path.join(ruta, "motor", "videos", "1", "9", fichero)
    assert params["lineas"] == [{"id": "5"}]


def test_decode_crops_extrae_layout(tmp_path):
    # tar con motor/caras/sinclasificar/1/9/x.png dentro
    rel = "motor/caras/sinclasificar/1/9/abc.png"
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tf:
        data = b"PNGDATA"
        info = tarfile.TarInfo(rel)
        info.size = len(data)
        tf.addfile(info, io.BytesIO(data))
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    dest = str(tmp_path)
    assert vo.decode_crops(b64, dest) is True
    assert os.path.isfile(os.path.join(dest, rel))


def test_decode_crops_vacio_ok(tmp_path):
    assert vo.decode_crops("", str(tmp_path)) is True


def test_result_of_desempaqueta_el_resumen():
    # El canal devuelve el resumen de ejecución; el combinado va en `result`.
    assert vo.result_of({"status": "done", "result": {"frames": 94}}) == {"frames": 94}
    # Ejecución fallida o sin resultado -> None (para caer al fallback).
    assert vo.result_of({"status": "failed", "result": None}) is None
    assert vo.result_of({"status": "running", "result": {"x": 1}}) is None
    # Formato ya combinado (pruebas) -> tal cual.
    assert vo.result_of({"frames": 94}) == {"frames": 94}
    assert vo.result_of(None) is None
