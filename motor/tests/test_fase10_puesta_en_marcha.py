"""Tests de la Fase 10: informe de métricas y validación end-to-end local."""
from __future__ import annotations

import json
import os
import time

import numpy as np
import pytest

from motor.core import pipeline_contracts as C
from motor.core.job_store import JobStatus
from motor.pipeline_collector import PipelineCollector
from motor.pipeline_report import format_table, load_events, summarize


# ---------------------------------------------------------------------------
# Informe de métricas
# ---------------------------------------------------------------------------


def _stage(ts, stage, dur):
    return {
        "ts": ts, "tipo": "stage", "trace_id": "t", "stage": stage,
        "unit_id": "u1", "extra": {"event": "end"}, "duration_s": dur,
    }


class TestPipelineReport:
    def test_percentiles(self):
        events = [
            _stage(1.0, "inferencia", 0.10),
            _stage(2.0, "inferencia", 0.20),
            _stage(3.0, "inferencia", 0.30),
            _stage(4.0, "inferencia", 0.40),
            _stage(5.0, "aplicacion", 0.05),
            {"ts": 6.0, "tipo": "summary", "result_kind": "final"},
            {"ts": 7.0, "tipo": "queue", "counts": {"pendiente": 3, "enviado": 2}},
        ]
        rep = summarize(events)
        assert rep["distinct_units"] == 1
        assert rep["final_summaries"] == 1
        assert rep["stages"]["inferencia"]["count"] == 4
        assert rep["stages"]["inferencia"]["p50_s"] == pytest.approx(0.25, abs=1e-6)
        assert rep["stages"]["inferencia"]["p99_s"] >= 0.39
        assert rep["queue_latest"]["counts"]["pendiente"] == 3

    def test_since_filter(self):
        events = [_stage(1.0, "a", 0.1), _stage(100.0, "a", 0.2)]
        rep = summarize(events, since=50.0)
        assert rep["stages"]["a"]["count"] == 1

    def test_format_table(self):
        rep = summarize([_stage(1.0, "inferencia", 0.1)])
        table = format_table(rep)
        assert "inferencia" in table
        assert "p50" in table

    def test_load_and_cli_json(self, tmp_path, capsys):
        path = tmp_path / "m.jsonl"
        path.write_text("\n".join(json.dumps(e) for e in [
            _stage(1.0, "inferencia", 0.2),
            {"ts": 2.0, "tipo": "summary", "result_kind": "final"},
        ]) + "\n", encoding="utf-8")
        loaded = load_events([str(path)])
        assert len(loaded) == 2

        from motor.pipeline_report import main
        rc = main(["--file", str(path), "--json"])
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["stages"]["inferencia"]["count"] == 1
        assert out["summaries"] == 1


# ---------------------------------------------------------------------------
# End-to-end local (captura simulada → worker → colector)
# ---------------------------------------------------------------------------


def _make_unit(tmp_path, unit_id="u1", absolute=False):
    video_dir = tmp_path / "motor" / "videos" / "1" / "cam1"
    video_dir.mkdir(parents=True, exist_ok=True)
    video = video_dir / "evt.mp4"
    video.write_bytes(b"fake-video")
    source = str(video) if absolute else video.name
    return C.AnalysisUnit(
        unit_id=unit_id,
        event=C.MotionEventRef(
            camera=C.CameraRef(
                instance=C.InstanceRef("ojos", "g1"), local_id=1, camera_id="cam1"
            ),
            event_id="e1",
            started_at=time.time(),
        ),
        frame_range=C.FrameRange(0, 9, 1000.0, 1000.9),
        config=C.ConfigRef(version="v1", params_hash="h1"),
        source_paths={"video": source},
        requested_stages=["video_faces"],
        trace_id=C.new_trace_id(),
        created_at=time.time(),
    )


def _job(unit):
    return C.JobRequest(
        job_id="j1", unit=unit, priority=10,
        submitted_at=time.time(), deadline_at=None,
    )


class TestEndToEndLocal:
    def _run_worker(self, tmp_path, unit, processor="stub"):
        from motor.inference_pool import main

        req_path = tmp_path / "request.json"
        req_path.write_text(json.dumps(_job(unit).to_dict()), encoding="utf-8")
        out_dir = tmp_path / "returns" / "j1" / "result"
        rc = main([
            "--request", str(req_path),
            "--out-dir", str(out_dir),
            "--ruta", str(tmp_path),
            "--processor", processor,
        ])
        return rc, out_dir

    def test_stub_loop_reaches_resultado_recibido(self, tmp_path):
        from motor.core.job_store import JobStore

        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        unit = _make_unit(tmp_path)
        store.submit_job(_job(unit))

        rc, out_dir = self._run_worker(tmp_path, unit, processor="stub")
        assert rc == 0

        data = json.loads((out_dir / "result.json").read_text(encoding="utf-8"))
        assert data["job_id"] == "j1"
        assert data["unit_result"]["unit_id"] == "u1"
        assert data["unit_result"]["event_id"] == "e1"

        collector = PipelineCollector(
            store, project_root=str(tmp_path),
            returns_dir_override=str(tmp_path / "returns"),
        )
        assert collector.collect_all() == ["j1"]
        assert store.get_job("j1", "g1")["status"] == JobStatus.RESULTADO_RECIBIDO.value

    def test_real_processor_with_mocked_inference(self, tmp_path, monkeypatch):
        from motor.core.job_store import JobStore
        import motor.procesa_video as pv
        from motor.core.model import Face

        def fake_process_video(local_id, camara_id, fichero, ruta, cfg, face_every, **kwargs):
            base = os.path.join(ruta, "motor/caras/sinclasificar", str(local_id))
            for sub in (camara_id, f"{camara_id}_busto", f"{camara_id}_frame", f"{camara_id}_cuerpo"):
                os.makedirs(os.path.join(base, sub), exist_ok=True)
                with open(os.path.join(base, sub, "x.png"), "wb") as fh:
                    fh.write(b"x")
            collector = kwargs.get("collector")
            if collector is not None:
                collector.on_face(
                    Face(
                        bbox=(1, 1, 20, 20), det_score=0.9,
                        embedding=np.array([1.0, 0.0], dtype=np.float32),
                        pose=(0.0, 0.0, 0.0), landmarks=None, kps=None,
                    ),
                    0, 0.0, "saved",
                )
            if kwargs.get("resumen") is not None:
                kwargs["resumen"].update({"frames": 10, "caras_detect": 1, "caras_guard": 1})
            return 10

        monkeypatch.setattr(pv, "process_video", fake_process_video)

        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        unit = _make_unit(tmp_path)
        store.submit_job(_job(unit))

        rc, out_dir = self._run_worker(tmp_path, unit, processor="real")
        assert rc == 0

        data = json.loads((out_dir / "result.json").read_text(encoding="utf-8"))
        uri = data["unit_result"]
        assert uri["event_id"] == "e1"
        assert uri["local_id"] == 1
        assert uri["camera_id"] == "cam1"
        assert len(uri["faces"]) == 1
        assert uri["faces"][0]["embedding"] == pytest.approx([1.0, 0.0])

        collector = PipelineCollector(
            store, project_root=str(tmp_path),
            returns_dir_override=str(tmp_path / "returns"),
        )
        assert collector.collect_all() == ["j1"]
