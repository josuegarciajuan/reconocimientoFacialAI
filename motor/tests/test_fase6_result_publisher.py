"""Tests de la Fase 6: publicación idempotente y coordinación de sesiones."""
from __future__ import annotations

import time

import pytest

from motor.core.job_store import JobStore
from motor.core.pipeline_contracts import (
    BoundingBox,
    CameraRef,
    FaceDetection,
    InstanceRef,
    RecognitionCandidate,
    ResultKind,
    UnitResult,
)
from motor.core.recognition_session import MatchResult, SessionConfig, SessionKey
from motor.core.result_publisher import (
    InMemorySink,
    ResultPublisher,
    SessionCoordinator,
    make_collector_hook,
)

A1 = [1.0, 0.0, 0.0]
B1 = [0.0, 1.0, 0.0]


class FixedGallery:
    def __init__(self, result):
        self.result = result

    def match(self, embedding):
        return self.result


class SequenceGallery:
    def __init__(self, results):
        self.results = list(results)
        self.i = 0

    def match(self, embedding):
        r = self.results[min(self.i, len(self.results) - 1)]
        self.i += 1
        return r


def _face(idx=0, ts=0.0, emb=A1, bbox=(0, 0, 10, 10)) -> FaceDetection:
    return FaceDetection(
        detection_id=f"d{idx}",
        frame_idx=idx,
        frame_ts=ts,
        bbox=BoundingBox(*bbox),
        keypoints={},
        confidence=0.9,
        embedding=emb,
        quality_score=0.9,
        sharpness=None,
        is_profile=False,
    )


def _unit(faces, unit_id="u1", kind=ResultKind.FINAL, event_id="e1") -> UnitResult:
    return UnitResult(
        unit_id=unit_id,
        instance=InstanceRef("ojos", "g1"),
        trace_id="t1",
        kind=kind,
        generated_at=time.time(),
        faces=faces,
        bodies=[],
        candidates=[],
        artifacts={},
        metrics={},
        event_id=event_id,
        local_id=1,
        camera_id="cam1",
    )


def _result_with_candidate(person_id, confirmed, kind=ResultKind.TEMPRANO, event_id="e1") -> UnitResult:
    return UnitResult(
        unit_id="r1",
        instance=InstanceRef("ojos", "g1"),
        trace_id="t1",
        kind=kind,
        generated_at=time.time(),
        faces=[],
        bodies=[],
        candidates=[
            RecognitionCandidate(
                candidate_id=f"e1:c0",
                person_id=person_id,
                person_label="Ana",
                score=0.9,
                method="embedding",
                is_confirmed=confirmed,
            )
        ],
        artifacts={},
        metrics={},
        event_id=event_id,
        local_id=1,
        camera_id="cam1",
    )


@pytest.fixture
def store(tmp_path):
    s = JobStore(str(tmp_path), "ojos")
    s.create_generation("g1")
    return s


class TestResultPublisher:
    def test_publishes_identified_candidate(self, store):
        sink = InMemorySink()
        pub = ResultPublisher(store, sink)
        n = pub.publish(_result_with_candidate(7, False))
        assert n == 1
        assert len(sink.records) == 1
        rec = next(iter(sink.records.values()))
        assert rec["person_id"] == 7
        assert rec["confirmed"] is False

    def test_skips_unidentified(self, store):
        sink = InMemorySink()
        pub = ResultPublisher(store, sink)
        assert pub.publish(_result_with_candidate(None, False)) == 0
        assert sink.records == {}

    def test_idempotent_same_result(self, store):
        sink = InMemorySink()
        pub = ResultPublisher(store, sink)
        r = _result_with_candidate(7, False)
        assert pub.publish(r) == 1
        assert pub.publish(r) == 0
        assert len(sink.records) == 1

    def test_final_updates_same_publication(self, store):
        sink = InMemorySink()
        pub = ResultPublisher(store, sink)
        early = _result_with_candidate(7, False, kind=ResultKind.TEMPRANO)
        final = _result_with_candidate(7, True, kind=ResultKind.FINAL)
        assert pub.publish(early) == 1
        assert pub.publish(final) == 1
        # Una sola clave de publicación (upsert), ya confirmada.
        assert len(sink.records) == 1
        assert next(iter(sink.records.values()))["confirmed"] is True

    def test_candidate_change_publishes_update(self, store):
        sink = InMemorySink()
        pub = ResultPublisher(store, sink)
        r1 = _result_with_candidate(7, False, kind=ResultKind.TEMPRANO)
        pub.publish(r1)
        # Mismo candidato, distinta persona -> nueva publicación (upsert).
        r2 = _result_with_candidate(8, False, kind=ResultKind.TEMPRANO)
        assert pub.publish(r2) == 1
        assert len(sink.records) == 1
        assert next(iter(sink.records.values()))["person_id"] == 8


class TestSessionCoordinator:
    def test_ingest_publishes_early(self, store):
        sink = InMemorySink()
        pub = ResultPublisher(store, sink)
        coord = SessionCoordinator(
            pub,
            gallery=FixedGallery(MatchResult(person_id=7, label="Ana", score=0.95, second_score=0.1)),
        )
        out = coord.ingest(_unit([_face()]))
        assert out["status"] == "ok"
        assert out["added"] == 1
        assert out["published"] == 1
        assert next(iter(sink.records.values()))["confirmed"] is False

    def test_close_publishes_final_confirmed(self, store):
        sink = InMemorySink()
        pub = ResultPublisher(store, sink)
        coord = SessionCoordinator(
            pub,
            gallery=FixedGallery(MatchResult(person_id=7, label="Ana", score=0.95, second_score=0.1)),
        )
        coord.ingest(_unit([_face()]))
        key = SessionKey(CameraRef(InstanceRef("ojos", "g1"), 1, "cam1"), "e1")
        out = coord.close(key)
        assert out["status"] == "cerrada"
        assert out["published"] == 1
        assert out["confirmed"] == 1
        assert next(iter(sink.records.values()))["confirmed"] is True

    def test_ingest_without_context(self, store):
        sink = InMemorySink()
        pub = ResultPublisher(store, sink)
        coord = SessionCoordinator(pub)
        result = _unit([_face()], event_id="")
        out = coord.ingest(result)
        assert out["status"] == "sin_contexto"

    def test_ingest_after_close_rejected(self, store):
        sink = InMemorySink()
        pub = ResultPublisher(store, sink)
        coord = SessionCoordinator(pub)
        key = SessionKey(CameraRef(InstanceRef("ojos", "g1"), 1, "cam1"), "e1")
        coord.ingest(_unit([_face()]))
        coord.sessions.close(key)
        out = coord.ingest(_unit([_face(idx=1, ts=1.0, bbox=(20, 20, 30, 30))]))
        assert out["status"] == "sesion_cerrada"

    def test_close_stale(self, store):
        sink = InMemorySink()
        pub = ResultPublisher(store, sink)
        coord = SessionCoordinator(
            pub,
            gallery=FixedGallery(MatchResult(person_id=7, label="Ana", score=0.95, second_score=0.1)),
            close_after_s=0.0,
        )
        coord.ingest(_unit([_face()]))
        closed = coord.close_stale(max_age_s=0.0)
        assert len(closed) == 1
        assert closed[0]["status"] == "cerrada"

    def test_two_people_two_publications(self, store):
        sink = InMemorySink()
        pub = ResultPublisher(store, sink)

        class TwoPeopleGallery:
            def __init__(self):
                self.i = 0

            def match(self, emb):
                self.i += 1
                pid = 7 if self.i == 1 else 8
                return MatchResult(person_id=pid, label=f"P{pid}", score=0.95, second_score=0.1)

        coord = SessionCoordinator(pub, gallery=TwoPeopleGallery())
        coord.ingest(_unit([
            _face(0, 0.0, A1, bbox=(0, 0, 10, 10)),
            _face(0, 0.0, B1, bbox=(50, 50, 60, 60)),
        ]))
        assert len(sink.records) == 2

    def test_collector_hook_ingests(self, store):
        sink = InMemorySink()
        pub = ResultPublisher(store, sink)
        coord = SessionCoordinator(
            pub,
            gallery=FixedGallery(MatchResult(person_id=7, label="Ana", score=0.95, second_score=0.1)),
        )
        hook = make_collector_hook(coord)
        hook(_unit([_face()]), 0)
        assert len(sink.records) == 1
