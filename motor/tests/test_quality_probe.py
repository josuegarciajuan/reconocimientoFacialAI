"""Tests de motor/quality_probe.py: funciones puras (sin modelos ni vídeos).

La sonda de calidad es una herramienta OFFLINE; aquí se validan las piezas que
no dependen de insightface/torch ni de datos reales: la etiqueta de calidad
(contrato con el panel), el recorte de contexto y la composición de la tira.
"""
import numpy as np

from motor.quality_probe import _context_crop, _strip, quality_label


def test_quality_label_matches_panel_contract():
    # mismo umbral que motor/core/image_provenance.py
    assert quality_label(10) == "insufficient"
    assert quality_label(31) == "insufficient"
    assert quality_label(32) == "limited"
    assert quality_label(63) == "limited"
    assert quality_label(64) == "usable"
    assert quality_label(200) == "usable"


def test_context_crop_returns_bbox_inside_crop():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    bbox = (300, 200, 340, 240)          # cara 40x40 centrada
    crop, bbx = _context_crop(frame, bbox)
    assert crop is not None
    x1, y1, x2, y2 = bbx
    assert 0 <= x1 < x2 <= crop.shape[1]
    assert 0 <= y1 < y2 <= crop.shape[0]


def test_context_crop_clamps_at_border():
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    crop, bbx = _context_crop(frame, (0, 0, 30, 30))   # cara pegada a la esquina
    assert crop is not None
    assert bbx[0] == 0 and bbx[1] == 0
    assert bbx[2] > 0 and bbx[3] > 0


def test_context_crop_empty_when_bbox_degenerate():
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    crop, bbx = _context_crop(frame, (10, 10, 11, 11))
    # cara 1x1: recorte degenerado -> None (no debe romper el llamador)
    assert crop is None and bbx is None


def test_strip_composes_labelled_tiles():
    a = np.zeros((40, 60, 3), dtype=np.uint8)
    b = np.full((50, 30, 3), 255, dtype=np.uint8)
    out = _strip([a, b], ["A", "B"], height=100)
    assert out is not None
    # todas las tiras tienen la misma altura (banner 28 + 100)
    assert out.shape[0] == 128


def test_strip_none_when_no_images():
    assert _strip([None, None], ["A", "B"]) is None
