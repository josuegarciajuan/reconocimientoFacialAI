"""Tests de la Fase 0: contratos, métricas y referencia de calidad."""
from __future__ import annotations

import json
import os
import time

import pytest

from motor.core import pipeline_contracts as C
from motor.core import pipeline_metrics as M
from motor.core import quality_reference as Q


class TestInstanceRef:
    def test_roundtrip(self):
        ref = C.InstanceRef(instance="ojos", run_generation="gen-1")
        d = ref.to_dict()
        restored = C.InstanceRef.from_dict(d)
        assert restored == ref

    def test_camera_ref_roundtrip(self):
        ref = C.CameraRef(
            instance=C.InstanceRef(instance="rf", run_generation="g1"),
            local_id=1,
            camera_id="cam-entrada",
        )
        restored = C.CameraRef.from_dict(ref.to_dict())
        assert restored.instance.instance == "rf"
        assert restored.camera_id == "cam-entrada"


class TestFrameRange:
    def test_basic_properties(self):
        fr = C.FrameRange(
            first_frame_idx=10,
            last_frame_idx=20,
            first_frame_ts=1000.0,
            last_frame_ts=1001.0,
        )
        assert fr.frame_count == 11
        assert fr.duration_s == pytest.approx(1.0)

    def test_invalid_range_is_normalized(self):
        fr = C.FrameRange(
            first_frame_idx=20,
            last_frame_idx=10,
            first_frame_ts=1001.0,
            last_frame_ts=1000.0,
        )
        assert fr.frame_count == 1
        assert fr.duration_s == pytest.approx(0.0)


class TestAnalysisUnit:
    def test_roundtrip(self):
        unit = C.AnalysisUnit(
            unit_id="u-1",
            event=C.MotionEventRef(
                camera=C.CameraRef(
                    instance=C.InstanceRef(instance="ojos", run_generation="g1"),
                    local_id=1,
                    camera_id="cam1",
                ),
                event_id="e-1",
                started_at=time.time(),
            ),
            frame_range=C.FrameRange(
                first_frame_idx=0,
                last_frame_idx=10,
                first_frame_ts=1000.0,
                last_frame_ts=1001.0,
            ),
            config=C.ConfigRef(version="v1", params_hash="h1", params={"det_size": 640}),
            source_paths={"video": "/tmp/v.mp4"},
            requested_stages=["detect", "embed"],
            trace_id=C.new_trace_id(),
            created_at=time.time(),
        )
        d = unit.to_dict()
        restored = C.AnalysisUnit.from_dict(d)
        assert restored.unit_id == unit.unit_id
        assert restored.trace_id == unit.trace_id
        assert restored.config.params == {"det_size": 640}


class TestUnitResult:
    def test_roundtrip(self):
        face = C.FaceDetection(
            detection_id="d1",
            frame_idx=5,
            frame_ts=1000.5,
            bbox=C.BoundingBox(0.0, 0.0, 100.0, 100.0),
            keypoints={"left_eye": (10.0, 10.0)},
            confidence=0.95,
            embedding=[0.1, 0.2, 0.3],
            quality_score=0.88,
            sharpness=120.0,
            is_profile=False,
        )
        result = C.UnitResult(
            unit_id="u-1",
            instance=C.InstanceRef("ojos", "g1"),
            trace_id=C.new_trace_id(),
            kind=C.ResultKind.TEMPRANO,
            generated_at=time.time(),
            faces=[face],
            bodies=[],
            candidates=[],
            artifacts={"thumb": "/tmp/t.jpg"},
            metrics={"infer_s": 0.5},
        )
        restored = C.UnitResult.from_dict(result.to_dict())
        assert restored.kind == C.ResultKind.TEMPRANO
        assert len(restored.faces) == 1
        assert restored.faces[0].embedding == [0.1, 0.2, 0.3]


class TestJobResult:
    def test_roundtrip(self):
        result = C.UnitResult(
            unit_id="u-1",
            instance=C.InstanceRef("rf", "g1"),
            trace_id=C.new_trace_id(),
            kind=C.ResultKind.FINAL,
            generated_at=time.time(),
            faces=[],
            bodies=[],
            candidates=[],
            artifacts={},
            metrics={},
        )
        jr = C.JobResult(
            job_id="j-1",
            unit_result=result,
            received_at=time.time(),
        )
        restored = C.JobResult.from_dict(jr.to_dict())
        assert restored.unit_result.instance.run_generation == "g1"
        assert restored.applied_at is None


class TestMetricsRecorder:
    def test_stage_timer_writes_event(self, tmp_path):
        rec = M.MetricsRecorder(str(tmp_path), local_id=1)
        trace = C.new_trace_id()
        with rec.stage_timer(trace, C.PipelineStage.INFERENCIA, unit_id="u-1"):
            time.sleep(0.01)
        events = rec.read_events()
        assert len(events) == 2
        start_ev, end_ev = events
        assert start_ev["tipo"] == "stage"
        assert start_ev["trace_id"] == trace
        assert start_ev["stage"] == C.PipelineStage.INFERENCIA.value
        assert start_ev["extra"]["event"] == "start"
        assert end_ev["extra"]["event"] == "end"
        assert end_ev["duration_s"] >= 0.01

    def test_marker_and_summary(self, tmp_path):
        rec = M.MetricsRecorder(str(tmp_path), local_id=2)
        trace = C.new_trace_id()
        rec.marker(trace, C.PipelineStage.CAPTURA, camera_id="cam1")
        rec.summary(trace, camera_id="cam1", result_kind="final", stages_s={"infer": 0.5})
        events = rec.read_events()
        assert len(events) == 2
        assert events[0]["tipo"] == "marker"
        assert events[1]["tipo"] == "summary"
        assert events[1]["stages_s"]["infer"] == 0.5

    def test_queue_state(self, tmp_path):
        rec = M.MetricsRecorder(str(tmp_path), local_id=1)
        rec.queue_state(pending=5, sent=2, executing=1, received=3, applying=1, applied=10)
        events = rec.read_events()
        assert events[0]["tipo"] == "queue"
        assert events[0]["counts"]["pending"] == 5


class TestQualityReference:
    def test_add_and_evaluate_detection(self):
        ref = Q.QualityReference()
        ref.add(
            Q.QualityCase(
                case_id="far-small",
                description="cara lejana",
                source_path="/tmp/far.mp4",
                dimensions=["deteccion"],
                expected_faces=1,
                expected_persons=None,
                expected_crossings=None,
                tags=["far"],
            )
        )
        report = ref.evaluate({"far-small": {"detected_faces": 1}})
        assert report.passed == 1
        assert report.failed == 0

    def test_evaluate_identification_tolerance(self):
        ref = Q.QualityReference()
        ref.add(
            Q.QualityCase(
                case_id="two-people",
                description="dos personas",
                source_path="/tmp/two.mp4",
                dimensions=["identificacion"],
                expected_faces=None,
                expected_persons=["alice", "bob"],
                expected_crossings=None,
                tags=["multi"],
            )
        )
        report = ref.evaluate({"two-people": {"detected_persons": ["alice"]}})
        assert report.failed == 1
        report2 = ref.evaluate({"two-people": {"detected_persons": ["alice", "bob"]}})
        assert report2.passed == 1

    def test_load_from_dir(self, tmp_path):
        case_file = tmp_path / "cases.json"
        case_file.write_text(
            json.dumps(
                [
                    {
                        "case_id": "profile",
                        "description": "perfil",
                        "source_path": "/tmp/profile.mp4",
                        "dimensions": ["deteccion"],
                        "expected_faces": 1,
                        "tags": ["profile"],
                    }
                ]
            ),
            encoding="utf-8",
        )
        ref = Q.QualityReference()
        ref.load_from_dir(str(tmp_path))
        assert len(ref.cases) == 1
        assert ref.cases[0].case_id == "profile"

    def test_report_write(self, tmp_path):
        ref = Q.QualityReference()
        ref.add(
            Q.QualityCase(
                case_id="c1",
                description="",
                source_path="",
                dimensions=["deteccion"],
                expected_faces=1,
                expected_persons=None,
                expected_crossings=None,
                tags=[],
            )
        )
        report = ref.evaluate({"c1": {"detected_faces": 1}})
        path = str(tmp_path / "report.json")
        report.write(path)
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        assert data["passed"] == 1
