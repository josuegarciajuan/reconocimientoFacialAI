"""Tests de motor/core/video.py: compresión H.264, guardado directo, escritor
por streaming, remux, poster y rutas seguras."""
import os

import cv2
import numpy as np
import pytest

from motor.core.video import (
    H264VideoWriter,
    VideoConfig,
    comprimir_video,
    duracion_video,
    dimensiones_video,
    extraer_poster,
    guardar_video,
    remux_video,
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


def test_h264_writer_streaming_mp4(tmp_path):
    """El escritor por streaming (guarda_movimientosV3.py) produce un MP4 legible
    de duración conservada, sin AVI intermedio."""
    dst = str(tmp_path / "stream.mp4")
    w = H264VideoWriter(dst, (W, H), FPS, CFG_FAST)
    for i in range(N):
        w.write(_frame(i))
    peso = w.close()
    assert peso is not None and peso > 0
    assert duracion_video(dst) == pytest.approx(N / FPS, abs=0.2)
    cap = cv2.VideoCapture(dst)
    assert cap.isOpened()
    n = 0
    while True:
        ok, _ = cap.read()
        if not ok:
            break
        n += 1
    cap.release()
    assert n >= N - 2


def test_h264_writer_pre_roll_y_vivo_en_orden(tmp_path):
    """Simula el flujo de guarda_movimientosV3.py: frames previos (pre-roll) +
    vivo. El MP4 debe contener todos los frames en el orden escrito."""
    dst = str(tmp_path / "preroll.mp4")
    w = H264VideoWriter(dst, (W, H), FPS, CFG_FAST)
    frames = [_frame(i) for i in range(N)]
    for f in frames:          # pre-roll + vivo: misma escritura secuencial
        w.write(f)
    assert w.close() is not None
    cap = cv2.VideoCapture(dst)
    assert cap.isOpened()
    n = 0
    while True:
        ok, _ = cap.read()
        if not ok:
            break
        n += 1
    cap.release()
    assert n >= N - 2


def test_h264_writer_close_idempotente(tmp_path):
    dst = str(tmp_path / "idem.mp4")
    w = H264VideoWriter(dst, (W, H), FPS, CFG_FAST)
    for i in range(N):
        w.write(_frame(i))
    assert w.close() is not None
    assert w.close() is None  # segundo close: no-op


def test_h264_writer_extension_tmp_publi_atomica(tmp_path):
    """Regresión (fix moov-race + `-f mp4`): la publicación atómica escribe a
    `*.tmp` y ffmpeg debe aceptarlo. Sin `-f mp4`, ffmpeg rechaza la extensión
    .tmp ("Unable to find a suitable output format") y close() devuelve None:
    el vídeo de movimiento se descartaba (peso=None) y no se capturaba nada."""
    dst = str(tmp_path / "stream.tmp")  # como video_actual + '.tmp'
    w = H264VideoWriter(dst, (W, H), FPS, CFG_FAST)
    for i in range(N):
        w.write(_frame(i))
    peso = w.close()
    assert peso is not None and peso > 0
    assert duracion_video(dst) == pytest.approx(N / FPS, abs=0.2)


def test_h264_writer_stderr_path_logs_ffmpeg(tmp_path):
    """stderr_path: el stderr de ffmpeg se vuelca al fichero indicado, tanto en
    éxito (banner/estadísticas) como en error (diagnóstico de vídeos
    descartados)."""
    log = str(tmp_path / "ffmpeg.log")
    dst = str(tmp_path / "ok.mp4")
    w = H264VideoWriter(dst, (W, H), FPS, CFG_FAST, stderr_path=log)
    for i in range(N):
        w.write(_frame(i))
    assert w.close() is not None
    assert os.path.exists(log)
    assert os.path.getsize(log) > 0


def test_remux_video_mp4(tmp_path):
    """Remux (stream copy) usado por archiva_video.py cuando la captura ya es MP4."""
    src = str(tmp_path / "origen.mp4")
    w = H264VideoWriter(src, (W, H), FPS, CFG_FAST)
    for i in range(N):
        w.write(_frame(i))
    w.close()
    dst = str(tmp_path / "remux.mp4")
    peso = remux_video(src, dst)
    assert peso is not None and peso > 0
    assert duracion_video(dst) == pytest.approx(N / FPS, abs=0.2)
    assert os.path.exists(dst)


def test_remux_video_fuente_inexistente(tmp_path):
    assert remux_video(str(tmp_path / "noexiste.mp4"), str(tmp_path / "x.mp4")) is None


def test_extraer_poster(tmp_path, avi_origen):
    """La miniatura (1 frame) se genera como JPG junto al vídeo."""
    jpg = str(tmp_path / "poster.jpg")
    assert extraer_poster(avi_origen, jpg) is True
    assert os.path.getsize(jpg) > 0


def test_extraer_poster_fuente_inexistente(tmp_path):
    assert extraer_poster(str(tmp_path / "no.mp4"), str(tmp_path / "p.jpg")) is False


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
