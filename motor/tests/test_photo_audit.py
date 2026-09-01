import json

from motor.core.photo_audit import (build_audit_record, layer_scores_json,
                                    post_move_event_for, write_audit_queue,
                                    write_move_event)


def test_audit_record_leaves_phase_for_database_authority():
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
    assert record["classification_phase"] == "initial"
    assert record["layers"]["cara"]["score"] == 0.8


def test_audit_queue_is_atomic(tmp_path):
    path = write_audit_queue(tmp_path, "local", "cam", "id", {"ok": True})
    assert path.exists()
    assert json.loads(path.with_suffix(".json").read_text()) == {"ok": True}


def test_audit_serializes_attributes_layer_activation():
    class Score:
        score, confidence, available = 0.75, 0.25, True
    assert layer_scores_json({"attributes": Score()}) == {
        "attributes": {"score": 0.75, "confidence": 0.25, "available": True}
    }


def test_post_move_event_is_scoped_to_destination_person(tmp_path):
    path = write_move_event(tmp_path, "7", "2", {"event_id": 9,
        "to_person_code": "person-a", "moved_at": 100.0})
    assert post_move_event_for(path, "person-a", 101.0)["event_id"] == 9
    assert post_move_event_for(path, "person-b", 101.0) is None


def test_audit_paths_reject_traversal(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        write_audit_queue(tmp_path, "../other", "2", "abc", {})
