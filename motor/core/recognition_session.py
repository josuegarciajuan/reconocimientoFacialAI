"""Sesión de reconocimiento incremental.

Agrupa los resultados parciales (unidades) de un evento de movimiento para
producir un resultado temprano y, eventualmente, un resultado final.

La sesión:
- Acepta unidades fuera de orden.
- Mantiene una ventana de evidencia recibida.
- No confirma una identidad hasta que las reglas temporales/calidad lo permitan.
- Separa explícitamente entre ``ResultKind.TEMPRANO`` y ``ResultKind.FINAL``.

En esta fase se entrega el esqueleto funcional; la lógica de agrupación y
confirmación se refinará en la Fase 6.
"""
from __future__ import annotations

import dataclasses
import time
from typing import Any

from motor.core.pipeline_contracts import (
    CameraRef,
    FaceDetection,
    RecognitionCandidate,
    ResultKind,
    UnitResult,
)


@dataclasses.dataclass(frozen=True, slots=True)
class SessionKey:
    """Clave de una sesión de reconocimiento."""

    camera: CameraRef
    event_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera": self.camera.to_dict(),
            "event_id": self.event_id,
        }


class RecognitionSession:
    """Sesión incremental de reconocimiento para un evento."""

    def __init__(self, key: SessionKey):
        self.key = key
        self.created_at = time.time()
        self.updated_at = self.created_at
        self._results: list[UnitResult] = []
        self._closed = False

    @property
    def is_closed(self) -> bool:
        return self._closed

    def add(self, result: UnitResult) -> None:
        """Añade un resultado parcial a la sesión."""
        if self._closed:
            raise RuntimeError("No se puede añadir resultados a una sesión cerrada")
        self._results.append(result)
        self.updated_at = time.time()

    def close(self) -> None:
        """Cierra la sesión: no se aceptarán más unidades."""
        self._closed = True

    def all_faces(self) -> list[FaceDetection]:
        """Todas las detecciones faciales recibidas en orden temporal."""
        faces: list[FaceDetection] = []
        for result in sorted(self._results, key=lambda r: r.generated_at):
            faces.extend(result.faces)
        return faces

    def early_result(self) -> UnitResult | None:
        """Resultado temprano con la evidencia acumulada hasta ahora.

        Devuelve None si aún no hay resultados.
        """
        if not self._results:
            return None
        faces = self.all_faces()
        last = max(self._results, key=lambda r: r.generated_at)
        return UnitResult(
            unit_id=f"session:{self.key.event_id}:early",
            instance=last.instance,
            trace_id=last.trace_id,
            kind=ResultKind.TEMPRANO,
            generated_at=time.time(),
            faces=faces,
            bodies=[],
            candidates=self._build_candidates(faces),
            artifacts={},
            metrics={"units": len(self._results), "faces": len(faces)},
        )

    def final_result(self) -> UnitResult | None:
        """Resultado final tras cerrar la sesión.

        Devuelve None si la sesión no está cerrada o no tiene resultados.
        """
        if not self._closed or not self._results:
            return None
        faces = self.all_faces()
        last = max(self._results, key=lambda r: r.generated_at)
        return UnitResult(
            unit_id=f"session:{self.key.event_id}:final",
            instance=last.instance,
            trace_id=last.trace_id,
            kind=ResultKind.FINAL,
            generated_at=time.time(),
            faces=faces,
            bodies=[],
            candidates=self._build_candidates(faces),
            artifacts={},
            metrics={"units": len(self._results), "faces": len(faces)},
        )

    def _build_candidates(self, faces: list[FaceDetection]) -> list[RecognitionCandidate]:
        """Construye candidatos provisionales a partir de las caras.

        Versión inicial: cada cara es un candidato no confirmado. En la Fase 6 se
        agruparán por identidad.
        """
        candidates: list[RecognitionCandidate] = []
        for i, face in enumerate(faces):
            candidates.append(
                RecognitionCandidate(
                    candidate_id=f"cand-{i}",
                    person_id=None,
                    person_label=None,
                    score=face.confidence,
                    method="direct",
                    is_confirmed=False,
                )
            )
        return candidates

    def stats(self) -> dict[str, Any]:
        return {
            "event_id": self.key.event_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "closed": self._closed,
            "units": len(self._results),
            "faces": sum(len(r.faces) for r in self._results),
        }


class SessionStore:
    """Almacén de sesiones de reconocimiento por evento."""

    def __init__(self):
        self._sessions: dict[SessionKey, RecognitionSession] = {}
        self._lock_state: dict[SessionKey, bool] = {}

    def get_or_create(self, key: SessionKey) -> RecognitionSession:
        if key not in self._sessions:
            self._sessions[key] = RecognitionSession(key)
        return self._sessions[key]

    def get(self, key: SessionKey) -> RecognitionSession | None:
        return self._sessions.get(key)

    def close(self, key: SessionKey) -> RecognitionSession | None:
        session = self._sessions.get(key)
        if session:
            session.close()
        return session

    def all_stats(self) -> dict[str, dict[str, Any]]:
        return {
            f"{k.camera.camera_id}:{k.event_id}": v.stats()
            for k, v in self._sessions.items()
        }
