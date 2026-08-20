"""Tests de la vigilancia de deriva (F3) — motor/tests/test_vigilar_deriva.py

Cubre la lógica pura de motor/vigilar_deriva.py: la firma estructural
(descriptor de densidad de bordes por celda), la similitud y la regla
anti-falsa-alarma de 2 días consecutivos (_decidir_dia).
"""
from __future__ import annotations

import numpy as np
import cv2

from motor.vigilar_deriva import (EMA_ALPHA, GRID_H, GRID_W, _celdas_cambiadas,
                                  _decidir_dia, _descriptor, _sim)

HOY = "2026-08-20T10:00:00"


def _escena(seed: int = 1, layout=None, caja_movil: bool = False,
            movida: bool = False) -> list[np.ndarray]:
    """30 frames sintéticos (240x320) con estructura fija + opciones."""
    layout = layout or [(30, 40, 90, 200, 200), (230, 30, 300, 150, 180)]
    frames = []
    for i in range(30):
        img = np.full((240, 320), 60, np.uint8)
        for (x1, y1, x2, y2, v) in layout:
            cv2.rectangle(img, (x1, y1), (x2, y2), v, -1)
        cv2.line(img, (0, 120), (320, 120), 120, 4)
        cv2.line(img, (160, 0), (160, 240), 100, 4)
        if movida:
            img = cv2.warpAffine(img, np.float32([[1, 0, 40], [0, 1, 30]]), (320, 240))
        if caja_movil:
            x = 60 + (i * 4) % 160  # la caja se mueve: transitoria en la mediana
            cv2.rectangle(img, (x, 170), (x + 35, 220), 255, -1)
        frames.append(img)
    return frames


# ---------------------------------------------------------------------------
# Firma estructural
# ---------------------------------------------------------------------------

def test_descriptor_dimensiones():
    desc = _descriptor(_escena())
    assert desc.shape == (GRID_W * GRID_H,)
    assert np.isfinite(desc).all()
    assert abs(float(desc.mean())) < 1e-9  # z-score


def test_misma_escena_similitud_maxima():
    a = _descriptor(_escena(1))
    b = _descriptor(_escena(1))
    assert _sim(a, b) > 0.99


def test_caja_transitoria_no_dispara():
    """Una caja que se mueve (presente en pocos frames) queda en la mediana: no avisa."""
    a = _descriptor(_escena(1))
    b = _descriptor(_escena(1, caja_movil=True))
    assert _sim(a, b) > 0.95


def test_camara_movida_baja_similitud():
    a = _descriptor(_escena(1))
    b = _descriptor(_escena(1, movida=True))
    assert _sim(a, b) < 0.5


def test_layout_distinto_baja_similitud():
    a = _descriptor(_escena(1))
    b = _descriptor(_escena(1, layout=[(140, 20, 180, 220, 200), (10, 100, 100, 140, 180)]))
    assert _sim(a, b) < 0.5


def test_celdas_cambiadas_top():
    today = np.zeros(GRID_W * GRID_H)
    ref = np.zeros(GRID_W * GRID_H)
    ref[0], ref[5], ref[47] = 1.0, 2.0, 3.0  # celdas más diferentes en ref
    top = _celdas_cambiadas(today, ref, top=3)
    assert len(top) == 3
    assert top[0]["delta"] == -3.0  # mayor |delta| primero (47)
    assert {t["fila"] for t in top} == {1, 6}
    assert {t["col"] for t in top} == {1, 6, 8}


# ---------------------------------------------------------------------------
# Regla anti-falsa-alarma (_decidir_dia)
# ---------------------------------------------------------------------------

def test_primer_dia_fija_referencia_sin_aviso():
    st, ev = _decidir_dia(None, _descriptor(_escena()), 0.75, HOY)
    assert ev is None
    assert st["n_dias"] == 1
    assert st["alerta"] is False
    assert st["fecha_referencia"] == HOY


def test_dia_estable_actualiza_ema():
    desc = _descriptor(_escena())
    st1, _ = _decidir_dia(None, desc, 0.75, HOY)
    st2, ev = _decidir_dia(st1, desc, 0.75, HOY)
    assert ev is None
    assert st2["n_dias"] == 2
    assert st2["dias_bajos"] == 0
    assert st2["ultima_sim"] > 0.99
    # EMA: la referencia apenas cambia con observaciones idénticas
    assert abs(st2["referencia"][0] - st1["referencia"][0]) < 0.01


def test_un_dia_bajo_no_avisa():
    st1, _ = _decidir_dia(None, _descriptor(_escena()), 0.75, HOY)
    st2, ev = _decidir_dia(st1, _descriptor(_escena(movida=True)), 0.75, HOY)
    assert ev is None
    assert st2["dias_bajos"] == 1
    assert st2["alerta"] is False
    # la referencia NO se contamina con el día raro
    assert st2["referencia"] == st1["referencia"]


def test_dos_dias_bajos_avisa_con_celdas():
    st1, _ = _decidir_dia(None, _descriptor(_escena()), 0.75, HOY)
    st2, ev1 = _decidir_dia(st1, _descriptor(_escena(movida=True)), 0.75, HOY)
    st3, ev2 = _decidir_dia(st2, _descriptor(_escena(movida=True)), 0.75, HOY)
    assert ev1 is None
    assert ev2 is not None
    assert ev2["dias_bajos"] == 2
    assert st3["alerta"] is True
    assert len(ev2["celdas"]) == 3
    assert ev2["fecha"] == HOY


def test_alerta_se_limpia_al_estabilizarse():
    st1, _ = _decidir_dia(None, _descriptor(_escena()), 0.75, HOY)
    st2, _ = _decidir_dia(st1, _descriptor(_escena(movida=True)), 0.75, HOY)
    st3, ev = _decidir_dia(st2, _descriptor(_escena(movida=True)), 0.75, HOY)
    assert ev is not None  # alerta activa
    # el escenario vuelve a la escena original -> estable -> alerta se apaga
    st4, ev4 = _decidir_dia(st3, _descriptor(_escena()), 0.75, HOY)
    assert ev4 is None
    assert st4["alerta"] is False
    assert st4["dias_bajos"] == 0
