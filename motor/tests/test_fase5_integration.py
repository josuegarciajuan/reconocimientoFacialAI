"""Tests de integración de la Fase 5 (despacho ↔ worker ↔ captura)."""
from __future__ import annotations

import json
import os
import time

import pytest

from motor.core import pipeline_contracts as C


def _unit(tmp_path, unit_id: str = "u1", absolute: bool = False) -> C.AnalysisUnit:
    video_dir = tmp_path / "motor" / "videos" / "1" / "cam1"
    video_dir.mkdir(parents=True, exist_ok=True)
    video_file = video_dir / "cam1_2026-01-01_10.00.00.avi"
    video_file.write_bytes(b"fake")
    source = str(video_file) if absolute else video_file.name
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
        config=C.ConfigRef(version="v1", params_hash="h1", params={}),
        source_paths={"video": source},
        requested_stages=["video_faces"],
        trace_id=C.new_trace_id(),
        created_at=time.time(),
    )


class TestDispatcherUnitPayload:
    def test_payload_contains_reconstructable_unit(self, tmp_path, monkeypatch):
        from motor.core.job_store import JobStore
        from motor.pipeline_dispatcher import PipelineDispatcher
        import motor.procesa_video as pv

        monkeypatch.setattr(pv, "cargar_lineas", lambda cam: [])

        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        spool = str(tmp_path / "spool")
        dispatcher = PipelineDispatcher(
            store, project_root=str(tmp_path), spool_dir=spool, max_sent=5
        )
        unit = _unit(tmp_path)
        store.submit_job(C.JobRequest(
            job_id="j1", unit=unit, priority=1,
            submitted_at=time.time(), deadline_at=None,
        ))
        assert dispatcher.dispatch_one("g1") == "j1"

        with open(os.path.join(spool, "j1.json"), encoding="utf-8") as fh:
            payload = json.load(fh)

        assert "unit" in payload["params"]
        restored = C.AnalysisUnit.from_dict(payload["params"]["unit"])
        assert restored.unit_id == unit.unit_id
        assert restored.trace_id == unit.trace_id
        assert restored.event.camera.camera_id == "cam1"


class TestInferencePoolReconstruction:
    def test_build_request_from_payload(self, tmp_path):
        from motor.inference_pool import _build_request_from_superserver

        unit = _unit(tmp_path)
        payload = {
            "id": "j1",
            "params": {
                "instance": "ojos",
                "run_generation": "g1",
                "unit": unit.to_dict(),
            },
            "priority": 5,
            "submitted_at": time.time(),
        }
        req = _build_request_from_superserver(payload)
        assert req.job_id == "j1"
        assert req.unit.unit_id == "u1"
        assert req.unit.event.camera.instance.run_generation == "g1"


class TestVideoProcessorAbsolutePath:
    def test_absolute_source_uses_override(self, tmp_path, monkeypatch):
        import motor.procesa_video as pv
        from motor.processors import video_processor

        captured = {}

        def fake_process_video(local_id, camara_id, fichero, ruta, cfg, face_every, **kwargs):
            captured["fichero"] = fichero
            captured["override"] = kwargs.get("video_path_override")
            if kwargs.get("resumen") is not None:
                kwargs["resumen"].update({"frames": 1})
            return 1

        monkeypatch.setattr(pv, "process_video", fake_process_video)

        class _Worker:
            project_root = str(tmp_path)

        class _Ctx:
            worker = _Worker()
            metrics = None
            trace_id = "t1"

        unit = _unit(tmp_path, absolute=True)
        result = video_processor.process_unit(unit, _Ctx())
        assert captured["override"] == unit.source_paths["video"]
        assert captured["fichero"] == "cam1_2026-01-01_10.00.00.avi"
        assert result.metrics["frames"] == 1


class TestDispatcherSpec:
    def test_payload_contains_spec_for_control_plane(self, tmp_path, monkeypatch):
        from motor.core.job_store import JobStore
        from motor.pipeline_dispatcher import PipelineDispatcher
        import motor.procesa_video as pv

        monkeypatch.setattr(pv, "cargar_lineas", lambda cam: [])

        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        spool = str(tmp_path / "spool")
        dispatcher = PipelineDispatcher(
            store, project_root=str(tmp_path), spool_dir=spool, max_sent=5
        )
        unit = _unit(tmp_path, absolute=True)
        store.submit_job(C.JobRequest(
            job_id="j1", unit=unit, priority=1,
            submitted_at=time.time(), deadline_at=None,
        ))
        dispatcher.dispatch_one("g1")

        with open(os.path.join(spool, "j1.json"), encoding="utf-8") as fh:
            payload = json.load(fh)

        spec = payload["spec"]
        assert spec["kind"] == "video_segment"
        assert spec["local"] == "1"
        assert spec["cam"] == "cam1"
        assert spec["frame_from"] == 0
        assert spec["frame_to"] == 10
        assert spec["run_generation"] == "g1"
