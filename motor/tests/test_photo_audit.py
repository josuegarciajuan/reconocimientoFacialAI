import json

from motor.core.photo_audit import build_audit_record, write_audit_queue


def test_audit_record_correlates_with_foto_identifier_and_marks_post_move():
    record = build_audit_record(
        correlation_id="abc123",
        local_id="7",
        camera_id="2",
        classification="match",
        person="person-a",
        layers={"cara": {"score": 0.8, "confidence": 0.9}},
        moved_at="2026-09-01 10:00:00",
    )
    assert record["correlation_id"] == "abc123"
    assert record["classification_phase"] == "post_move"
    assert record["layers"]["cara"]["score"] == 0.8


def test_audit_queue_is_atomic(tmp_path):
    path = write_audit_queue(tmp_path, "local", "cam", "id", {"ok": True})
    assert path.exists()
    assert json.loads(path.with_suffix(".json").read_text()) == {"ok": True}
