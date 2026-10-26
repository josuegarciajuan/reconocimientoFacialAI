"""Tests de la Fase 4: ciclo de vida de artefactos y sesiones."""
from __future__ import annotations

import os
import time

import pytest

from motor.core.artifact_lifecycle import ArtifactLifecycle, ArtifactManifest
from motor.core.pipeline_contracts import (
    BoundingBox,
    CameraRef,
    FaceDetection,
    InstanceRef,
    RecognitionCandidate,
    ResultKind,
    UnitResult,
)
from motor.core.recognition_session import RecognitionSession, SessionKey, SessionStore


class TestArtifactLifecycle:
    def test_create_and_publish_manifest(self, tmp_path):
        al = ArtifactLifecycle(str(tmp_path))
        artifact = tmp_path / "face.png"
        artifact.write_text("face", encoding="utf-8")
        manifest = al.create_manifest("m1", "u1", "j1", {"face": str(artifact)})
        assert not al.is_published("m1")
        published = al.publish_manifest("m1")
        assert al.is_published("m1")
        assert published.is_complete()

    def test_publish_incomplete_fails(self, tmp_path):
        al = ArtifactLifecycle(str(tmp_path))
        manifest = al.create_manifest("m1", "u1", "j1", {"face": str(tmp_path / "missing.png")})
        with pytest.raises(Exception):
            al.publish_manifest("m1")

    def test_cleanup_unreferenced(self, tmp_path):
        al = ArtifactLifecycle(str(tmp_path))
        kept = tmp_path / "kept.txt"
        orphan = tmp_path / "orphan.txt"
        kept.write_text("x", encoding="utf-8")
        orphan.write_text("y", encoding="utf-8")
        # Asegurar que el huérfano sea viejo.
        os.utime(str(orphan), (time.time() - 120, time.time() - 120))

        manifest = al.create_manifest("m1", "u1", "j1", {"kept": str(kept)})
        al.publish_manifest("m1")

        removed = al.cleanup_unreferenced(str(tmp_path), min_age_s=60.0)
        assert str(orphan) in removed
        assert str(kept) not in removed
        assert orphan.exists() is False
        assert kept.exists() is True

    def test_dry_run_does_not_delete(self, tmp_path):
        al = ArtifactLifecycle(str(tmp_path))
        orphan = tmp_path / "orphan.txt"
        orphan.write_text("y", encoding="utf-8")
        os.utime(str(orphan), (time.time() - 120, time.time() - 120))

        removed = al.cleanup_unreferenced(str(tmp_path), dry_run=True, min_age_s=60.0)
        assert str(orphan) in removed
        assert orphan.exists() is True


class TestRecognitionSession:
    def _result(self, unit_id: str = "u1", face_count: int = 1) -> UnitResult:
        faces = [
            FaceDetection(
                detection_id=f"d{i}",
                frame_idx=i,
                frame_ts=1000.0 + i,
                bbox=BoundingBox(0, 0, 10, 10),
                keypoints={},
                confidence=0.9,
                embedding=None,
                quality_score=0.8,
                sharpness=None,
                is_profile=False,
            )
            for i in range(face_count)
        ]
        return UnitResult(
            unit_id=unit_id,
            instance=InstanceRef("ojos", "g1"),
            trace_id="t1",
            kind=ResultKind.FINAL,
            generated_at=time.time(),
            faces=faces,
            bodies=[],
            candidates=[],
            artifacts={},
            metrics={},
        )

    def test_add_and_early_result(self):
        key = SessionKey(CameraRef(InstanceRef("ojos", "g1"), 1, "cam1"), "e1")
        session = RecognitionSession(key)
        session.add(self._result("u1", 2))
        early = session.early_result()
        assert early is not None
        assert early.kind == ResultKind.TEMPRANO
        assert len(early.faces) == 2
        assert len(early.candidates) == 2
        assert all(not c.is_confirmed for c in early.candidates)

    def test_final_result_requires_close(self):
        key = SessionKey(CameraRef(InstanceRef("ojos", "g1"), 1, "cam1"), "e1")
        session = RecognitionSession(key)
        session.add(self._result("u1", 1))
        assert session.final_result() is None
        session.close()
        final = session.final_result()
        assert final is not None
        assert final.kind == ResultKind.FINAL

    def test_add_after_close_raises(self):
        key = SessionKey(CameraRef(InstanceRef("ojos", "g1"), 1, "cam1"), "e1")
        session = RecognitionSession(key)
        session.close()
        with pytest.raises(RuntimeError):
            session.add(self._result("u1", 1))

    def test_session_store(self):
        store = SessionStore()
        key = SessionKey(CameraRef(InstanceRef("ojos", "g1"), 1, "cam1"), "e1")
        session = store.get_or_create(key)
        session.add(self._result("u1", 1))
        assert store.get(key) is session
        store.close(key)
        assert session.is_closed
        assert len(store.all_stats()) == 1
