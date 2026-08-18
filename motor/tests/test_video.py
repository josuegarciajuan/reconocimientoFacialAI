"""Tests de motor/core/video.py: compresión H.264, guardado directo y rutas seguras."""
import os

import cv2
import numpy as np
import pytest

from motor.core.video import (
    VideoConfig,
    comprimir_video,
    duracion_video,
    dimensiones_video,
    guardar_video,
    ruta_archivo,
    ruta_video,
)

CFG_FAST = VideoConfig(crf=28, preset="ultrafast", fps=10, gop=10)
W, H, N, FPS = 160, 120, 20, 10


def _frame(i):
    f = np.zeros((H, W, 3), dtype=np.uint8)
    cv2.rectangle(f, (10 + i * 3, 30), (40 + i * 3, 70), (255, 255, 255), -1)
    return f


@pytest.fixture()
def avi_origen(tmp_path):
    """AVI XVID sintético (equivalente al que genera guarda_movimientosV3.py)."""
    src = str(tmp_path / "cam_2026-08-18_10:00:00.123456.avi")
    out = cv2.VideoWriter(src, cv2.VideoWriter_fourcc(*"XVID"), FPS, (W, H))
    assert out.isOpened()
    for i in range(N):
        out.write(_frame(i))
    out.release()
    return src


def test_comprimir_video_mp4_legible_y_duracion_preservada(avi_origen, tmp_path):
    dst = str(tmp_path / "mov.mp4")
    peso = comprimir_video(avi_origen, dst, CFG_FAST)
    assert peso is not None and peso > 0
    # la duración se conserva aunque baje de fps (velocidad natural)
    assert duracion_video(dst) == pytest.approx(N / FPS, abs=0.2)
    w, h = dimensiones_video(dst)
    assert (w, h) == (W, H)
    # el MP4 se puede releer frame a frame
    cap = cv2.VideoCapture(dst)
    assert cap.isOpened()
    n = 0
    while True:
        ok, _ = cap.read()
        if not ok:
            break
        n += 1
    cap.release()
    assert n >= N - 2  # tolerancia al remuestreo de fps


def test_comprimir_video_fuente_inexistente(tmp_path):
    assert comprimir_video(str(tmp_path / "noexiste.avi"), str(tmp_path / "x.mp4"), CFG_FAST) is None


def test_guardar_video_directo_mp4(tmp_path):
    dst = str(tmp_path / "directo.mp4")
    peso = guardar_video([_frame(i) for i in range(N)], dst, FPS, (W, H), CFG_FAST)
    assert peso is not None and peso > 0
    assert duracion_video(dst) == pytest.approx(N / FPS, abs=0.2)


def test_duracion_video_inexistente():
    assert duracion_video("/no/existe.mp4") == 0.0
    assert dimensiones_video("/no/existe.mp4") == (0, 0)


def test_rutas_archivo(tmp_path):
    d = ruta_archivo(str(tmp_path), 1, 18, "mov.mp4")
    assert d.endswith(os.path.join("motor", "videos_archivo", "1", "18", "mov.mp4"))
    assert os.path.isdir(os.path.dirname(d))

    # ruta relativa válida
    rel = os.path.join("motor", "videos_archivo", "1", "18", "mov.mp4")
    assert ruta_video(rel, str(tmp_path)) == os.path.abspath(os.path.join(str(tmp_path), rel))

    # path-traversal rechazado
    assert ruta_video("../../etc/passwd", str(tmp_path)) is None
    assert ruta_video("motor/videos/1/18/mov.avi", str(tmp_path)) is None
