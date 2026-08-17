"""Tests de cruces.py: detección de cruce con frames sintéticos."""
import cv2
import numpy as np

from motor.cruces import CrossingConfig, CrossingDetector, Line, signed_distance


def _frame(obj_x, w=640, h=480):
    f = np.zeros((h, w, 3), dtype=np.uint8)
    if obj_x is not None:
        cv2.rectangle(f, (obj_x, 200), (obj_x + 40, 240), (255, 255, 255), -1)
    return f


def _run_sequence(det, xs, start_ts=0.0, step_ts=0.1):
    events = []
    ts = start_ts
    for x in xs:
        events.extend(det.process(_frame(x), ts))
        ts += step_ts
    return events


def test_signed_distance_sign():
    line = Line(320, 0, 320, 480)
    d_left = signed_distance(line, (100, 100))
    d_right = signed_distance(line, (500, 100))
    # signos opuestos a cada lado de la línea
    assert d_left * d_right < 0


def test_crossing_left_to_right():
    line = Line(320, 0, 320, 480, "L1")
    det = CrossingDetector(line, CrossingConfig())
    # calentamiento del fondo
    for _ in range(20):
        det.process(_frame(None), 0.0)
    events = _run_sequence(det, range(100, 500, 8))
    assert len(events) == 1
    assert events[0].line_id == "L1"
    assert events[0].direction in (1, 2)


def test_crossing_right_to_left_opposite_direction():
    line = Line(320, 0, 320, 480, "L1")
    det = CrossingDetector(line, CrossingConfig())
    for _ in range(20):
        det.process(_frame(None), 0.0)
    events = _run_sequence(det, range(500, 100, -8))
    assert len(events) == 1


def test_no_crossing_when_object_stops_before_line():
    line = Line(320, 0, 320, 480, "L1")
    det = CrossingDetector(line, CrossingConfig())
    for _ in range(20):
        det.process(_frame(None), 0.0)
    # objeto se mueve solo hasta x=260 (no llega a la línea)
    events = _run_sequence(det, range(100, 260, 8))
    assert events == []


def test_dedup_single_event_for_slow_pass():
    line = Line(320, 0, 320, 480, "L1")
    det = CrossingDetector(line, CrossingConfig())
    for _ in range(20):
        det.process(_frame(None), 0.0)
    # paso lento con pasos pequeños -> no debe duplicar el cruce
    events = _run_sequence(det, range(100, 500, 2), step_ts=0.05)
    assert len(events) == 1


def test_full_frame_flash_does_not_cross():
    # un cambio global (flash) no debe generar cruce: área > area_max se descarta
    line = Line(320, 0, 320, 480, "L1")
    det = CrossingDetector(line, CrossingConfig())
    for _ in range(20):
        det.process(_frame(None), 0.0)
    # frame totalmente iluminado (cambio global)
    events = []
    ts = 0.0
    for _ in range(5):
        f = np.full((480, 640, 3), 255, dtype=np.uint8)
        events.extend(det.process(f, ts))
        ts += 0.1
    assert events == []
