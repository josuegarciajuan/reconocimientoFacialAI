"""Tests de la detección de movimiento pura — motor/tests/test_motion.py.

Cubre motor/core/motion.py: MotionConfig (ventana/umbral), hay_movimiento y
MotionDetector (estático, movimiento, primer frame, dontCare). No requiere
cámara: frames sintéticos.

Runner:
    motor/venv/bin/python -m pytest motor/tests/test_motion.py -q
"""
from __future__ import annotations

import cv2
import numpy as np

from motor.core.motion import MotionConfig, MotionDetector, hay_movimiento


# ---------------------------------------------------------------- MotionConfig

def test_frames_a_analizar_defaults():
    cfg = MotionConfig(segundos_analizar=2, fps=14, porcentaje_mov=60)
    # 2 s x 14 fps = 28 frames en el buffer; 60% de 28 = 17 para disparar
    assert cfg.frames_a_analizar == 28
    assert cfg.frames_con_movimiento == 17


def test_frames_a_analizar_independiente_de_sensibilidad():
    # Semántica legacy preservada: el buffer se mide en frames ANALIZADOS y no
    # se divide por sensibilidad (la ventana de reloj se alarga, no se rompe).
    c1 = MotionConfig(segundos_analizar=2, fps=14, sensibilidad=1)
    c3 = MotionConfig(segundos_analizar=2, fps=14, sensibilidad=3)
    assert c1.frames_a_analizar == 28
    assert c3.frames_a_analizar == 28
    assert c1.frames_con_movimiento == 17
    assert c3.frames_con_movimiento == 17


# ------------------------------------------------------------- hay_movimiento

def test_hay_movimiento_umbral_exacto():
    assert hay_movimiento([1] * 17 + [0] * 11, 17) is True
    assert hay_movimiento([1] * 16 + [0] * 12, 17) is False


def test_hay_movimiento_con_nones():
    # Los None (buffer legacy en arranque) no cuentan como movimiento
    buf = [None] * 10 + [1] * 17 + [0] * 1
    assert hay_movimiento(buf, 17) is True


# -------------------------------------------------------------- MotionDetector

def _base(w=320, h=240):
    return np.zeros((h, w, 3), dtype=np.uint8)


def _con_rect(x, w=320, h=240, size=60):
    f = np.zeros((h, w, 3), dtype=np.uint8)
    cv2.rectangle(f, (x, 100), (x + size, 100 + size), (255, 255, 255), -1)
    return f


def test_primer_frame_inicializa_sin_movimiento():
    det = MotionDetector(MotionConfig())
    motion, hay = det.process(_base())
    assert motion is None          # primer frame: solo inicializa prevFrame
    assert hay is False


def test_escena_estatica_no_dispara():
    det = MotionDetector(MotionConfig(segundos_analizar=2, fps=10, porcentaje_mov=60))
    f = _base()
    for _ in range(40):
        motion, hay = det.process(f)
        assert motion != 1
        assert hay is False


def test_movimiento_dispara():
    det = MotionDetector(MotionConfig(
        segundos_analizar=2, fps=10, porcentaje_mov=60, dontCare=200,
        threshold=21, blur=21, dilate=2))
    # 20 frames en el buffer; 12 con movimiento -> debe disparar
    for i in range(30):
        motion, hay = det.process(_con_rect(x=(i * 5) % 200))
        if hay:
            return  # OK: disparó
    raise AssertionError("el movimiento no disparó hay_movimiento")


def test_dontcare_filtra_contorno_pequeno():
    # Rectángulo 60x60 moviéndose 10px/frame: con blur 21 + dilate 2 el contorno
    # real mide ~1.6k px². dontCare=20000 lo ignora; dontCare=1000 lo detecta.
    det_big = MotionDetector(MotionConfig(dontCare=20000, threshold=21, blur=21, dilate=2))
    det_small = MotionDetector(MotionConfig(dontCare=1000, threshold=21, blur=21, dilate=2))
    ok_big = ok_small = False
    for i in range(10):
        f = _con_rect(x=(i * 10) % 200)
        mb, _ = det_big.process(f)
        ms, _ = det_small.process(f)
        if mb == 0:
            ok_big = True
        if ms == 1:
            ok_small = True
    assert ok_big, "dontCare alto no filtró el contorno"
    assert ok_small, "dontCare bajo no detectó el contorno"


def test_hay_ahora_refleja_buffer():
    det = MotionDetector(MotionConfig(
        segundos_analizar=2, fps=10, porcentaje_mov=60, dontCare=200))
    # Tras alimentar movimiento continuo, hay_ahora() (re-lectura usada por el
    # worker al parar) debe reflejar el mismo buffer que process().
    disparo = False
    for i in range(30):
        motion, hay = det.process(_con_rect(x=(i * 5) % 200))
        if hay:
            disparo = True
            assert det.hay_ahora() is True
            break
    assert disparo
