"""Tests de la Fase 7: optimizaciones del camino crítico."""
from __future__ import annotations

import time

import pytest

from motor.core.batching import Batcher
from motor.core.change_signal import ChangeSignal, PeriodicReconciler
from motor.core.concurrency import ConcurrencyConfig, derive_workers, from_env
from motor.core.gallery_cache import CachedGalleryMatcher, GalleryEntry
from motor.core.quality_gate import (
    QualityGateError,
    assert_no_regression,
    compare_reports,
    load_report,
)
from motor.core.quality_reference import QualityReport, QualityResult


# ---------------------------------------------------------------------------
# Galería cacheada
# ---------------------------------------------------------------------------


def _gallery():
    return [
        GalleryEntry(person_id=1, label="Ana", embedding=(1.0, 0.0, 0.0)),
        GalleryEntry(person_id=2, label="Bea", embedding=(0.0, 1.0, 0.0)),
    ]


class TestCachedGallery:
    def test_top2(self):
        g = CachedGalleryMatcher()
        g.set_gallery("v1", _gallery())
        r = g.match([0.9, 0.1, 0.0])
        assert r.person_id == 1
        assert r.score > 0.9
        assert r.second_score < 0.2
        assert r.margin > 0.7

    def test_cache_hit(self):
        g = CachedGalleryMatcher()
        g.set_gallery("v1", _gallery())
        emb = [0.9, 0.1, 0.0]
        r1 = g.match(emb)
        r2 = g.match(emb)
        assert r1 == r2
        stats = g.stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_version_change_clears_cache(self):
        g = CachedGalleryMatcher()
        g.set_gallery("v1", _gallery())
        g.match([0.9, 0.1, 0.0])
        g.set_gallery("v2", _gallery())
        assert g.stats()["cache_size"] == 0
        assert g.version == "v2"

    def test_match_batch_matches_individual(self):
        g = CachedGalleryMatcher()
        g.set_gallery("v1", _gallery())
        embs = [[0.9, 0.1, 0.0], [0.1, 0.9, 0.0], [0.5, 0.5, 0.0]]
        batch = g.match_batch(embs)
        individual = [g.match(e) for e in embs]
        assert [b.person_id for b in batch] == [i.person_id for i in individual]
        for b, i in zip(batch, individual):
            assert b.score == pytest.approx(i.score, abs=1e-5)

    def test_empty_gallery(self):
        g = CachedGalleryMatcher()
        g.set_gallery("v1", [])
        assert g.match([1.0, 0.0, 0.0]) is None
        assert g.match_batch([[1.0, 0.0, 0.0]]) == [None]

    def test_invalidate(self):
        g = CachedGalleryMatcher()
        g.set_gallery("v1", _gallery())
        g.invalidate()
        assert g.size == 0
        assert g.match([1.0, 0.0, 0.0]) is None


# ---------------------------------------------------------------------------
# Batching
# ---------------------------------------------------------------------------


class TestBatcher:
    def test_flush_by_size(self):
        out = []
        b = Batcher(out.append, max_size=3, max_wait_s=10.0)
        assert b.add(1) is False
        assert b.add(2) is False
        assert b.add(3) is True
        assert out == [[1, 2, 3]]
        assert b.pending == 0

    def test_flush_by_wait(self):
        out = []
        now = [0.0]
        b = Batcher(out.append, max_size=10, max_wait_s=0.5, clock=lambda: now[0])
        b.add("a")
        now[0] = 0.4
        assert b.flush_if_due() == 0
        now[0] = 0.6
        assert b.flush_if_due() == 1
        assert out == [["a"]]

    def test_manual_flush(self):
        out = []
        b = Batcher(out.append, max_size=10, max_wait_s=10.0)
        b.add("x")
        assert b.flush() == 1
        assert out == [["x"]]
        assert b.flush() == 0

    def test_stats(self):
        out = []
        b = Batcher(out.append, max_size=2, max_wait_s=10.0)
        b.add(1)
        b.add(2)
        b.flush()
        s = b.stats_dict()
        assert s["batches_flushed"] == 1
        assert s["items_flushed"] == 2
        assert s["flushes_by_size"] == 1
        assert s["flushes_manual"] == 0

    def test_consumer_error_does_not_raise(self):
        def boom(batch):
            raise RuntimeError("fallo")

        b = Batcher(boom, max_size=1, max_wait_s=10.0)
        assert b.add(1) is True


# ---------------------------------------------------------------------------
# Gate de calidad
# ---------------------------------------------------------------------------


def _report(passed_ids, failed_ids, scores=None):
    scores = scores or {}
    results = [
        QualityResult(case_id=c, dimension="deteccion", passed=True, score=scores.get(c, 1.0), details={})
        for c in passed_ids
    ] + [
        QualityResult(case_id=c, dimension="deteccion", passed=False, score=scores.get(c, 0.0), details={})
        for c in failed_ids
    ]
    return QualityReport(
        evaluated_at=time.time(),
        total=len(results),
        passed=len(passed_ids),
        failed=len(failed_ids),
        by_dimension={"deteccion": {"passed": len(passed_ids), "failed": len(failed_ids)}},
        results=results,
    )


class TestQualityGate:
    def test_no_regression(self):
        base = _report(["a", "b"], [], {"a": 1.0, "b": 0.9})
        cur = _report(["a", "b"], [], {"a": 1.0, "b": 0.9})
        r = compare_reports(base, cur)
        assert r.passed is True
        assert r.issues == []

    def test_score_drop_within_tolerance(self):
        base = _report(["a"], [], {"a": 1.0})
        cur = _report(["a"], [], {"a": 0.99})
        assert compare_reports(base, cur, tolerance=0.02).passed is True

    def test_score_drop_beyond_tolerance(self):
        base = _report(["a"], [], {"a": 1.0})
        cur = _report(["a"], [], {"a": 0.90})
        r = compare_reports(base, cur, tolerance=0.02)
        assert r.passed is False
        assert r.issues[0].case_id == "a"

    def test_passed_to_failed(self):
        base = _report(["a"], [])
        cur = _report([], ["a"])
        r = compare_reports(base, cur)
        assert r.passed is False
        assert "falla ahora" in r.issues[0].reason

    def test_missing_case(self):
        base = _report(["a", "b"], [])
        cur = _report(["a"], [])
        r = compare_reports(base, cur)
        assert r.passed is False
        assert r.issues[0].reason == "caso ausente en el informe actual"

    def test_assert_raises(self):
        base = _report(["a"], [], {"a": 1.0})
        cur = _report([], ["a"])
        with pytest.raises(QualityGateError):
            assert_no_regression(base, cur)

    def test_load_report_roundtrip(self, tmp_path):
        rep = _report(["a"], [], {"a": 0.95})
        path = str(tmp_path / "report.json")
        rep.write(path)
        loaded = load_report(path)
        assert loaded.passed == 1
        assert loaded.results[0].case_id == "a"
        assert loaded.results[0].score == pytest.approx(0.95)


# ---------------------------------------------------------------------------
# Concurrencia
# ---------------------------------------------------------------------------


class TestConcurrency:
    def test_derive_by_cpu(self):
        assert derive_workers(4, 0, per_worker_mem_mb=2048, max_workers=8) == 4

    def test_derive_by_memory(self):
        assert derive_workers(16, 4096, per_worker_mem_mb=2048, max_workers=8) == 2

    def test_env_override(self):
        cfg = from_env({"RF_WORKERS": "3", "RF_THREADS_PER_WORKER": "2",
                        "RF_BATCH_SIZE": "16", "RF_BATCH_WAIT_MS": "100"},
                       cpu_count=8, mem_mb=32000)
        assert cfg.workers == 3
        assert cfg.threads_per_worker == 2
        assert cfg.batch_size == 16
        assert cfg.batch_wait_s == pytest.approx(0.1)

    def test_defaults(self):
        cfg = from_env({}, cpu_count=8, mem_mb=0)
        assert cfg.workers >= 1
        assert cfg.threads_per_worker >= 1
        assert isinstance(cfg, ConcurrencyConfig)


# ---------------------------------------------------------------------------
# Señal de cambios y reconciliación
# ---------------------------------------------------------------------------


class TestChangeSignal:
    def test_notify_increments_version(self):
        s = ChangeSignal()
        assert s.version == 0
        assert s.notify() == 1
        assert s.version == 1

    def test_wait_detects_change(self):
        s = ChangeSignal()
        v = s.version
        s.notify()
        assert s.wait(timeout=0.1, last_version=v) is True

    def test_wait_timeout_without_change(self):
        s = ChangeSignal()
        v = s.version
        assert s.wait(timeout=0.01, last_version=v) is False

    def test_close(self):
        s = ChangeSignal()
        s.close()
        assert s.closed is True


class TestPeriodicReconciler:
    def test_respects_interval(self):
        calls = []
        now = [0.0]
        r = PeriodicReconciler(1.0, lambda: calls.append(now[0]), clock=lambda: now[0])
        assert r.run_if_due() is True
        now[0] = 0.5
        assert r.run_if_due() is False
        now[0] = 1.1
        assert r.run_if_due() is True
        assert len(calls) == 2

    def test_force(self):
        calls = []
        r = PeriodicReconciler(10.0, lambda: calls.append(1), clock=lambda: 1.0)
        r.run_if_due()
        assert r.force() is True
        assert len(calls) == 2

    def test_callback_error_counted(self):
        def boom():
            raise RuntimeError("x")

        r = PeriodicReconciler(0.0, boom, clock=lambda: 1.0)
        assert r.run_if_due() is True
        assert r.stats()["errors"] == 1


class TestCachedGalleryInSession:
    def test_session_batch_matches_individual(self):
        from motor.core.pipeline_contracts import (
            BoundingBox, CameraRef, FaceDetection, InstanceRef, ResultKind, UnitResult,
        )
        from motor.core.recognition_session import RecognitionSession, SessionKey

        def face(idx, ts, emb, bbox):
            return FaceDetection(
                detection_id=f"d{idx}", frame_idx=idx, frame_ts=ts,
                bbox=BoundingBox(*bbox), keypoints={}, confidence=0.9,
                embedding=emb, quality_score=0.9, sharpness=None, is_profile=False,
            )

        unit = UnitResult(
            unit_id="u1", instance=InstanceRef("ojos", "g1"), trace_id="t1",
            kind=ResultKind.FINAL, generated_at=time.time(),
            faces=[
                face(0, 0.0, [0.9, 0.1, 0.0], (0, 0, 10, 10)),
                face(0, 0.0, [0.1, 0.9, 0.0], (50, 50, 60, 60)),
            ],
            bodies=[], candidates=[], artifacts={}, metrics={},
            event_id="e1", local_id=1, camera_id="cam1",
        )
        key = SessionKey(CameraRef(InstanceRef("ojos", "g1"), 1, "cam1"), "e1")
        g = CachedGalleryMatcher()
        g.set_gallery("v1", _gallery())
        s = RecognitionSession(key, gallery=g)
        s.add(unit)
        early = s.early_result()
        assert sorted(c.person_id for c in early.candidates) == [1, 2]
        # La sesión usó el camino por lotes.
        assert g.stats()["batch_calls"] == 1
