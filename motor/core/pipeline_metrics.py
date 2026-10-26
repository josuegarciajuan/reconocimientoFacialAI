"""Medición correlacionada del pipeline de reconocimiento facial.

Este módulo registra métricas de extremo a extremo usando un ``trace_id`` que
une todas las etapas de un mismo trabajo. Los eventos se escriben en JSONL de
forma best-effort: un fallo de medición no debe tumbar el pipeline.

Archivo de salida: ``motor/logs/pipeline_metrics_<local>.jsonl``.

Etapas medibles (ver ``PipelineStage``):
- captura
- publicacion_unidad
- espera_local
- espera_pool
- transferencia
- carga_modelo
- inferencia
- aplicacion
- resultado_temprano
- resultado_final

Tipos de evento:
- ``stage``    : inicio/fin de una etapa con duración.
- ``marker``   : punto en el tiempo (p. ej., fotograma capturado).
- ``summary``  : resumen de un trabajo completo.
- ``queue``    : estado de la cola local en un instante.
- ``capacity`` : uso de la pool en un instante.
"""
from __future__ import annotations

import contextlib
import json
import os
import threading
import time
from typing import Any

from motor.core.pipeline_contracts import PipelineStage


class MetricsRecorder:
    """Registrador thread-safe de métricas del pipeline."""

    def __init__(self, project_root: str, local_id: int):
        self.project_root = project_root
        self.local_id = local_id
        self._path = os.path.join(
            project_root, "motor", "logs", f"pipeline_metrics_{local_id}.jsonl"
        )
        self._lock = threading.Lock()

    def _write(self, record: dict[str, Any]) -> None:
        """Escribe un evento en el fichero JSONL (best-effort)."""
        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            line = json.dumps(record, ensure_ascii=False, default=_json_default)
            with self._lock:
                with open(self._path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
        except Exception:  # noqa: BLE001 — la métrica nunca rompe el pipeline
            pass

    def marker(
        self,
        trace_id: str,
        stage: PipelineStage,
        *,
        unit_id: str | None = None,
        job_id: str | None = None,
        camera_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Registra un punto en el tiempo de una etapa."""
        record = _base_record(
            "marker",
            trace_id=trace_id,
            stage=stage,
            unit_id=unit_id,
            job_id=job_id,
            camera_id=camera_id,
            extra=extra,
        )
        self._write(record)

    def stage_start(
        self,
        trace_id: str,
        stage: PipelineStage,
        *,
        unit_id: str | None = None,
        job_id: str | None = None,
        camera_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> float:
        """Registra el inicio de una etapa y devuelve el timestamp."""
        now = time.time()
        record = _base_record(
            "stage",
            trace_id=trace_id,
            stage=stage,
            unit_id=unit_id,
            job_id=job_id,
            camera_id=camera_id,
            extra={"event": "start", **(extra or {})},
        )
        record["ts_start"] = now
        self._write(record)
        return now

    def stage_end(
        self,
        trace_id: str,
        stage: PipelineStage,
        ts_start: float,
        *,
        unit_id: str | None = None,
        job_id: str | None = None,
        camera_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> float:
        """Registra el fin de una etapa y devuelve la duración en segundos."""
        now = time.time()
        duration = max(0.0, now - ts_start)
        record = _base_record(
            "stage",
            trace_id=trace_id,
            stage=stage,
            unit_id=unit_id,
            job_id=job_id,
            camera_id=camera_id,
            extra={"event": "end", **(extra or {})},
        )
        record["ts_start"] = ts_start
        record["ts_end"] = now
        record["duration_s"] = round(duration, 6)
        self._write(record)
        return duration

    @contextlib.contextmanager
    def stage_timer(
        self,
        trace_id: str,
        stage: PipelineStage,
        *,
        unit_id: str | None = None,
        job_id: str | None = None,
        camera_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ):
        """Context manager que mide la duración de una etapa."""
        ts_start = self.stage_start(
            trace_id, stage, unit_id=unit_id, job_id=job_id,
            camera_id=camera_id, extra=extra,
        )
        try:
            yield ts_start
        finally:
            self.stage_end(
                trace_id, stage, ts_start, unit_id=unit_id, job_id=job_id,
                camera_id=camera_id, extra=extra,
            )

    def summary(
        self,
        trace_id: str,
        *,
        unit_id: str | None = None,
        job_id: str | None = None,
        camera_id: str | None = None,
        result_kind: str | None = None,
        stages_s: dict[str, float] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Registra el resumen de un trabajo completo."""
        record = _base_record(
            "summary",
            trace_id=trace_id,
            stage=PipelineStage.RESULTADO_FINAL,
            unit_id=unit_id,
            job_id=job_id,
            camera_id=camera_id,
            extra=extra,
        )
        record["result_kind"] = result_kind
        record["stages_s"] = stages_s or {}
        self._write(record)

    def queue_state(
        self,
        pending: int,
        sent: int,
        executing: int,
        received: int,
        applying: int,
        applied: int,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Registra el estado de la cola local en un instante."""
        record = _base_record(
            "queue",
            trace_id="",
            stage=PipelineStage.ESPERA_LOCAL,
            extra=extra,
        )
        record["counts"] = {
            "pending": pending,
            "sent": sent,
            "executing": executing,
            "received": received,
            "applying": applying,
            "applied": applied,
        }
        self._write(record)

    def capacity_state(
        self,
        pool_pending: int,
        pool_executing: int,
        pool_ready: int,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Registra el uso observado de la pool en un instante."""
        record = _base_record(
            "capacity",
            trace_id="",
            stage=PipelineStage.ESPERA_POOL,
            extra=extra,
        )
        record["counts"] = {
            "pool_pending": pool_pending,
            "pool_executing": pool_executing,
            "pool_ready": pool_ready,
        }
        self._write(record)

    def read_events(self) -> list[dict[str, Any]]:
        """Lee todos los eventos almacenados (ignora líneas corruptas)."""
        if not os.path.exists(self._path):
            return []
        out: list[dict[str, Any]] = []
        try:
            with open(self._path, encoding="utf-8") as fh:
                for ln in fh:
                    ln = ln.strip()
                    if not ln:
                        continue
                    try:
                        out.append(json.loads(ln))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            return []
        return out


def _base_record(
    tipo: str,
    *,
    trace_id: str,
    stage: PipelineStage,
    unit_id: str | None = None,
    job_id: str | None = None,
    camera_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "ts": time.time(),
        "tipo": tipo,
        "trace_id": trace_id,
        "stage": stage.value,
    }
    if unit_id:
        record["unit_id"] = unit_id
    if job_id:
        record["job_id"] = job_id
    if camera_id:
        record["camera_id"] = camera_id
    if extra:
        record["extra"] = extra
    return record


def _json_default(obj: Any) -> Any:
    """Conversión JSON para tipos no nativos."""
    if hasattr(obj, "value"):
        return obj.value
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# Instancia global por compatibilidad con el estilo PROF/embudo.
# Se inicializa bajo demanda para no depender de una configuración global.
_recorder: MetricsRecorder | None = None
_init_lock = threading.Lock()


def init_recorder(project_root: str, local_id: int) -> MetricsRecorder:
    """Inicializa el registrador global."""
    global _recorder
    with _init_lock:
        _recorder = MetricsRecorder(project_root, local_id)
    return _recorder


def get_recorder() -> MetricsRecorder | None:
    """Devuelve el registrador global si fue inicializado."""
    return _recorder
