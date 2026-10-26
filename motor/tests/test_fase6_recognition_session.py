"""Tests de la Fase 6: sesión de reconocimiento incremental."""
from __future__ import annotations

import time

import pytest

from motor.core.pipeline_contracts import (
    BoundingBox,
    CameraRef,
    FaceDetection,
    InstanceRef,
    ResultKind,
    UnitResult,
)
from motor.core.recognition_session import (
    MatchResult,
    RecognitionSession,
    SessionConfig,
    SessionKey,
    SessionStore,
)


class FixedGallery:
    def __init__(self, result):
        self.result = result
        self.calls = 0

    def match(self, embedding):
        self.calls += 1
        return self.result


class SequenceGallery:
    def __init__(self, results):
        self.results = list(results)
        self.index = 0

    def match(self, embedding):
        if not self.results:
            return None
        r = self.results[min(self.index, len(self.results) - 1)]
        self.index += 1
        return r


def _camera() -> CameraRef:
    return CameraRef(InstanceRef("ojos", "g1"), 1, "cam1")


def _key() -> SessionKey:
    return SessionKey(_camera(), "e1")


def _face(idx: int, ts: float, emb, bbox=(0, 0, 10, 10), quality=0.9) -> FaceDetection:
    return FaceDetection(
        detection_id=f"d{idx}",
        frame_idx=idx,
        frame_ts=ts,
        bbox=BoundingBox(*bbox),
        keypoints={},
        confidence=0.9,
        embedding=emb,
        quality_score=quality,
        sharpness=None,
        is_profile=False,
    )


def _unit(unit_id: str, faces, event_id="e1", camera_id="cam1") -> UnitResult:
    return UnitResult(
        unit_id=unit_id,
        instance=InstanceRef("ojos", "g1"),
        trace_id="t1",
        kind=ResultKind.FINAL,
        generated_at=time.time(),
        faces=faces,
        bodies=[],
        candidates=[],
        artifacts={},
        metrics={},
        event_id=event_id,
        local_id=1,
        camera_id=camera_id,
    )


A1 = [1.0, 0.0, 0.0]
A2 = [0.99, 0.01, 0.0]
B1 = [0.0, 1.0, 0.0]
B2 = [0.01, 0.99, 0.0]


class TestClustering:
    def test_similar_embeddings_group(self):
        s = RecognitionSession(_key())
        s.add(_unit("u1", [_face(0, 0.0, A1, bbox=(0, 0, 10, 10))]))
        s.add(_unit("u2", [_face(1, 1.0, A2, bbox=(20, 20, 30, 30))]))
        assert len(s.clusters) == 1
        assert s.clusters[0].size == 2

    def test_different_embeddings_separate(self):
        s = RecognitionSession(_key())
        s.add(_unit("u1", [_face(0, 0.0, A1, bbox=(0, 0, 10, 10))]))
        s.add(_unit("u2", [_face(1, 1.0, B1, bbox=(20, 20, 30, 30))]))
        assert len(s.clusters) == 2

    def test_out_of_order_units_sorted(self):
        s = RecognitionSession(_key())
        s.add(_unit("u2", [_face(5, 5.0, A1, bbox=(50, 50, 60, 60))]))
        s.add(_unit("u1", [_face(1, 1.0, A2, bbox=(10, 10, 20, 20))]))
        faces = s.early_result().faces
        assert [f.frame_idx for f in faces] == [1, 5]

    def test_duplicate_face_deduped(self):
        s = RecognitionSession(_key())
        f = _face(0, 0.0, A1, bbox=(0, 0, 10, 10))
        assert s.add(_unit("u1", [f])) == 1
        assert s.add(_unit("u1b", [f])) == 0
        assert len(s.early_result().faces) == 1


class TestEarlyFinal:
    def test_early_never_confirmed(self):
        gallery = FixedGallery(MatchResult(person_id=7, label="Ana", score=0.99))
        s = RecognitionSession(_key(), gallery=gallery)
        s.add(_unit("u1", [_face(0, 0.0, A1)]))
        early = s.early_result()
        assert early.kind == ResultKind.TEMPRANO
        assert len(early.candidates) == 1
        assert early.candidates[0].person_id == 7
        assert early.candidates[0].is_confirmed is False

    def test_final_confirmed_with_strong_match(self):
        gallery = FixedGallery(MatchResult(person_id=7, label="Ana", score=0.99, second_score=0.1))
        s = RecognitionSession(_key(), gallery=gallery)
        s.add(_unit("u1", [_face(0, 0.0, A1)]))
        assert s.final_result() is None  # no cerrada
        s.close()
        final = s.final_result()
        assert final.kind == ResultKind.FINAL
        assert final.candidates[0].is_confirmed is True

    def test_final_not_confirmed_with_low_score(self):
        gallery = FixedGallery(MatchResult(person_id=7, label="Ana", score=0.30, second_score=0.29))
        s = RecognitionSession(_key(), gallery=gallery)
        s.add(_unit("u1", [_face(0, 0.0, A1)]))
        s.close()
        assert s.final_result().candidates[0].is_confirmed is False

    def test_final_not_confirmed_with_small_margin(self):
        gallery = FixedGallery(MatchResult(person_id=7, label="Ana", score=0.90, second_score=0.89))
        s = RecognitionSession(_key(), gallery=gallery)
        s.add(_unit("u1", [_face(0, 0.0, A1)]))
        s.close()
        assert s.final_result().candidates[0].is_confirmed is False

    def test_two_people_two_candidates(self):
        gallery = FixedGallery(MatchResult(person_id=7, label="Ana", score=0.95, second_score=0.1))
        s = RecognitionSession(_key(), gallery=gallery)
        s.add(_unit("u1", [
            _face(0, 0.0, A1, bbox=(0, 0, 10, 10)),
            _face(0, 0.0, B1, bbox=(50, 50, 60, 60)),
        ]))
        early = s.early_result()
        assert len(early.candidates) == 2
        assert len(s.clusters) == 2

    def test_single_useful_image_confirmed(self):
        gallery = FixedGallery(MatchResult(person_id=7, label="Ana", score=0.80, second_score=0.2))
        s = RecognitionSession(_key(), gallery=gallery)
        s.add(_unit("u1", [_face(0, 0.0, A1)]))
        s.close()
        assert s.final_result().candidates[0].is_confirmed is True

    def test_custom_config_requires_more_faces(self):
        cfg = SessionConfig(min_faces_confirm=2)
        gallery = FixedGallery(MatchResult(person_id=7, label="Ana", score=0.99, second_score=0.1))
        s = RecognitionSession(_key(), config=cfg, gallery=gallery)
        s.add(_unit("u1", [_face(0, 0.0, A1)]))
        s.close()
        assert s.final_result().candidates[0].is_confirmed is False


class TestSessionStore:
    def test_get_or_create_and_close(self):
        store = SessionStore()
        key = _key()
        s = store.get_or_create(key)
        assert store.get(key) is s
        store.close(key)
        assert s.is_closed
        assert len(store.all_stats()) == 1

    def test_add_after_close_raises(self):
        s = RecognitionSession(_key())
        s.close()
        with pytest.raises(RuntimeError):
            s.add(_unit("u1", [_face(0, 0.0, A1)]))


class TestUnitResultContextRoundtrip:
    def test_event_context_survives_json(self):
        r = _unit("u1", [_face(0, 0.0, A1)], event_id="evt-42", camera_id="cam9")
        d = r.to_dict()
        restored = UnitResult.from_dict(d)
        assert restored.event_id == "evt-42"
        assert restored.camera_id == "cam9"
        assert restored.local_id == 1

    def test_legacy_payload_without_context(self):
        r = _unit("u1", [_face(0, 0.0, A1)])
        d = r.to_dict()
        for k in ("event_id", "local_id", "camera_id"):
            d.pop(k, None)
        restored = UnitResult.from_dict(d)
        assert restored.event_id == ""
        assert restored.local_id == 0
        assert restored.camera_id == ""
