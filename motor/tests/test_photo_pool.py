"""Contrato del puente de foto HQ (M3): petición, rutas y lectura de jobs."""
import json

import cv2
import numpy as np

from motor.photo_pool import (MODE_FILE, RETURNS_DIR, SPOOL_DIR, build_request,
                              hq_name)
from motor.photo_worker import _frames_of, load_pairs


def _job(tmp_path, boxes):
    frames = []
    for i, bbox in enumerate(boxes):
        p = tmp_path / f"f{i}.png"
        cv2.imwrite(str(p), np.zeros((20, 20, 3), dtype=np.uint8))
        frames.append({"src": str(p), "bbox": bbox})
    out = str(tmp_path / "foto.jpg")
    job = tmp_path / "job.json"
    job.write_text(json.dumps({"frames": frames, "out": out}), encoding="utf-8")
    return str(job), out


def test_build_request_contract():
    req = build_request("/x/foto.jpg", [{"src": "/x/f0.png", "bbox": [0, 0, 5, 5]}], rid="req-t")
    assert req["id"] == "req-t"
    assert req["project"] == "reconocimientoFacial"
    assert req["process"] == "hq_photo"
    assert req["externalId"] == "photo:/x/foto.jpg"
    assert req["params"]["frames"][0]["src"] == "/x/f0.png"
    assert req["params"]["out"] == "/x/foto.jpg"


def test_rutas_y_nombre():
    assert SPOOL_DIR == "/var/lib/taildeck/spool"
    assert RETURNS_DIR == "/var/lib/taildeck/returns/reconocimientoFacial"
    assert MODE_FILE == "/var/lib/taildeck/projects/reconocimientoFacial.mode"
    assert hq_name("/a/b/foto.jpg") == "foto.jpg.hq"


def test_load_pairs_y_frames_of(tmp_path):
    job, out = _job(tmp_path, [[0, 0, 10, 10], [1, 1, 12, 12]])
    o, pairs, srcs = load_pairs(job)
    assert o == out
    assert len(pairs) == 2
    assert len(srcs) == 2
    assert len(_frames_of(job)) == 2
