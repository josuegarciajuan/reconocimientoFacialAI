"""Publicación idempotente y coordinación de sesiones de reconocimiento.

Separación de responsabilidades:

- ``RecognitionSession`` decide *qué* se ha visto (agrupación + candidatos).
- ``PublicationSink`` aplica el resultado en la galería/BD (inyectable).
- ``ResultPublisher`` garantiza idempotencia y orden de publicación.
- ``SessionCoordinator`` enruta unidades a sesiones, publica resultados
  tempranos y cierra los finales.

El sink real (galería/BD/panel) se implementará en la integración; en esta fase
se entrega el coordinador y un sink en memoria para pruebas.
"""
from __future__ import annotations

import time
from typing import Any, Protocol

from motor.core.pipeline_contracts import (
    CameraRef,
    RecognitionCandidate,
    ResultKind,
    UnitResult,
)
from motor.core.recognition_session import (
    GalleryMatcher,
    RecognitionSession,
    SessionConfig,
    SessionKey,
    SessionStore,
)


class PublicationSink(Protocol):
    """Destino de publicación (galería/BD/panel)."""

    def upsert(
        self,
        *,
        publication_key: str,
        result: UnitResult,
        candidate: RecognitionCandidate,
        confirmed: bool,
    ) -> None:
        ...


class NullSink:
    """Sink que no hace nada (bootstrap o pruebas que no verifican efectos)."""

    def upsert(self, *, publication_key, result, candidate, confirmed) -> None:
        return None


class InMemorySink:
    """Sink de prueba que registra upserts por clave estable."""

    def __init__(self):
        self.records: dict[str, dict[str, Any]] = {}

    def upsert(self, *, publication_key, result, candidate, confirmed) -> None:
        self.records[publication_key] = {
            "publication_key": publication_key,
            "kind": result.kind.value,
            "event_id": result.event_id,
            "camera_id": result.camera_id,
            "candidate_id": candidate.candidate_id,
            "person_id": candidate.person_id,
            "person_label": candidate.person_label,
            "score": candidate.score,
            "confirmed": bool(confirmed),
            "updated_at": time.time(),
        }


class JsonlSink:
    """Sink operativo que escribe una línea JSON por publicación.

    No sustituye a la galería/BD real; sirve para observar el pipeline,
    validar en carga y como puente hasta conectar el sink definitivo.
    """

    def __init__(self, path: str):
        import os
        import threading

        self.path = path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    def upsert(self, *, publication_key, result, candidate, confirmed) -> None:
        import json

        record = {
            "ts": time.time(),
            "publication_key": publication_key,
            "kind": result.kind.value,
            "event_id": result.event_id,
            "camera_id": result.camera_id,
            "candidate_id": candidate.candidate_id,
            "person_id": candidate.person_id,
            "person_label": candidate.person_label,
            "score": candidate.score,
            "confirmed": bool(confirmed),
        }
        try:
            with self._lock:
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError:
            pass


class ResultPublisher:
    """Publica resultados de forma idempotente."""

    def __init__(self, job_store, sink: PublicationSink | None = None):
        self.store = job_store
        self.sink = sink or NullSink()

    def _idempotency_key(
        self, result: UnitResult, candidate: RecognitionCandidate
    ) -> tuple[str, str, str]:
        kind = "final" if result.kind == ResultKind.FINAL else "early"
        publication_key = (
            f"{result.instance.instance}:{result.event_id}:{candidate.candidate_id}"
        )
        # Incluye la persona: si el candidato temprano cambia de identidad, se
        # publica la actualización (el sink hace upsert por `publication_key`).
        idem = f"{publication_key}:{kind}:{candidate.person_id}"
        return publication_key, kind, idem

    def publish(self, result: UnitResult | None, *, result_id: int = 0) -> int:
        """Publica los candidatos identificados. Devuelve cuántos se aplicaron."""
        if result is None:
            return 0
        published = 0
        for candidate in result.candidates:
            if candidate.person_id is None:
                continue
            publication_key, kind, idem = self._idempotency_key(result, candidate)
            if self.store.is_applied(idem):
                continue
            self.sink.upsert(
                publication_key=publication_key,
                result=result,
                candidate=candidate,
                confirmed=bool(candidate.is_confirmed),
            )
            self.store.record_application(
                key=idem,
                result_id=result_id,
                application_type=f"publish_{kind}",
                target_type="candidate",
                target_id=idem,
                metadata={
                    "publication_key": publication_key,
                    "candidate_id": candidate.candidate_id,
                    "person_id": candidate.person_id,
                    "kind": kind,
                    "confirmed": bool(candidate.is_confirmed),
                },
            )
            published += 1
        return published


class SessionCoordinator:
    """Enruta unidades a sesiones y publica temprano/final."""

    def __init__(
        self,
        publisher: ResultPublisher,
        *,
        config: SessionConfig | None = None,
        gallery: GalleryMatcher | None = None,
        close_after_s: float = 30.0,
        sessions: SessionStore | None = None,
    ):
        self.publisher = publisher
        self.config = config
        self.gallery = gallery
        self.close_after_s = float(close_after_s)
        self.sessions = sessions or SessionStore()

    def _key(self, result: UnitResult) -> SessionKey | None:
        if not result.event_id or not result.camera_id:
            return None
        camera = CameraRef(
            instance=result.instance,
            local_id=int(result.local_id or 0),
            camera_id=result.camera_id,
        )
        return SessionKey(camera=camera, event_id=result.event_id)

    def ingest(self, result: UnitResult, *, result_id: int = 0) -> dict[str, Any]:
        """Incorpora una unidad y publica un resultado temprano si procede."""
        key = self._key(result)
        if key is None:
            return {"status": "sin_contexto", "added": 0, "published": 0}
        session = self.sessions.get_or_create(
            key, config=self.config, gallery=self.gallery
        )
        if session.is_closed:
            return {"status": "sesion_cerrada", "added": 0, "published": 0}
        added = session.add(result)
        published = 0
        if added > 0:
            early = session.early_result()
            published = self.publisher.publish(early, result_id=result_id)
        return {
            "status": "ok",
            "event_id": key.event_id,
            "camera_id": key.camera.camera_id,
            "added": added,
            "published": published,
            "clusters": len(session.clusters),
        }

    def close(self, key: SessionKey, *, result_id: int = 0) -> dict[str, Any]:
        """Cierra una sesión y publica el resultado final."""
        session = self.sessions.close(key)
        if session is None:
            return {"status": "no_existe", "published": 0}
        final = session.final_result()
        published = self.publisher.publish(final, result_id=result_id)
        self.sessions.remove(key)
        return {
            "status": "cerrada",
            "event_id": key.event_id,
            "camera_id": key.camera.camera_id,
            "published": published,
            "confirmed": sum(1 for c in (final.candidates if final else []) if c.is_confirmed),
        }

    def close_stale(self, max_age_s: float | None = None) -> list[dict[str, Any]]:
        """Cierra sesiones sin actividad reciente."""
        threshold = self.close_after_s if max_age_s is None else float(max_age_s)
        closed: list[dict[str, Any]] = []
        for key in self.sessions.keys():
            session = self.sessions.get(key)
            if session is None:
                continue
            if session.age_s() >= threshold:
                closed.append(self.close(key))
        return closed

    def stats(self) -> dict[str, Any]:
        return {
            "sessions": self.sessions.all_stats(),
            "close_after_s": self.close_after_s,
        }


def make_collector_hook(coordinator: SessionCoordinator):
    """Adapta el coordinador al hook ``on_result`` del colector."""

    def hook(result: UnitResult, result_id: int = 0) -> None:
        try:
            coordinator.ingest(result, result_id=result_id)
        except Exception:  # noqa: BLE001 — la recolección no debe romperse
            pass

    return hook
