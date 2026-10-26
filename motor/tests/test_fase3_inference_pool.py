"""Tests del entry point de pool de inferencia."""
from __future__ import annotations

import json
import os
import time

import pytest

from motor.core import pipeline_contracts as C


def _make_request(job_id: str = "j1") -> dict:
    unit = C.AnalysisUnit(
        unit_id="u1",
        event=C.MotionEventRef(
            camera=C.CameraRef(
                instance=C.InstanceRef("ojos", "g1"),
                local_id=1,
                camera_id="cam1",
            ),
            event_id="e1",
            started_at=time.time(),
        ),
        frame_range=C.FrameRange(0, 20, 1000.0, 1002.0),
        config=C.ConfigRef(version="v1", params_hash="h1"),
        source_paths={"video": "/tmp/v.mp4"},
        requested_stages=["video_faces"],
        trace_id=C.new_trace_id(),
        created_at=time.time(),
    )
    return {
        "id": job_id,
        "project": "ojos",
        "process": "video_faces",
        "priority": 10,
        "submitted_at": time.time(),
        "params": {
            "instance": "ojos",
            "run_generation": "g1",
            "unit": unit.to_dict(),
        },
    }


class TestInferencePool:
    def test_main_writes_result_json(self, tmp_path):
        req_file = tmp_path / "request.json"
        out_dir = tmp_path / "result"
        req_file.write_text(json.dumps(_make_request("j1")), encoding="utf-8")

        from motor.inference_pool import main

        import sys
        old_argv = sys.argv
        try:
            sys.argv = [
                "motor/inference_pool.py",
                "--request", str(req_file),
                "--out-dir", str(out_dir),
                "--ruta", str(tmp_path),
            ]
            rc = main()
        finally:
            sys.argv = old_argv

        assert rc == 0
        result_path = out_dir / "result.json"
        assert result_path.exists()
        data = json.loads(result_path.read_text(encoding="utf-8"))
        assert data["unit_id"] == "u1"
        assert data["instance"]["instance"] == "ojos"
        assert data["metrics"]["frames"] == 21
        assert data["kind"] == C.ResultKind.FINAL.value

    def test_main_writes_error_on_bad_request(self, tmp_path):
        req_file = tmp_path / "request.json"
        out_dir = tmp_path / "result"
        req_file.write_text(json.dumps({"id": "bad"}), encoding="utf-8")

        from motor.inference_pool import main

        import sys
        old_argv = sys.argv
        try:
            sys.argv = [
                "motor/inference_pool.py",
                "--request", str(req_file),
                "--out-dir", str(out_dir),
                "--ruta", str(tmp_path),
            ]
            rc = main()
        finally:
            sys.argv = old_argv

        assert rc == 1
        result_path = out_dir / "result.json"
        assert result_path.exists()
        data = json.loads(result_path.read_text(encoding="utf-8"))
        assert "error" in data
