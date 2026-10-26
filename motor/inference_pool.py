"""Entry point de SuperServer para el worker de inferencia reutilizable.

Uso (en el worker, con ``--ruta`` apuntando al sandbox/proyecto):

    motor/venv/bin/python motor/inference_pool.py \
        --request <spool>/<job>.json \
        --out-dir <returns>/<project>/<job>/result

Acepta dos formatos de petición:

1. ``JobRequest`` directo (``{"job_id":..., "unit": {...}}``).
2. Petición de spool (``{"id":..., "params": {"unit": {...}}}``).

Escribe ``result.json`` con el formato ``JobResult`` que consume el colector.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.pipeline_contracts import (  # noqa: E402
    AnalysisUnit,
    JobRequest,
    JobResult,
    PipelineStage,
    ResultKind,
    UnitResult,
)
from motor.core.pipeline_metrics import MetricsRecorder  # noqa: E402
from motor.inference_worker import InferenceContext, InferenceWorker  # noqa: E402


def _video_processor_stub(unit: AnalysisUnit, ctx: InferenceContext) -> UnitResult:
    """Procesador de vídeo provisional para pruebas de plumbing."""
    ts_infer = ctx.record_stage_start(PipelineStage.INFERENCIA)
    frame_count = unit.frame_range.frame_count
    ctx.record_stage_end(PipelineStage.INFERENCIA, ts_infer)

    return UnitResult(
        unit_id=unit.unit_id,
        instance=unit.event.camera.instance,
        trace_id=unit.trace_id,
        kind=ResultKind.FINAL,
        generated_at=time.time(),
        faces=[],
        bodies=[],
        candidates=[],
        artifacts={},
        event_id=unit.event.event_id,
        local_id=unit.event.camera.local_id,
        camera_id=unit.event.camera.camera_id,
        metrics={
            "frames": frame_count,
            "processor": "video_faces_stub",
        },
    )


def _build_request_from_superserver(data: dict) -> JobRequest:
    """Reconstruye un ``JobRequest`` desde cualquiera de los dos formatos."""
    # Formato 1: JobRequest directo (lo usa el adaptador del worker).
    if "job_id" in data and "unit" in data:
        return JobRequest.from_dict(data)
    # Formato 2: petición de spool.
    params = data.get("params", {})
    unit = AnalysisUnit.from_dict(params["unit"])
    return JobRequest(
        job_id=data["id"],
        unit=unit,
        priority=int(data.get("priority", 0)),
        submitted_at=float(data.get("submitted_at", time.time())),
        deadline_at=(float(data["deadline"]) if data.get("deadline") is not None else None),
    )


def _write_error(out_dir: str, message: str, job_id: str | None) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "result.json"), "w", encoding="utf-8") as fh:
        json.dump({"error": message, "job_id": job_id}, fh, ensure_ascii=False)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", required=True, help="ruta al JSON de petición")
    ap.add_argument("--out-dir", required=True, help="directorio donde escribir result.json")
    ap.add_argument("--ruta", default=os.getcwd(), help="raíz del proyecto")
    ap.add_argument(
        "--processor",
        choices=["real", "stub"],
        default="real",
        help="procesador de vídeo (real por defecto; stub para pruebas)",
    )
    args = ap.parse_args(argv)

    try:
        with open(args.request, encoding="utf-8") as fh:
            data = json.load(fh)
        request = _build_request_from_superserver(data)
    except Exception as exc:
        _write_error(args.out_dir, f"petición inválida: {exc}", None)
        print(f"[inference-pool] ERROR petición inválida: {exc}", flush=True)
        return 1

    local_id = int(request.unit.event.camera.local_id or 1)
    metrics = MetricsRecorder(args.ruta, local_id)
    worker = InferenceWorker(project_root=args.ruta, metrics=metrics)
    if args.processor == "real":
        from motor.processors.video_processor import process_unit

        worker.register_processor("video_faces", process_unit)
        worker.register_processor("detect", process_unit)
    else:
        worker.register_processor("video_faces", _video_processor_stub)
        worker.register_processor("detect", _video_processor_stub)

    try:
        result = worker.process_request(request)
    except Exception as exc:
        _write_error(args.out_dir, str(exc), request.job_id)
        print(f"[inference-pool] ERROR {exc}", flush=True)
        return 1

    job_result = JobResult(
        job_id=request.job_id,
        unit_result=result,
        received_at=time.time(),
    )
    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(job_result.to_dict(), fh, ensure_ascii=False, indent=2)

    print(f"[inference-pool] {request.job_id} → {args.out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
