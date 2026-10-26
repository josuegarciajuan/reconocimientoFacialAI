"""Tests de la Fase 4: procesador de vídeo y validación de artefactos."""
from __future__ import annotations

import json
import os
import time

import numpy as np
import pytest

from motor.core import pipeline_contracts as C
from motor.core.artifact_lifecycle import ArtifactLifecycle
from motor.core.job_store import JobStatus
from motor.processors.video_processor import DetectionCollector, process_unit


def _unit(tmp_path, unit_id: str = "u1") -> C.AnalysisUnit:
    video = tmp_path / "motor" / "videos" / "1" / "cam1"
    video.mkdir(parents=True, exist_ok=True)
    video_file = video / "cam1_2026-01-01_10.00.00.avi"
    video_file.write_bytes(b"fakevideo")
    return C.AnalysisUnit(
        unit_id=unit_id,
        event=C.MotionEventRef(
            camera=C.CameraRef(
                instance=C.InstanceRef("ojos", "g1"),
                local_id=1,
                camera_id="cam1",
            ),
            event_id="e1",
            started_at=time.time(),
        ),
        frame_range=C.FrameRange(0, 9, 1000.0, 1000.9),
        config=C.ConfigRef(version="v1", params_hash="h1", params={"face_every": 3}),
        source_paths={"video": video_file.name},
        requested_stages=["video_faces"],
        trace_id=C.new_trace_id(),
        created_at=time.time(),
    )


class _FakeCtx:
    def __init__(self, root):
        class _Worker:
            project_root = root

        self.worker = _Worker()
        self.metrics = None
        self.trace_id = "t1"

    def record_stage_start(self, stage):
        return time.time()

    def record_stage_end(self, stage, ts):
        pass


def _fake_face():
    from motor.core.model import Face

    return Face(
        bbox=(10, 10, 60, 60),
        det_score=0.92,
        embedding=np.array([0.1, 0.2, 0.3], dtype=np.float32),
        pose=(5.0, 0.0, 0.0),
        landmarks=None,
        kps=np.array([[20.0, 20.0], [50.0, 20.0], [35.0, 35.0], [20.0, 50.0], [50.0, 50.0]], dtype=np.float32),
    )


def _fake_process_video(local_id, camara_id, fichero, ruta, cfg, face_every, **kwargs):
    collector = kwargs.get("collector")
    resumen = kwargs.get("resumen")
    # Crear artefactos simulados.
    base = os.path.join(ruta, "motor/caras/sinclasificar", str(local_id))
    for sub in (camara_id, f"{camara_id}_busto", f"{camara_id}_frame", f"{camara_id}_cuerpo"):
        os.makedirs(os.path.join(base, sub), exist_ok=True)
        with open(os.path.join(base, sub, "x.png"), "wb") as fh:
            fh.write(b"x")
    if collector is not None:
        collector.on_face(_fake_face(), 0, 0.0, "saved")
        collector.on_body((1, 1, 10, 20), 3, 0.3, False)
        collector.on_crossing(type("Ev", (), {"direction": 1, "x": 5, "y": 6})(),
                              type("Ln", (), {"line_id": "l1"})())
    if resumen is not None:
        resumen.update(
            {"frames": 10, "caras_detect": 1, "caras_guard": 1,
             "caras_borroso": 0, "caras_dedup": 0, "cuerpos": 1}
        )
    return 10


class TestDetectionCollector:
    def test_collects_faces_bodies_crossings(self):
        c = DetectionCollector()
        c.on_face(_fake_face(), 0, 0.0, "saved")
        c.on_body((1, 1, 10, 20), 3, 0.3, False)
        c.on_body((1, 1, 10, 20), 4, 0.4, True)  # con cara: se ignora
        c.on_crossing(type("Ev", (), {"direction": 1, "x": 5, "y": 6})(),
                      type("Ln", (), {"line_id": "l1"})())
        assert len(c.faces) == 1
        assert c.faces[0].embedding == [pytest.approx(0.1), pytest.approx(0.2), pytest.approx(0.3)]
        assert len(c.bodies) == 1
        assert len(c.crossings) == 1
        assert c.crossings[0]["linea_id"] == "l1"


class TestProcessUnit:
    def test_process_unit_returns_detections_and_artifacts(self, tmp_path, monkeypatch):
        import motor.procesa_video as pv

        monkeypatch.setattr(pv, "process_video", _fake_process_video)

        unit = _unit(tmp_path)
        ctx = _FakeCtx(str(tmp_path))
        result = process_unit(unit, ctx)

        assert result.unit_id == "u1"
        assert len(result.faces) == 1
        assert result.faces[0].frame_idx == 0
        assert len(result.bodies) == 1
        assert result.metrics["frames"] == 10
        assert result.metrics["cruces"] == 1
        assert "faces" in result.artifacts
        assert os.path.isdir(result.artifacts["faces"])
        # Manifiesto publicado.
        al = ArtifactLifecycle(os.path.join(str(tmp_path), "motor", "artifacts"))
        assert al.is_published("u1")


class TestCollectorArtifactVerification:
    def _make_result(self, artifacts):
        uri = C.UnitResult(
            unit_id="u1",
            instance=C.InstanceRef("ojos", "g1"),
            trace_id=C.new_trace_id(),
            kind=C.ResultKind.FINAL,
            generated_at=time.time(),
            faces=[],
            bodies=[],
            candidates=[],
            artifacts=artifacts,
            metrics={},
        )
        return C.JobResult(job_id="j1", unit_result=uri, received_at=time.time())

    def test_verify_artifacts_rejects_missing(self, tmp_path):
        from motor.core.job_store import JobStore
        from motor.pipeline_collector import PipelineCollector

        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        returns = str(tmp_path / "returns")
        collector = PipelineCollector(
            store, project_root=str(tmp_path), returns_dir_override=returns,
            verify_artifacts=True,
        )
        job_dir = os.path.join(returns, "j1", "result")
        os.makedirs(job_dir, exist_ok=True)
        result = self._make_result({"faces": str(tmp_path / "missing_dir")})
        with open(os.path.join(job_dir, "result.json"), "w", encoding="utf-8") as fh:
            json.dump(result.to_dict(), fh, ensure_ascii=False)

        assert collector.collect_all() == []

    def test_verify_artifacts_accepts_present(self, tmp_path):
        from motor.core.job_store import JobStore
        from motor.pipeline_collector import PipelineCollector

        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        existing = tmp_path / "faces"
        existing.mkdir()
        returns = str(tmp_path / "returns")
        collector = PipelineCollector(
            store, project_root=str(tmp_path), returns_dir_override=returns,
            verify_artifacts=True,
        )
        job_dir = os.path.join(returns, "j1", "result")
        os.makedirs(job_dir, exist_ok=True)
        result = self._make_result({"faces": str(existing)})
        with open(os.path.join(job_dir, "result.json"), "w", encoding="utf-8") as fh:
            json.dump(result.to_dict(), fh, ensure_ascii=False)

        assert collector.collect_all() == ["j1"]


class TestDispatcherLines:
    def test_dispatch_includes_lines_in_config(self, tmp_path, monkeypatch):
        from motor.core.job_store import JobStore
        from motor.pipeline_dispatcher import PipelineDispatcher
        import motor.procesa_video as pv

        class _Line:
            def __init__(self, i):
                self.line_id = i
                self.x1, self.y1, self.x2, self.y2 = 0.0, 0.0, 10.0, 10.0

        monkeypatch.setattr(pv, "cargar_lineas", lambda cam: [_Line("l1")])

        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        spool = str(tmp_path / "spool")
        dispatcher = PipelineDispatcher(
            store, project_root=str(tmp_path), spool_dir=spool, max_sent=5
        )
        store.submit_job(
            C.JobRequest(
                job_id="j1",
                unit=_unit(tmp_path),
                priority=1,
                submitted_at=time.time(),
                deadline_at=None,
            )
        )
        sent = dispatcher.dispatch_one("g1")
        assert sent == "j1"
        with open(os.path.join(spool, "j1.json"), encoding="utf-8") as fh:
            payload = json.load(fh)
        assert payload["params"]["config"]["params"]["lineas"][0]["id"] == "l1"
