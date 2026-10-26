"""Tests de la Fase 3: worker de inferencia reutilizable."""
from __future__ import annotations

import time

import pytest

from motor.core import pipeline_contracts as C
from motor.inference_worker import (
    InferenceContext,
    InferenceWorker,
    InferenceWorkerError,
    ModelCache,
)


def _unit(unit_id: str = "u1") -> C.AnalysisUnit:
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
        frame_range=C.FrameRange(0, 10, 1000.0, 1001.0),
        config=C.ConfigRef(version="v1", params_hash="h1"),
        source_paths={"video": "/tmp/v.mp4"},
        requested_stages=["detect"],
        trace_id=C.new_trace_id(),
        created_at=time.time(),
    )


def _job(job_id: str = "j1", unit_id: str = "u1") -> C.JobRequest:
    return C.JobRequest(
        job_id=job_id,
        unit=_unit(unit_id),
        priority=10,
        submitted_at=time.time(),
        deadline_at=None,
    )


def _result(unit_id: str = "u1") -> C.UnitResult:
    return C.UnitResult(
        unit_id=unit_id,
        instance=C.InstanceRef("ojos", "g1"),
        trace_id=C.new_trace_id(),
        kind=C.ResultKind.FINAL,
        generated_at=time.time(),
        faces=[],
        bodies=[],
        candidates=[],
        artifacts={},
        metrics={"frames": 10},
    )


class TestModelCache:
    def test_get_tracks_usage(self):
        loads = []

        def loader(det_size):
            loads.append(det_size)
            return f"model-{det_size}"

        cache = ModelCache(loader=loader, max_models=2)
        m1 = cache.get((640, 640))
        m2 = cache.get((640, 640))
        assert m1 == m2 == "model-(640, 640)"
        assert len(loads) == 1
        stats = cache.stats()
        assert stats["loads"] == 1
        assert stats["hits"] == 1

    def test_evict_lru(self):
        cache = ModelCache(loader=lambda ds: f"m{ds}", max_models=2)
        cache.get((640, 640))
        time.sleep(0.01)
        cache.get((1280, 1280))
        evicted = cache.evict_lru()
        assert evicted == [(640, 640)]
        remaining = cache.stats()["cached_sizes"]
        assert remaining == [(1280, 1280)]


class TestInferenceWorker:
    def test_process_request_with_registered_processor(self, tmp_path):
        calls = []

        def processor(unit, ctx):
            calls.append(unit.unit_id)
            return _result(unit.unit_id)

        worker = InferenceWorker(project_root=str(tmp_path))
        worker.register_processor("detect", processor)

        result = worker.process_request(_job("j1", "u1"))
        assert result.unit_id == "u1"
        assert result.metrics["frames"] == 10
        assert calls == ["u1"]
        assert worker.stats()["jobs_processed"] == 1

    def test_process_request_missing_processor(self, tmp_path):
        worker = InferenceWorker(project_root=str(tmp_path))
        with pytest.raises(InferenceWorkerError, match="No hay procesador"):
            worker.process_request(_job("j1", "u1"))

    def test_processor_can_access_model_cache(self, tmp_path):
        def processor(unit, ctx):
            model = ctx.worker.model_cache.get((640, 640))
            return C.UnitResult(
                unit_id=unit.unit_id,
                instance=C.InstanceRef("ojos", "g1"),
                trace_id=unit.trace_id,
                kind=C.ResultKind.FINAL,
                generated_at=time.time(),
                faces=[],
                bodies=[],
                candidates=[],
                artifacts={},
                metrics={"model": str(model)},
            )

        worker = InferenceWorker(
            project_root=str(tmp_path),
            model_cache=ModelCache(loader=lambda ds: f"model-{ds}"),
        )
        worker.register_processor("detect", processor)
        result = worker.process_request(_job("j1", "u1"))
        assert result.metrics["model"] == "model-(640, 640)"

    def test_eviction_under_memory_pressure(self, tmp_path):
        evicted = []

        def loader(det_size):
            return f"model-{det_size}"

        class CustomCache(ModelCache):
            def should_evict(self):
                return True

            def evict_lru(self):
                evicted.extend(super().evict_lru())
                return evicted

        cache = CustomCache(loader=loader, max_models=2)
        cache.get((640, 640))

        worker = InferenceWorker(project_root=str(tmp_path), model_cache=cache)
        worker.register_processor("detect", lambda unit, ctx: _result(unit.unit_id))
        worker.process_request(_job("j1", "u1"))

        assert evicted == [(640, 640)]

    def test_context_records_stages(self, tmp_path):
        recorded = []

        class FakeMetrics:
            def marker(self, trace_id, stage, **kwargs):
                recorded.append(("marker", stage.value))

            def stage_start(self, trace_id, stage, **kwargs):
                recorded.append(("start", stage.value))
                return time.time()

            def stage_end(self, trace_id, stage, ts_start, **kwargs):
                recorded.append(("end", stage.value))

        worker = InferenceWorker(
            project_root=str(tmp_path),
            metrics=FakeMetrics(),
        )
        worker.register_processor("detect", lambda unit, ctx: _result(unit.unit_id))
        worker.process_request(_job("j1", "u1"))

        assert ("start", "inferencia") in recorded
        assert ("end", "inferencia") in recorded


class TestInferenceContext:
    def test_context_exposes_worker_and_unit(self, tmp_path):
        worker = InferenceWorker(project_root=str(tmp_path))
        unit = _unit("u1")
        ctx = InferenceContext(worker, unit)
        assert ctx.worker is worker
        assert ctx.unit is unit
        assert ctx.trace_id == unit.trace_id
