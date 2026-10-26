"""Contratos del pipeline de reconocimiento facial.

Este módulo define los identificadores, estados y estructuras de datos que usan
todos los componentes del nuevo pipeline. Todo contenido debe ser
JSON-serializable para poder viajar entre procesos, nodos y la base de datos de
trabajos local.

Reglas del contrato:
- Los identificadores son explícitos; los nombres de archivo no son la fuente
  primaria de la información temporal.
- Cada ejecución desde cero tiene una ``run_generation`` que invalida trabajos
  y resultados de generaciones anteriores.
- Un trabajo incluye la configuración efectiva que lo produjo, o una referencia
  versionada verificable.
- Las métricas llevan ``trace_id`` para poder correlacionar etapas de extremo a
  extremo.
"""
from __future__ import annotations

import dataclasses
import enum
import time
import uuid
from typing import Any


class JobStatus(str, enum.Enum):
    """Estados de un trabajo en el registro duradero."""

    PENDIENTE = "pendiente"
    ENVIADO = "enviado"
    EJECUTANDO = "ejecutando"
    RESULTADO_RECIBIDO = "resultado_recibido"
    APLICANDO = "aplicando"
    APLICADO = "aplicado"
    REINTENTO = "reintento"
    REQUIERE_INTERVENCION = "requiere_intervencion"
    CANCELADO = "cancelado"


class ResultKind(str, enum.Enum):
    """Tipo de resultado que puede publicar el pipeline."""

    TEMPRANO = "temprano"
    FINAL = "final"


class PipelineStage(str, enum.Enum):
    """Etapas medibles del pipeline.

    Se usan para etiquetar métricas y para saber qué partes están fallando o
    saturándose.
    """

    CAPTURA = "captura"
    PUBLICACION_UNIDAD = "publicacion_unidad"
    ESPERA_LOCAL = "espera_local"
    ESPERA_POOL = "espera_pool"
    TRANSFERENCIA = "transferencia"
    CARGA_MODELO = "carga_modelo"
    INFERENCIA = "inferencia"
    APLICACION = "aplicacion"
    RESULTADO_TEMPRANO = "resultado_temprano"
    RESULTADO_FINAL = "resultado_final"


@dataclasses.dataclass(frozen=True, slots=True)
class InstanceRef:
    """Referencia completa a una ejecución de una instancia."""

    instance: str
    run_generation: str

    def to_dict(self) -> dict[str, Any]:
        return {"instance": self.instance, "run_generation": self.run_generation}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "InstanceRef":
        return cls(instance=str(d["instance"]), run_generation=str(d["run_generation"]))


@dataclasses.dataclass(frozen=True, slots=True)
class CameraRef:
    """Referencia a una cámara dentro de una instancia."""

    instance: InstanceRef
    local_id: int
    camera_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "instance": self.instance.to_dict(),
            "local_id": self.local_id,
            "camera_id": self.camera_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CameraRef":
        return cls(
            instance=InstanceRef.from_dict(d["instance"]),
            local_id=int(d["local_id"]),
            camera_id=str(d["camera_id"]),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class MotionEventRef:
    """Evento de movimiento detectado por una cámara."""

    camera: CameraRef
    event_id: str
    started_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "camera": self.camera.to_dict(),
            "event_id": self.event_id,
            "started_at": self.started_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "MotionEventRef":
        return cls(
            camera=CameraRef.from_dict(d["camera"]),
            event_id=str(d["event_id"]),
            started_at=float(d["started_at"]),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class FrameRange:
    """Rango de fotogramas dentro de un evento de movimiento."""

    first_frame_idx: int
    last_frame_idx: int
    first_frame_ts: float
    last_frame_ts: float

    def __post_init__(self) -> None:
        if self.last_frame_idx < self.first_frame_idx:
            object.__setattr__(
                self, "last_frame_idx", self.first_frame_idx
            )
        if self.last_frame_ts < self.first_frame_ts:
            object.__setattr__(
                self, "last_frame_ts", self.first_frame_ts
            )

    @property
    def frame_count(self) -> int:
        return max(0, self.last_frame_idx - self.first_frame_idx + 1)

    @property
    def duration_s(self) -> float:
        return max(0.0, self.last_frame_ts - self.first_frame_ts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "first_frame_idx": self.first_frame_idx,
            "last_frame_idx": self.last_frame_idx,
            "first_frame_ts": self.first_frame_ts,
            "last_frame_ts": self.last_frame_ts,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FrameRange":
        return cls(
            first_frame_idx=int(d["first_frame_idx"]),
            last_frame_idx=int(d["last_frame_idx"]),
            first_frame_ts=float(d["first_frame_ts"]),
            last_frame_ts=float(d["last_frame_ts"]),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class ConfigRef:
    """Referencia a la configuración efectiva de un análisis.

    Incluye un hash o versión de los parámetros que afectan al resultado, para
    poder invalidar cachés y asegurar reproducibilidad.
    """

    version: str
    params_hash: str
    params: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "params_hash": self.params_hash,
            "params": self.params,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ConfigRef":
        return cls(
            version=str(d["version"]),
            params_hash=str(d["params_hash"]),
            params=d.get("params"),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class AnalysisUnit:
    """Unidad cerrada de análisis enviada a la pool.

    Puede representar un segmento de un evento de movimiento, un vídeo completo
    o cualquier otra granularidad que permita el análisis progresivo.
    """

    unit_id: str
    event: MotionEventRef
    frame_range: FrameRange
    config: ConfigRef
    source_paths: dict[str, str]
    requested_stages: list[str]
    trace_id: str
    created_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "event": self.event.to_dict(),
            "frame_range": self.frame_range.to_dict(),
            "config": self.config.to_dict(),
            "source_paths": self.source_paths,
            "requested_stages": self.requested_stages,
            "trace_id": self.trace_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AnalysisUnit":
        return cls(
            unit_id=str(d["unit_id"]),
            event=MotionEventRef.from_dict(d["event"]),
            frame_range=FrameRange.from_dict(d["frame_range"]),
            config=ConfigRef.from_dict(d["config"]),
            source_paths=dict(d.get("source_paths") or {}),
            requested_stages=list(d.get("requested_stages") or []),
            trace_id=str(d["trace_id"]),
            created_at=float(d["created_at"]),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class BoundingBox:
    """Caja delimitadora en píxeles, sistema (x1, y1, x2, y2)."""

    x1: float
    y1: float
    x2: float
    y2: float

    def to_dict(self) -> dict[str, Any]:
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BoundingBox":
        return cls(
            x1=float(d["x1"]),
            y1=float(d["y1"]),
            x2=float(d["x2"]),
            y2=float(d["y2"]),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class FaceDetection:
    """Detección facial con metadatos de calidad."""

    detection_id: str
    frame_idx: int
    frame_ts: float
    bbox: BoundingBox
    keypoints: dict[str, tuple[float, float]]
    confidence: float
    embedding: list[float] | None
    quality_score: float
    sharpness: float | None
    is_profile: bool | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "detection_id": self.detection_id,
            "frame_idx": self.frame_idx,
            "frame_ts": self.frame_ts,
            "bbox": self.bbox.to_dict(),
            "keypoints": self.keypoints,
            "confidence": self.confidence,
            "embedding": self.embedding,
            "quality_score": self.quality_score,
            "sharpness": self.sharpness,
            "is_profile": self.is_profile,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FaceDetection":
        return cls(
            detection_id=str(d["detection_id"]),
            frame_idx=int(d["frame_idx"]),
            frame_ts=float(d["frame_ts"]),
            bbox=BoundingBox.from_dict(d["bbox"]),
            keypoints={
                str(k): tuple(v) for k, v in (d.get("keypoints") or {}).items()
            },
            confidence=float(d["confidence"]),
            embedding=list(d["embedding"]) if d.get("embedding") is not None else None,
            quality_score=float(d["quality_score"]),
            sharpness=float(d["sharpness"]) if d.get("sharpness") is not None else None,
            is_profile=d.get("is_profile") if d.get("is_profile") is not None else None,
        )


@dataclasses.dataclass(frozen=True, slots=True)
class BodyDetection:
    """Detección de cuerpo/torso asociada a una cara o independiente."""

    detection_id: str
    frame_idx: int
    frame_ts: float
    bbox: BoundingBox
    confidence: float
    face_detection_id: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "detection_id": self.detection_id,
            "frame_idx": self.frame_idx,
            "frame_ts": self.frame_ts,
            "bbox": self.bbox.to_dict(),
            "confidence": self.confidence,
            "face_detection_id": self.face_detection_id,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BodyDetection":
        return cls(
            detection_id=str(d["detection_id"]),
            frame_idx=int(d["frame_idx"]),
            frame_ts=float(d["frame_ts"]),
            bbox=BoundingBox.from_dict(d["bbox"]),
            confidence=float(d["confidence"]),
            face_detection_id=d.get("face_detection_id"),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class RecognitionCandidate:
    """Candidato de identificación para una cara o grupo."""

    candidate_id: str
    person_id: int | None
    person_label: str | None
    score: float
    method: str
    is_confirmed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "person_id": self.person_id,
            "person_label": self.person_label,
            "score": self.score,
            "method": self.method,
            "is_confirmed": self.is_confirmed,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RecognitionCandidate":
        return cls(
            candidate_id=str(d["candidate_id"]),
            person_id=int(d["person_id"]) if d.get("person_id") is not None else None,
            person_label=d.get("person_label"),
            score=float(d["score"]),
            method=str(d["method"]),
            is_confirmed=bool(d["is_confirmed"]),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class UnitResult:
    """Resultado del análisis de una unidad."""

    unit_id: str
    instance: InstanceRef
    trace_id: str
    kind: ResultKind
    generated_at: float
    faces: list[FaceDetection]
    bodies: list[BodyDetection]
    candidates: list[RecognitionCandidate]
    artifacts: dict[str, str]
    metrics: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "instance": self.instance.to_dict(),
            "trace_id": self.trace_id,
            "kind": self.kind.value,
            "generated_at": self.generated_at,
            "faces": [f.to_dict() for f in self.faces],
            "bodies": [b.to_dict() for b in self.bodies],
            "candidates": [c.to_dict() for c in self.candidates],
            "artifacts": self.artifacts,
            "metrics": self.metrics,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "UnitResult":
        return cls(
            unit_id=str(d["unit_id"]),
            instance=InstanceRef.from_dict(d["instance"]),
            trace_id=str(d["trace_id"]),
            kind=ResultKind(d["kind"]),
            generated_at=float(d["generated_at"]),
            faces=[FaceDetection.from_dict(f) for f in d.get("faces") or []],
            bodies=[BodyDetection.from_dict(b) for b in d.get("bodies") or []],
            candidates=[RecognitionCandidate.from_dict(c) for c in d.get("candidates") or []],
            artifacts=dict(d.get("artifacts") or {}),
            metrics=dict(d.get("metrics") or {}),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class JobRequest:
    """Petición enviada a la pool para analizar una unidad."""

    job_id: str
    unit: AnalysisUnit
    priority: int
    submitted_at: float
    deadline_at: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "unit": self.unit.to_dict(),
            "priority": self.priority,
            "submitted_at": self.submitted_at,
            "deadline_at": self.deadline_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "JobRequest":
        return cls(
            job_id=str(d["job_id"]),
            unit=AnalysisUnit.from_dict(d["unit"]),
            priority=int(d["priority"]),
            submitted_at=float(d["submitted_at"]),
            deadline_at=float(d["deadline_at"]) if d.get("deadline_at") is not None else None,
        )


@dataclasses.dataclass(frozen=True, slots=True)
class JobResult:
    """Envoltura de un resultado recibido de la pool, con su estado de aplicación."""

    job_id: str
    unit_result: UnitResult
    received_at: float
    applied_at: float | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "unit_result": self.unit_result.to_dict(),
            "received_at": self.received_at,
            "applied_at": self.applied_at,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "JobResult":
        return cls(
            job_id=str(d["job_id"]),
            unit_result=UnitResult.from_dict(d["unit_result"]),
            received_at=float(d["received_at"]),
            applied_at=float(d["applied_at"]) if d.get("applied_at") is not None else None,
            error=d.get("error"),
        )


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def new_trace_id() -> str:
    """Identificador único para correlacionar métricas de un mismo trabajo."""
    return uuid.uuid4().hex


def new_run_generation() -> str:
    """Generación de ejecución: timestamp + UUID corto.

    Se usa tras un reset o rearranque controlado desde cero.
    """
    return f"{int(time.time())}-{uuid.uuid4().hex[:8]}"


def encode_json(obj: Any) -> Any:
    """Serialización auxiliar para valores no nativos de JSON."""
    if isinstance(obj, enum.Enum):
        return obj.value
    if dataclasses.is_dataclass(obj):
        return obj.to_dict()
    if isinstance(obj, (list, tuple)):
        return [encode_json(v) for v in obj]
    if isinstance(obj, dict):
        return {str(k): encode_json(v) for k, v in obj.items()}
    return obj
