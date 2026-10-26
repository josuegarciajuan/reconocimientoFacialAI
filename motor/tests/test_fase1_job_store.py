"""Tests de la Fase 1: cola duradera, generaciones e idempotencia."""
from __future__ import annotations

import time

import pytest

from motor.core import pipeline_contracts as C
from motor.core.job_store import GenerationMismatchError, JobStore, JobStatus


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


class TestGenerations:
    def test_active_generation(self, tmp_path):
        store = JobStore(str(tmp_path), "ojos")
        assert store.active_generation() is None
        store.create_generation("g1")
        assert store.active_generation() == "g1"

    def test_new_generation_deactivates_old(self, tmp_path):
        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        store.create_generation("g2")
        assert store.active_generation() == "g2"
        gens = store.generations()
        assert len(gens) == 2
        assert sum(1 for g in gens if g["is_active"]) == 1

    def test_new_generation_cancels_old_pending_jobs(self, tmp_path):
        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        store.submit_job(_job("ojos", "g1", "j1"))
        store.create_generation("g2")
        old = store.get_job("j1", "g1")
        assert old["status"] == JobStatus.CANCELADO.value


class TestEventAndUnit:
    def test_save_and_get_event(self, tmp_path):
        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        event = _event("ojos", "g1", "e1")
        store.save_event(event)
        row = store.get_event("e1", "g1")
        assert row is not None
        assert row["event_id"] == "e1"

    def test_save_and_get_unit(self, tmp_path):
        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        unit = _unit("ojos", "g1", "u1", "e1")
        store.save_unit(unit)
        row = store.get_unit("u1", "g1")
        assert row is not None
        assert row["unit_id"] == "u1"


class TestJobs:
    def test_submit_job(self, tmp_path):
        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        job = _job("ojos", "g1", "j1")
        store.submit_job(job)
        row = store.get_job("j1", "g1")
        assert row["status"] == JobStatus.PENDIENTE.value
        assert row["trace_id"] == job.unit.trace_id

    def test_list_jobs_by_status(self, tmp_path):
        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        store.submit_job(_job("ojos", "g1", "j1"))
        store.submit_job(_job("ojos", "g1", "j2"))
        pending = store.list_jobs(status=JobStatus.PENDIENTE)
        assert len(pending) == 2

    def test_set_job_status(self, tmp_path):
        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        store.submit_job(_job("ojos", "g1", "j1"))
        assert store.set_job_status("j1", "g1", JobStatus.ENVIADO)
        row = store.get_job("j1", "g1")
        assert row["status"] == JobStatus.ENVIADO.value


class TestResults:
    def test_save_result(self, tmp_path):
        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        store.submit_job(_job("ojos", "g1", "j1"))
        result = _result("ojos", "g1", "j1")
        rid = store.save_result(result)
        assert rid > 0
        job = store.get_job("j1", "g1")
        assert job["status"] == JobStatus.RESULTADO_RECIBIDO.value
        assert job["result_id"] == rid

    def test_result_from_old_generation_rejected(self, tmp_path):
        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        store.submit_job(_job("ojos", "g1", "j1"))
        store.create_generation("g2")
        result = _result("ojos", "g1", "j1")
        with pytest.raises(GenerationMismatchError):
            store.save_result(result)


class TestIdempotency:
    def test_record_application_idempotent(self, tmp_path):
        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        store.submit_job(_job("ojos", "g1", "j1"))
        result = _result("ojos", "g1", "j1")
        rid = store.save_result(result)

        first = store.record_application(
            "persona:alice:foto:1", rid, "create_foto", "persona", "alice"
        )
        assert first is True
        second = store.record_application(
            "persona:alice:foto:1", rid, "create_foto", "persona", "alice"
        )
        assert second is False
        assert store.is_applied("persona:alice:foto:1")

    def test_different_keys_independent(self, tmp_path):
        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        store.submit_job(_job("ojos", "g1", "j1"))
        result = _result("ojos", "g1", "j1")
        rid = store.save_result(result)

        assert store.record_application("k1", rid, "x", "y", "z1")
        assert store.record_application("k2", rid, "x", "y", "z2")
        assert store.is_applied("k1")
        assert store.is_applied("k2")


class TestRecovery:
    def test_pending_or_sent(self, tmp_path):
        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        store.submit_job(_job("ojos", "g1", "j1"))
        store.submit_job(_job("ojos", "g1", "j2"))
        store.set_job_status("j2", "g1", JobStatus.ENVIADO)
        jobs = store.pending_or_sent("g1")
        assert len(jobs) == 2

    def test_unapplied_results(self, tmp_path):
        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        store.submit_job(_job("ojos", "g1", "j1"))
        result = _result("ojos", "g1", "j1")
        store.save_result(result)
        unapplied = store.unapplied_results("g1")
        assert len(unapplied) == 1

    def test_jobs_without_recent_attempt(self, tmp_path):
        store = JobStore(str(tmp_path), "ojos")
        store.create_generation("g1")
        store.submit_job(_job("ojos", "g1", "j1"))
        store.set_job_status("j1", "g1", JobStatus.ENVIADO)
        # Sin intentos recientes.
        old = store.jobs_without_recent_attempt("g1", older_than_s=0.1)
        assert len(old) == 1
        # Registrar intento reciente.
        store.record_attempt("j1", "g1", "w1", JobStatus.EJECUTANDO.value, started_at=time.time())
        old = store.jobs_without_recent_attempt("g1", older_than_s=10.0)
        assert len(old) == 0


class TestInstanceIsolation:
    def test_different_instances_do_not_see_each_other(self, tmp_path):
        ojos = JobStore(str(tmp_path), "ojos")
        rf = JobStore(str(tmp_path), "rf")
        ojos.create_generation("g1")
        rf.create_generation("g1")
        ojos.submit_job(_job("ojos", "g1", "j1"))
        rf.submit_job(_job("rf", "g1", "j1"))
        assert len(ojos.list_jobs()) == 1
        assert len(rf.list_jobs()) == 1
