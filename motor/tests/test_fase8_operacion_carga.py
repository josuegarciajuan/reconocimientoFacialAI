"""Tests de la Fase 8: operación, retención y carga/recuperación."""
from __future__ import annotations

import json
import os
import time

import pytest

from motor.core import pipeline_contracts as C
from motor.core.job_store import JobStatus
from motor.core.retention import (
    cleanup_units,
    make_reference_check,
    referenced_paths_from_jobs,
)
from motor.pipeline_service import PipelineService


@pytest.fixture(autouse=True)
def _sin_lineas(monkeypatch):
    """Evita que el despachador invoque ws.php/DB real durante las pruebas."""
    import motor.procesa_video as pv

    monkeypatch.setenv("RF_SUPERSERVER_PROJECT", "ojos")
    monkeypatch.setattr(pv, "cargar_lineas", lambda cam: [])


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def _make_project(tmp_path):
    (tmp_path / "motor" / "videos" / "1" / "cam1").mkdir(parents=True, exist_ok=True)
    (tmp_path / "motor" / "logs").mkdir(parents=True, exist_ok=True)
    return tmp_path


def _unit(tmp_path, unit_id="u1", event_id="e1"):
    return C.AnalysisUnit(
        unit_id=unit_id,
        event=C.MotionEventRef(
            camera=C.CameraRef(
                instance=C.InstanceRef("ojos", "g1"), local_id=1, camera_id="cam1"
            ),
            event_id=event_id,
            started_at=time.time(),
        ),
        frame_range=C.FrameRange(0, 9, 1000.0, 1000.9),
        config=C.ConfigRef(version="v1", params_hash="h1"),
        source_paths={"video": "/tmp/seg.mp4"},
        requested_stages=["video_faces"],
        trace_id=C.new_trace_id(),
        created_at=time.time(),
    )


def _job(tmp_path, job_id="j1", unit_id="u1"):
    return C.JobRequest(
        job_id=job_id,
        unit=_unit(tmp_path, unit_id=unit_id),
        priority=10,
        submitted_at=time.time(),
        deadline_at=None,
    )


def _result(job_id="j1", event_id="e1"):
    uri = C.UnitResult(
        unit_id="u1",
        instance=C.InstanceRef("ojos", "g1"),
        trace_id=C.new_trace_id(),
        kind=C.ResultKind.FINAL,
        generated_at=time.time(),
        faces=[],
        bodies=[],
        candidates=[],
        artifacts={},
        metrics={"frames": 10},
        event_id=event_id,
        local_id=1,
        camera_id="cam1",
    )
    return C.JobResult(job_id=job_id, unit_result=uri, received_at=time.time())


def _write_result(returns_dir, job_id, result):
    job_dir = os.path.join(returns_dir, job_id, "result")
    os.makedirs(job_dir, exist_ok=True)
    with open(os.path.join(job_dir, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(result.to_dict(), fh, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Retención
# ---------------------------------------------------------------------------


class TestRetention:
    def _event(self, units_root, name, mtime):
        d = os.path.join(units_root, name)
        os.makedirs(d, exist_ok=True)
        f = os.path.join(d, "seg.mp4")
        with open(f, "wb") as fh:
            fh.write(b"x" * 100)
        os.utime(f, (mtime, mtime))
        return d, f

    def test_removes_old_unreferenced(self, tmp_path):
        units = str(tmp_path / ".units")
        now = time.time()
        old_dir, old_file = self._event(units, "old", now - 1000)
        new_dir, _ = self._event(units, "new", now)
        ref_dir, ref_file = self._event(units, "ref", now - 1000)

        check = make_reference_check({ref_file})
        report = cleanup_units(units, max_age_s=100, is_referenced=check, now=now)

        assert old_dir in report.removed_dirs
        assert not os.path.exists(old_dir)
        assert new_dir in report.kept_dirs
        assert ref_dir in report.kept_dirs
        assert report.bytes_freed >= 100

    def test_dry_run(self, tmp_path):
        units = str(tmp_path / ".units")
        now = time.time()
        old_dir, _ = self._event(units, "old", now - 1000)
        report = cleanup_units(units, max_age_s=100, dry_run=True, now=now)
        assert old_dir in report.removed_dirs
        assert os.path.exists(old_dir)

    def test_referenced_paths_from_jobs(self):
        rows = [
            {"job_json": json.dumps({
                "unit": {"source_paths": {"video": "/a/seg1.mp4", "segment": "/a/seg1.mp4"}}
            })},
            {"job_json": json.dumps({
                "unit": {"source_paths": {"video": "/a/seg2.mp4"}}
            })},
            {"job_json": "no-json"},
        ]
        refs = referenced_paths_from_jobs(rows)
        assert os.path.abspath("/a/seg1.mp4") in refs
        assert os.path.abspath("/a/seg2.mp4") in refs


# ---------------------------------------------------------------------------
# Servicio
# ---------------------------------------------------------------------------


class TestPipelineService:
    def _service(self, tmp_path, **kwargs):
        _make_project(tmp_path)
        spool = str(tmp_path / "spool")
        returns = str(tmp_path / "returns")
        os.makedirs(spool, exist_ok=True)
        os.makedirs(returns, exist_ok=True)
        service = PipelineService(
            str(tmp_path), spool_dir=spool, returns_dir_override=returns, **kwargs
        )
        service.store.create_generation("g1")
        return service, spool, returns

    def test_generation_created(self, tmp_path):
        service, _spool, _returns = self._service(tmp_path)
        gen = service.ensure_generation()
        assert service.store.active_generation() == gen

    def test_run_once_dispatches_and_collects(self, tmp_path):
        service, spool, returns = self._service(tmp_path, max_sent=10)
        for i in range(3):
            service.store.submit_job(_job(tmp_path, job_id=f"j{i}", unit_id=f"u{i}"))

        out = service.run_once()
        assert out["dispatched"] == 3
        assert len(os.listdir(spool)) == 3

        sent = service.store.list_jobs(status=JobStatus.ENVIADO)
        assert len(sent) == 3
        _write_result(returns, "j0", _result(job_id="j0"))

        out2 = service.run_once()
        assert out2["collected"] == 1
        assert service.store.get_job("j0", out["generation"])["status"] == JobStatus.RESULTADO_RECIBIDO.value

    def test_status_structure(self, tmp_path):
        service, _spool, _returns = self._service(tmp_path)
        service.store.submit_job(_job(tmp_path))
        status = service.status()
        assert status["instance"] == "ojos"
        assert "generation" in status
        assert "queues" in status
        assert "sessions" in status
        assert status["queues"]["pendiente"] == 1

    def test_start_stop_threads(self, tmp_path):
        service, _spool, _returns = self._service(
            tmp_path,
            intervals={
                "dispatch": 0.02,
                "collect": 0.02,
                "reconcile": 0.05,
                "sessions": 0.05,
                "retention": 0.05,
                "metrics": 0.05,
            },
        )
        service.start()
        time.sleep(0.25)
        service.stop()
        assert service.status()["running"] is False
        assert service._cycles["dispatch"] >= 1


# ---------------------------------------------------------------------------
# Carga y drenaje
# ---------------------------------------------------------------------------


class TestLoadDrain:
    def test_100_jobs_drain_in_windows(self, tmp_path):
        _make_project(tmp_path)
        spool = str(tmp_path / "spool")
        returns = str(tmp_path / "returns")
        os.makedirs(spool, exist_ok=True)
        os.makedirs(returns, exist_ok=True)
        service = PipelineService(
            str(tmp_path),
            spool_dir=spool,
            returns_dir_override=returns,
            max_sent=20,
            sink=__import__(
                "motor.core.result_publisher", fromlist=["NullSink"]
            ).NullSink(),
        )
        service.store.create_generation("g1")
        gen = "g1"
        total = 100
        for i in range(total):
            service.store.submit_job(_job(tmp_path, job_id=f"j{i:03d}", unit_id=f"u{i:03d}"))

        rounds = 0
        while True:
            rounds += 1
            dispatched = service.dispatcher.run_once()
            sent = service.store.list_jobs(status=JobStatus.ENVIADO, run_generation=gen, limit=1000)
            for row in sent:
                _write_result(returns, row["job_id"], _result(job_id=row["job_id"]))
            collected = service.collector.run_once()
            service.reconciler.run_once()
            if collected == 0 and not dispatched and rounds > 10:
                break
            done = service.store.list_jobs(
                status=JobStatus.RESULTADO_RECIBIDO, run_generation=gen, limit=1000
            )
            if len(done) >= total:
                break
            assert rounds <= 10, f"no drenó en 10 rondas ({len(done)}/{total})"

        done = service.store.list_jobs(
            status=JobStatus.RESULTADO_RECIBIDO, run_generation=gen, limit=1000
        )
        assert len(done) == total
        # Sin duplicados en resultados.
        with service.store._conn() as conn:
            n = conn.execute(
                "SELECT COUNT(*) AS c FROM results WHERE instance = ? AND run_generation = ?",
                (service.instance, gen),
            ).fetchone()["c"]
        assert int(n) == total


class TestDuplicateResults:
    def test_collect_same_result_twice_is_idempotent(self, tmp_path):
        _make_project(tmp_path)
        spool = str(tmp_path / "spool")
        returns = str(tmp_path / "returns")
        os.makedirs(spool, exist_ok=True)
        os.makedirs(returns, exist_ok=True)
        service = PipelineService(
            str(tmp_path), spool_dir=spool, returns_dir_override=returns, max_sent=10
        )
        service.store.create_generation("g1")
        gen = "g1"
        service.store.submit_job(_job(tmp_path, job_id="j1", unit_id="u1"))
        service.dispatcher.run_once()
        _write_result(returns, "j1", _result(job_id="j1"))

        assert service.collector.run_once() == ["j1"]
        # Forzar una segunda ingesta del mismo result.json (se elimina el
        # marcador de recolección) para probar la idempotencia del JobStore.
        marker = os.path.join(returns, "j1", ".pipeline_collected")
        if os.path.exists(marker):
            os.remove(marker)
        service.collector.run_once()
        with service.store._conn() as conn:
            n = conn.execute(
                "SELECT COUNT(*) AS c FROM results WHERE instance = ? AND run_generation = ?",
                (service.instance, gen),
            ).fetchone()["c"]
        assert int(n) == 1
