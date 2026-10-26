"""Ejecutor de inferencia reutilizable para la pool.

Este módculo proporciona una capa que permite a un worker de SuperServer:

- Recibir peticiones en formato nuevo (``AnalysisUnit`` / ``JobRequest``).
- Cargar modelos bajo demanda y reutilizarlos entre trabajos compatibles.
- Liberar modelos bajo presión de memoria.
- Procesar la unidad y devolver un ``UnitResult``.

La carga real de modelos se delega en ``motor.core.model``; este módculo gestiona
el ciclo de vida y la contabilidad del worker. Los procesadores concretos
(análisis de vídeo, cuerpo, etc.) son inyectables para facilitar las pruebas.
"""
from __future__ import annotations

import functools
import os
import threading
import time
import tracemalloc
from typing import Any, Callable, Protocol

from motor.core.pipeline_contracts import (
    AnalysisUnit,
    BoundingBox,
    FaceDetection,
    JobRequest,
    PipelineStage,
    ResultKind,
    UnitResult,
)
from motor.core.pipeline_metrics import MetricsRecorder


class Processor(Protocol):
    """Interfaz de un procesador de unidades."""

    def __call__(self, unit: AnalysisUnit, ctx: "InferenceContext") -> UnitResult:
        ...


class InferenceContext:
    """Contexto disponible para los procesadores dentro de un worker."""

    def __init__(self, worker: "InferenceWorker", unit: AnalysisUnit):
        self.worker = worker
        self.unit = unit
        self.metrics = worker.metrics
        self.trace_id = unit.trace_id

    def record_stage_start(self, stage: PipelineStage) -> float:
        if self.metrics:
            return self.metrics.stage_start(
                self.trace_id, stage, unit_id=self.unit.unit_id
            )
        return time.time()

    def record_stage_end(self, stage: PipelineStage, ts_start: float) -> None:
        if self.metrics:
            self.metrics.stage_end(
                self.trace_id, stage, ts_start, unit_id=self.unit.unit_id
            )


class ModelCache:
    """Caché de modelos con contabilidad y eviction bajo presión.

    Actualmente delega en ``motor.core.model.get_app`` (caché global por
    det_size). Esta clase añade seguimiento de uso y un mecanismo explícito de
    liberación para cuando el worker necesite recuperar memoria.
    """

    def __init__(
        self,
        *,
        loader: Callable[[tuple[int, int]], Any] | None = None,
        max_models: int = 3,
        memory_threshold_mb: float | None = None,
    ):
        self._loader = loader
        self.max_models = max_models
        self.memory_threshold_mb = memory_threshold_mb
        self._lock = threading.Lock()
        self._models: dict[tuple[int, int], Any] = {}
        self._usage: dict[tuple[int, int], float] = {}
        self._loads = 0
        self._hits = 0

    def _default_loader(self, det_size: tuple[int, int]) -> Any:
        from motor.core import model

        return model.get_app(det_size)

    def get(self, det_size: tuple[int, int]) -> Any:
        """Obtiene un modelo, cargándolo si es necesario."""
        with self._lock:
            model = self._models.get(det_size)
            if model is not None:
                self._usage[det_size] = time.time()
                self._hits += 1
                return model

        loader = self._loader or self._default_loader
        try:
            model = loader(det_size)
        except Exception as exc:
            raise InferenceWorkerError(f"No se pudo cargar el modelo {det_size}: {exc}") from exc

        with self._lock:
            self._models[det_size] = model
            self._usage[det_size] = time.time()
            self._loads += 1
        return model

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "cached_sizes": list(self._usage.keys()),
                "loads": self._loads,
                "hits": self._hits,
            }

    def should_evict(self) -> bool:
        """Heurística simple de presión de memoria."""
        if self.memory_threshold_mb is None:
            return False
        try:
            import psutil

            mem = psutil.virtual_memory()
            return mem.percent >= 85.0
        except Exception:  # noqa: BLE001
            return False

    def evict_lru(self) -> list[tuple[int, int]]:
        """Libera el modelo menos recientemente usado."""
        with self._lock:
            if not self._usage:
                return []
            lru = min(self._usage, key=self._usage.get)
            del self._usage[lru]
            self._models.pop(lru, None)
        # La liberación real depende del loader. Si es el loader por defecto,
        # InsightFace mantiene sus propias referencias globales; esta llamada
        # es principalmente para loaders personalizados.
        if self._loader is not None:
            try:
                # Notificación al loader externo si expone evict.
                evict_fn = getattr(self._loader, "evict", None)
                if callable(evict_fn):
                    evict_fn(lru)
            except Exception:  # noqa: BLE001
                pass
        return [lru]


class InferenceWorkerError(Exception):
    """Error del worker de inferencia."""


class InferenceWorker:
    """Worker que procesa unidades reutilizando modelos."""

    def __init__(
        self,
        *,
        project_root: str,
        processors: dict[str, Processor] | None = None,
        model_cache: ModelCache | None = None,
        metrics: MetricsRecorder | None = None,
    ):
        self.project_root = project_root
        self.processors = processors or {}
        self.model_cache = model_cache or ModelCache()
        self.metrics = metrics
        self._jobs_processed = 0
        self._lock = threading.Lock()

    def register_processor(self, stage: str, processor: Processor) -> None:
        self.processors[stage] = processor

    def process_request(self, request: JobRequest) -> UnitResult:
        """Procesa una petición completa y devuelve el resultado."""
        unit = request.unit
        trace_id = unit.trace_id

        if self.metrics:
            self.metrics.marker(trace_id, PipelineStage.CARGA_MODELO, unit_id=unit.unit_id)

        ts_infer = time.time()
        if self.metrics:
            self.metrics.stage_start(trace_id, PipelineStage.INFERENCIA, unit_id=unit.unit_id)

        try:
            result = self._process_unit(unit)
        except Exception as exc:
            if self.metrics:
                self.metrics.stage_end(trace_id, PipelineStage.INFERENCIA, ts_infer, unit_id=unit.unit_id)
            raise InferenceWorkerError(f"Error procesando {unit.unit_id}: {exc}") from exc

        if self.metrics:
            self.metrics.stage_end(trace_id, PipelineStage.INFERENCIA, ts_infer, unit_id=unit.unit_id)

        with self._lock:
            self._jobs_processed += 1

        if self.model_cache.should_evict():
            self.model_cache.evict_lru()

        return result

    def _process_unit(self, unit: AnalysisUnit) -> UnitResult:
        """Selecciona el procesador adecuado y ejecuta la unidad."""
        ctx = InferenceContext(self, unit)

        # Por defecto usamos el primer stage solicitado; si no hay, usamos
        # "video_faces" como fallback compatible con el pipeline actual.
        stage = unit.requested_stages[0] if unit.requested_stages else "video_faces"
        processor = self.processors.get(stage)
        if processor is None:
            raise InferenceWorkerError(f"No hay procesador registrado para '{stage}'")

        return processor(unit, ctx)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "jobs_processed": self._jobs_processed,
                "model_cache": self.model_cache.stats(),
                "registered_processors": list(self.processors.keys()),
            }


def analyze_frame(
    img,
    det_size: tuple[int, int] = (640, 640),
    min_score: float = 0.5,
) -> list[FaceDetection]:
    """Envoltura sobre ``motor.core.model.analyze`` que devuelve contratos."""
    from motor.core import model

    faces = model.analyze(img, det_size=det_size, min_score=min_score)
    out: list[FaceDetection] = []
    for i, f in enumerate(faces):
        out.append(
            FaceDetection(
                detection_id=f"det-{i}",
                frame_idx=-1,
                frame_ts=0.0,
                bbox=BoundingBox(*f.bbox),
                keypoints={},
                confidence=f.det_score,
                embedding=f.embedding.tolist(),
                quality_score=f.det_score,
                sharpness=None,
                is_profile=abs(f.yaw) > 30,
            )
        )
    return out


# ---------------------------------------------------------------------------
# Utilidades de contabilidad
# ---------------------------------------------------------------------------


def current_memory_mb() -> float:
    """Memoria residente aproximada del proceso en MB."""
    try:
        import psutil

        proc = psutil.Process(os.getpid())
        return proc.memory_info().rss / (1024 * 1024)
    except Exception:  # noqa: BLE001
        return 0.0


def snapshot_memory() -> dict[str, float]:
    """Snapshot de memoria usando tracemalloc si está activo."""
    if not tracemalloc.is_tracing():
        return {"rss_mb": current_memory_mb()}
    current, peak = tracemalloc.get_traced_memory()
    return {
        "rss_mb": current_memory_mb(),
        "tracemalloc_current_mb": current / (1024 * 1024),
        "tracemalloc_peak_mb": peak / (1024 * 1024),
    }
