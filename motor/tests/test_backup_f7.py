"""Tests de F6 (backup/journal/rollback) y F7 (detección de persona sin cara)."""
import json
import os

import numpy as np
import pytest

from motor.core.backup import Journal
from motor.core.store import FaceStore
from motor.cruces import PersonDetector, bbox_iou, bbox_overlap


# ---------------------------------------------------------------------------
# F6: journal
# ---------------------------------------------------------------------------

def test_journal_append_and_read(tmp_path):
    j = Journal(str(tmp_path / "j.jsonl"))
    j.append({"op": "merge", "src": "A", "dst": "B", "n": 3})
    j.append({"op": "remove", "cod": "C"})
    entries = j.entries()
    assert len(entries) == 2
    assert entries[0]["op"] == "merge" and entries[1]["cod"] == "C"


def test_journal_append_concurrent(tmp_path):
    j = Journal(str(tmp_path / "j.jsonl"))
    import threading

    def w(i):
        for _ in range(10):
            j.append({"op": "t", "i": i})

    threads = [threading.Thread(target=w, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(j.entries()) == 50


def test_journal_empty_missing_file(tmp_path):
    assert Journal(str(tmp_path / "no.jsonl")).entries() == []


# ---------------------------------------------------------------------------
# F7: PersonDetector (personas sin cara)
# ---------------------------------------------------------------------------

def _synthetic_frame(person_bbox, bg=(60, 60, 60), fg=(200, 200, 200), size=(240, 320)):
    frame = np.full((size[0], size[1], 3), bg, dtype=np.uint8)
    x, y, w, h = person_bbox
    frame[y:y + h, x:x + w] = fg
    return frame


def test_person_detector_finds_moving_object():
    det = PersonDetector()
    # fondo estático durante 5 frames para entrenar MOG2
    for _ in range(5):
        det.process(_synthetic_frame((0, 0, 10, 10), fg=(60, 60, 60)))
    bboxes = det.process(_synthetic_frame((50, 60, 40, 120)))
    assert any(w >= 30 and h >= 80 for (x, y, w, h) in bboxes)


def test_person_detector_no_motion_no_boxes():
    det = PersonDetector()
    frame = _synthetic_frame((0, 0, 10, 10), fg=(60, 60, 60))
    for _ in range(5):
        det.process(frame)
    bboxes = det.process(frame)     # mismo frame -> sin movimiento nuevo
    assert len(bboxes) <= 1         # tolerancia: ruido residual del primer frame


def test_bbox_iou():
    assert bbox_iou((0, 0, 10, 10), (0, 0, 10, 10)) == pytest.approx(1.0)
    assert bbox_iou((0, 0, 10, 10), (100, 100, 10, 10)) == 0.0
    assert 0.0 < bbox_iou((0, 0, 20, 20), (10, 10, 20, 20)) < 1.0


def test_bbox_overlap():
    assert bbox_overlap((0, 0, 10, 10), (5, 5, 10, 10))
    assert not bbox_overlap((0, 0, 10, 10), (20, 20, 10, 10))


# ---------------------------------------------------------------------------
# F6: merge_undoable + restore (integración con backup)
# ---------------------------------------------------------------------------

def _rnd(seed):
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(512)
    return (v / np.linalg.norm(v)).astype(np.float32)


def test_journal_with_merge_undoable_roundtrip(tmp_path):
    p = str(tmp_path / "face_enc_v2")
    s = FaceStore(p)
    s.add("A", [_rnd(1)], [80.0], ["f"])
    s.add("B", [_rnd(2), _rnd(3)], [70.0, 60.0], ["pi", "pd"])

    j = Journal(str(tmp_path / "backup" / "journal.jsonl"))
    s.save_snapshot_bytes(str(tmp_path / "backup" / "face_enc_v2.bak"))
    entry = s.merge_undoable("A", "B")
    j.append({"op": "merge", "src": entry["src"], "dst": entry["dst"],
              "encodings_moved": entry["encodings_moved"]})
    assert set(s.persons()) == {"A"}

    # rollback del store (la BD se restaura aparte con el dump)
    data = s.load_snapshot_bytes(str(tmp_path / "backup" / "face_enc_v2.bak"))
    with open(p, "wb") as fh:
        import pickle
        pickle.dump(data, fh)
    s2 = FaceStore(p)
    assert set(s2.persons()) == {"A", "B"}
    assert s2.count("B") == 2
    assert len(j.entries()) == 1
