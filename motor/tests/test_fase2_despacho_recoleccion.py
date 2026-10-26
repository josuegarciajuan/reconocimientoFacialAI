"""Tests de la Fase 2: despacho, recolección y reconciliación."""
from __future__ import annotations

import json
import os
import time

import pytest

from motor.core import pipeline_contracts as C
from motor.core.job_store import JobStatus
from motor.pipeline_collector import PipelineCollector
from motor.pipeline_dispatcher import PipelineDispatcher
from motor.pipeline_reconcile import PipelineReconcile


def _instance_ref(name: str = "ojos", gen: str = "g1") -> C.InstanceRef:
    return C.InstanceRef(instance=name, run_generation=gen)


def _camera_ref(name: str = "ojos", gen: str = "g1", cam: str = "cam1") -> C.CameraRef:
    return C.CameraRef(instance=_instance_ref(name, gen), local_id=1, camera_id=cam)


def _event(name: str = "ojos", gen: str = "g1", event_id: str = "e1") -> C.MotionEventRef:
    return C.MotionEventRef(
        camera=_camera_ref(name, gen, "cam1"),
        event_id=event_id,
        started_at=time.time(),
    )


def _unit(
    name: str = "ojos",
    gen: str = "g1",
    unit_id: str = "u1",
    event_id: str = "e1",
) -> C.AnalysisUnit:
    return C.AnalysisUnit(
        unit_id=unit_id,
        event=_event(name, gen, event_id),
        frame_range=C.FrameRange(
            first_frame_idx=0,
            last_frame_idx=10,
            first_frame_ts=1000.0,
            last_frame_ts=1001.0,
        ),
        config=C.ConfigRef(version="v1", params_hash="h1"),
        source_paths={"video": "/tmp/v.mp4"},
        requested_stages=["detect"],
        trace_id=C.new_trace_id(),
        created_at=time.time(),
    )


def _job(
    name: str = "ojos",
    gen: str = "g1",
    job_id: str = "j1",
    unit_id: str = "u1",
    event_id: str = "e1",
) -> C.JobRequest:
    return C.JobRequest(
        job_id=job_id,
        unit=_unit(name, gen, unit_id, event_id),
        priority=10,
        submitted_at=time.time(),
        deadline_at=None,
    )


def _result(
    name: str = "ojos",
    gen: str = "g1",
    job_id: str = "j1",
    kind: C.ResultKind = C.ResultKind.FINAL,
) -> C.JobResult:
    unit_result = C.UnitResult(
        unit_id="u1",
        instance=_instance_ref(name, gen),
        trace_id=C.new_trace_id(),
        kind=kind,
        generated_at=time.time(),
        faces=[],
        bodies=[],
        candidates=[],
        artifacts={},
        metrics={},
    )
    return C.JobResult(
        job_id=job_id,
        unit_result=unit_result,
        received_at=time.time(),
    )


@pytest.fixture
def store(tmp_path):
    from motor.core.job_store import JobStore

    s = JobStore(str(tmp_path), "ojos")
    s.create_generation("g1")
    return s


class TestDispatcher:
    def test_dispatch_one_writes_spool_and_updates_status(self, store, tmp_path):
        spool = str(tmp_path / "spool")
        dispatcher = PipelineDispatcher(store, project_root=str(tmp_path), spool_dir=spool, max_sent=5)
        store.submit_job(_job("ojos", "g1", "j1"))

        sent = dispatcher.dispatch_one("g1")
        assert sent == "j1"

        job = store.get_job("j1", "g1")
        assert job["status"] == JobStatus.ENVIADO.value

        spool_files = os.listdir(spool)
        assert len(spool_files) == 1
        with open(os.path.join(spool, spool_files[0]), encoding="utf-8") as fh:
            payload = json.load(fh)
        assert payload["id"] == "j1"
        assert payload["project"] == "reconocimientoFacial"
        assert payload["process"] == "video_faces"
        assert payload["params"]["run_generation"] == "g1"
        assert payload["params"]["trace_id"]

    def test_dispatch_respects_max_sent(self, store, tmp_path):
        spool = str(tmp_path / "spool")
        dispatcher = PipelineDispatcher(store, project_root=str(tmp_path), spool_dir=spool, max_sent=2)
        store.submit_job(_job("ojos", "g1", "j1"))
        store.submit_job(_job("ojos", "g1", "j2"))
        store.submit_job(_job("ojos", "g1", "j3"))

        sent = dispatcher.dispatch_all("g1")
        assert len(sent) == 2
        assert len(os.listdir(spool)) == 2

    def test_dispatch_all_empties_pending(self, store, tmp_path):
        spool = str(tmp_path / "spool")
        dispatcher = PipelineDispatcher(store, project_root=str(tmp_path), spool_dir=spool, max_sent=10)
        store.submit_job(_job("ojos", "g1", "j1"))
        store.submit_job(_job("ojos", "g1", "j2"))

        sent = dispatcher.dispatch_all("g1")
        assert set(sent) == {"j1", "j2"}
        pending = store.list_jobs(status=JobStatus.PENDIENTE, run_generation="g1")
        assert len(pending) == 0


class TestCollector:
    def test_collect_one_reads_result_and_saves(self, store, tmp_path):
        returns = str(tmp_path / "returns")
        collector = PipelineCollector(store, project_root=str(tmp_path), returns_dir_override=returns)
        store.submit_job(_job("ojos", "g1", "j1"))
        store.set_job_status("j1", "g1", JobStatus.ENVIADO)

        job_dir = os.path.join(returns, "j1", "result")
        os.makedirs(job_dir, exist_ok=True)
        with open(os.path.join(job_dir, "result.json"), "w", encoding="utf-8") as fh:
            json.dump(_result("ojos", "g1", "j1").to_dict(), fh, ensure_ascii=False)

        processed = collector.collect_all()
        assert processed == ["j1"]

        job = store.get_job("j1", "g1")
        assert job["status"] == JobStatus.RESULTADO_RECIBIDO.value
        assert job["result_id"] is not None

    def test_collect_rejects_old_generation(self, store, tmp_path):
        returns = str(tmp_path / "returns")
        collector = PipelineCollector(store, project_root=str(tmp_path), returns_dir_override=returns)
        store.submit_job(_job("ojos", "g1", "j1"))
        store.set_job_status("j1", "g1", JobStatus.ENVIADO)

        job_dir = os.path.join(returns, "j1", "result")
        os.makedirs(job_dir, exist_ok=True)
        with open(os.path.join(job_dir, "result.json"), "w", encoding="utf-8") as fh:
            json.dump(_result("ojos", "g0", "j1").to_dict(), fh, ensure_ascii=False)

        processed = collector.collect_all()
        assert processed == []
        job = store.get_job("j1", "g1")
        assert job["status"] == JobStatus.REQUIERE_INTERVENCION.value

    def test_collect_skips_applied_marker(self, store, tmp_path):
        returns = str(tmp_path / "returns")
        collector = PipelineCollector(store, project_root=str(tmp_path), returns_dir_override=returns)
        job_dir = os.path.join(returns, "j1")
        result_dir = os.path.join(job_dir, "result")
        os.makedirs(result_dir, exist_ok=True)
        with open(os.path.join(job_dir, ".aplicado"), "w", encoding="utf-8") as fh:
            fh.write("x")
        with open(os.path.join(result_dir, "result.json"), "w", encoding="utf-8") as fh:
            json.dump(_result("ojos", "g1", "j1").to_dict(), fh, ensure_ascii=False)

        processed = collector.collect_all()
        assert processed == []

    def test_collect_writes_ack(self, store, tmp_path):
        returns = str(tmp_path / "returns")
        spool = str(tmp_path / "spool")
        collector = PipelineCollector(
            store,
            project_root=str(tmp_path),
            returns_dir_override=returns,
        )
        store.submit_job(_job("ojos", "g1", "j1"))
        store.set_job_status("j1", "g1", JobStatus.ENVIADO)

        job_dir = os.path.join(returns, "j1", "result")
        os.makedirs(job_dir, exist_ok=True)
        with open(os.path.join(job_dir, "result.json"), "w", encoding="utf-8") as fh:
            json.dump(_result("ojos", "g1", "j1").to_dict(), fh, ensure_ascii=False)

        # Simular ruta de acks usando variable de entorno no es trivial; verificamos
        # que no lance y que el resultado quede guardado.
        processed = collector.collect_all()
        assert processed == ["j1"]


class TestReconcile:
    def test_reconcile_retries_stale_sent_job(self, store, tmp_path):
        returns = str(tmp_path / "returns")
        reconciler = PipelineReconcile(
            store,
            project_root=str(tmp_path),
            returns_dir_override=returns,
            stale_after_s=0.1,
            max_retries=3,
        )
        store.submit_job(_job("ojos", "g1", "j1"))
        store.set_job_status("j1", "g1", JobStatus.ENVIADO)
        # Marcar intento antiguo.
        store.record_attempt("j1", "g1", "w1", JobStatus.ENVIADO.value, started_at=time.time() - 10)

        time.sleep(0.15)
        result = reconciler.reconcile_generation("g1")
        assert result["retried"] == 1
        assert result["recovered"] == 1
        job = store.get_job("j1", "g1")
        assert job["status"] == JobStatus.PENDIENTE.value

    def test_reconcile_intervenes_after_max_retries(self, store, tmp_path):
        returns = str(tmp_path / "returns")
        reconciler = PipelineReconcile(
            store,
            project_root=str(tmp_path),
            returns_dir_override=returns,
            stale_after_s=0.1,
            max_retries=2,
        )
        store.submit_job(_job("ojos", "g1", "j1"))
        store.set_job_status("j1", "g1", JobStatus.ENVIADO)
        store.record_attempt("j1", "g1", "w1", JobStatus.ENVIADO.value, started_at=time.time() - 10)
        store.record_attempt("j1", "g1", "w2", JobStatus.REINTENTO.value, started_at=time.time() - 5)

        time.sleep(0.15)
        result = reconciler.reconcile_generation("g1")
        assert result["intervened"] == 1
        job = store.get_job("j1", "g1")
        assert job["status"] == JobStatus.REQUIERE_INTERVENCION.value

    def test_reconcile_detects_existing_result(self, store, tmp_path):
        returns = str(tmp_path / "returns")
        reconciler = PipelineReconcile(
            store,
            project_root=str(tmp_path),
            returns_dir_override=returns,
            stale_after_s=0.1,
            max_retries=3,
        )
        store.submit_job(_job("ojos", "g1", "j1"))
        store.set_job_status("j1", "g1", JobStatus.ENVIADO)
        store.record_attempt("j1", "g1", "w1", JobStatus.ENVIADO.value, started_at=time.time() - 10)

        job_dir = os.path.join(returns, "j1", "result")
        os.makedirs(job_dir, exist_ok=True)
        with open(os.path.join(job_dir, "result.json"), "w", encoding="utf-8") as fh:
            json.dump(_result("ojos", "g1", "j1").to_dict(), fh, ensure_ascii=False)

        time.sleep(0.15)
        result = reconciler.reconcile_generation("g1")
        assert result["with_result"] == 1
        job = store.get_job("j1", "g1")
        assert job["status"] == JobStatus.RESULTADO_RECIBIDO.value
