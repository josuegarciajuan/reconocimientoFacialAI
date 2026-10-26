"""Entry point de SuperServer para el worker de inferencia reutilizable.

Uso (en el worker, con ``--ruta`` apuntando al sandbox/proyecto):

    motor/venv/bin/python motor/inference_pool.py \
        --request <spool>/<job>.json \
        --out-dir <returns>/<project>/<job>/result

Lee la petición en formato SuperServer, extrae la ``AnalysisUnit`` de los
parámetros, ejecuta el ``InferenceWorker`` y escribe ``result.json``.

En esta fase el procesador concreto de vídeo es un stub que debe ser
reemplazado/extendido en fases posteriores; la infraestructura del worker ya
está operativa.
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
    InstanceRef,
    JobRequest,
    PipelineStage,
    ResultKind,
    UnitResult,
)
from motor.inference_worker import InferenceContext, InferenceWorker  # noqa: E402


def _video_processor_stub(unit: AnalysisUnit, ctx: InferenceContext) -> UnitResult:
    """Procesador de vídeo provisional.

    En fases posteriores se reemplazará por la invocación real a
    ``procesa_video.process_video`` o a un analizador por unidades. Ahora solo
    demuestra el contrato: devuelve un resultado con métricas básicas.
    """
    ts_infer = ctx.record_stage_start(PipelineStage.INFERENCIA)

    # Simulación de trabajo: contar fotogramas del rango.
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
        metrics={
            "frames": frame_count,
            "processor": "video_faces_stub",
        },
    )


def _build_request_from_superserver(data: dict) -> JobRequest:
    """Reconstruye un ``JobRequest`` desde el JSON de SuperServer."""
    params = data.get("params", {})
    instance_ref = InstanceRef(
        instance=params["instance"],
        run_generation=params["run_generation"],
    )
    unit = AnalysisUnit.from_dict(params["unit"])
    return JobRequest(
        job_id=data["id"],
        unit=unit,
        priority=int(data.get("priority", 0)),
        submitted_at=float(data.get("submitted_at", time.time())),
        deadline_at=(float(data["deadline"]) if data.get("deadline") is not None else None),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--request", required=True, help="ruta al JSON de petición de SuperServer")
    ap.add_argument("--out-dir", required=True, help="directorio donde escribir result.json")
    ap.add_argument("--ruta", default=os.getcwd(), help="raíz del proyecto")
    args = ap.parse_args()

    try:
        with open(args.request, encoding="utf-8") as fh:
            data = json.load(fh)
        request = _build_request_from_superserver(data)
    except Exception as exc:
        err = {"error": f"petición inválida: {exc}", "job_id": None}
        os.makedirs(args.out_dir, exist_ok=True)
        with open(os.path.join(args.out_dir, "result.json"), "w", encoding="utf-8") as fh:
            json.dump(err, fh, ensure_ascii=False)
        print(f"[inference-pool] ERROR petición inválida: {exc}", flush=True)
        return 1

    worker = InferenceWorker(project_root=args.ruta)
    worker.register_processor("video_faces", _video_processor_stub)
    worker.register_processor("detect", _video_processor_stub)

    try:
        result = worker.process_request(request)
    except Exception as exc:
        err = {"error": str(exc), "job_id": data.get("id")}
        os.makedirs(args.out_dir, exist_ok=True)
        with open(os.path.join(args.out_dir, "result.json"), "w", encoding="utf-8") as fh:
            json.dump(err, fh, ensure_ascii=False)
        print(f"[inference-pool] ERROR {exc}", flush=True)
        return 1

    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "result.json"), "w", encoding="utf-8") as fh:
        json.dump(result.to_dict(), fh, ensure_ascii=False, indent=2)

    print(f"[inference-pool] {request.job_id} → {args.out_dir}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
