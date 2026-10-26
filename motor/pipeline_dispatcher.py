"""Despachador asíncrono de trabajos hacia SuperServer.

Lee trabajos en estado ``pendiente`` del ``JobStore`` y los escribe en el spool
de SuperServer (``/var/lib/taildeck/spool``). No bloquea esperando el resultado;
eso lo hace el ``pipeline_collector``.

El despachador respeta una ventana máxima de trabajos enviados para no
inundar la pool. Cuando la ventana está llena, los trabajos permanecen en el
``JobStore`` hasta que haya capacidad.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from motor.core.job_store import JobStatus
from motor.core.pipeline_contracts import AnalysisUnit, JobRequest
from motor.core.instance import project_id


SPOOL_DIR = "/var/lib/taildeck/spool"


class DispatcherError(Exception):
    """Error del despachador."""


class PipelineDispatcher:
    """Despacha trabajos del JobStore al spool de SuperServer."""

    def __init__(
        self,
        job_store,
        *,
        project_root: str,
        spool_dir: str = SPOOL_DIR,
        max_sent: int = 20,
        max_concurrent_by_stage: dict[str, int] | None = None,
    ):
        self.store = job_store
        self.project_root = project_root
        self.spool_dir = spool_dir
        self.max_sent = max_sent
        self.max_concurrent_by_stage = max_concurrent_by_stage or {}
        self.project_id = project_id(project_root)
        # Caché TTL de líneas por cámara: evita dos subprocess php por despacho.
        self._lines_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        self._lines_ttl = 60.0

    def _to_superserver_request(self, job: JobRequest) -> dict[str, Any]:
        """Convierte un ``JobRequest`` al formato esperado por SuperServer.

        Incluye el ``trace_id`` y los identificadores de generación para que el
        collector pueda validar el resultado.
        """
        unit = job.unit
        event = unit.event
        source_path = (
            unit.source_paths.get("video")
            or unit.source_paths.get("segment")
            or ""
        )
        # La casa consulta las líneas (el worker no debe hablar con la BD) y las
        # adjunta a la unidad. Si la consulta falla, se despacha sin cruces.
        lineas = self._camera_lines(event.camera.camera_id)
        unit_dict = unit.to_dict()
        if lineas:
            cfg = unit_dict.get("config") or {}
            params = dict(cfg.get("params") or {})
            params.setdefault("lineas", lineas)
            cfg["params"] = params
            unit_dict["config"] = cfg
        return {
            "id": job.job_id,
            "project": self.project_id,
            "process": self._process_name(unit),
            "params": {
                # `unit` es lo que reconstruye el worker. Los campos planos se
                # mantienen para observabilidad y compatibilidad.
                "unit": unit_dict,
                "instance": event.camera.instance.instance,
                "run_generation": event.camera.instance.run_generation,
                "local_id": event.camera.local_id,
                "camera_id": event.camera.camera_id,
                "event_id": event.event_id,
                "unit_id": unit.unit_id,
                "frame_range": unit.frame_range.to_dict(),
                "source_paths": unit.source_paths,
                "config": unit_dict.get("config"),
                "requested_stages": unit.requested_stages,
                "trace_id": unit.trace_id,
            },
            # `spec` es el contrato que consume el control plane de SuperServer
            # (definición del proceso). Se incluye ya para que la integración
            # final no requiera cambiar el payload.
            "spec": {
                "kind": "video_segment",
                "local": str(event.camera.local_id),
                "cam": event.camera.camera_id,
                "fichero": os.path.basename(source_path),
                "home_path": source_path if os.path.isabs(source_path) else "",
                "home": event.camera.instance.instance,
                "lineas": lineas,
                "unit_id": unit.unit_id,
                "frame_from": unit.frame_range.first_frame_idx,
                "frame_to": unit.frame_range.last_frame_idx + 1,
                "run_generation": event.camera.instance.run_generation,
                "trace_id": unit.trace_id,
            },
            "externalId": (
                f"{event.camera.instance.instance}:"
                f"{event.camera.local_id}/{event.camera.camera_id}/"
                f"{event.event_id}/{unit.unit_id}"
            ),
            "priority": job.priority,
            "deadline": job.deadline_at,
        }

    def _camera_lines(self, camera_id: str) -> list[dict[str, Any]]:
        """Líneas de la cámara consultadas en la casa (best-effort, con TTL)."""
        now = time.time()
        cached = self._lines_cache.get(camera_id)
        if cached is not None and (now - cached[0]) < self._lines_ttl:
            return cached[1]
        try:
            from motor.procesa_video import cargar_lineas

            lineas = [
                {
                    "id": ln.line_id,
                    "x1": ln.x1,
                    "y1": ln.y1,
                    "x2": ln.x2,
                    "y2": ln.y2,
                }
                for ln in cargar_lineas(camera_id)
            ]
        except Exception:  # noqa: BLE001 — sin líneas, el resto del pipeline sigue
            lineas = []
        self._lines_cache[camera_id] = (now, lineas)
        return lineas

    def _process_name(self, unit: AnalysisUnit) -> str:  # noqa: ARG002
        """Nombre del proceso SuperServer según el tipo de unidad."""
        # En la fase actual solo existe el pipeline facial. Se deja extensible
        # para cuando haya procesos separados (cuerpo, pose, etc.).
        return "video_faces"

    def _write_spool(self, req: dict[str, Any]) -> str:
        os.makedirs(self.spool_dir, exist_ok=True)
        dst = os.path.join(self.spool_dir, f"{req['id']}.json")
        tmp = dst + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(req, fh, ensure_ascii=False, default=str)
        os.replace(tmp, dst)
        return dst

    def _count_sent(self, run_generation: str) -> int:
        return len(self.store.list_jobs(status=JobStatus.ENVIADO, run_generation=run_generation))

    def dispatch_one(self, run_generation: str | None = None) -> str | None:
        """Despacha el siguiente trabajo pendiente si cabe en la ventana.

        Devuelve el ``job_id`` enviado o None si no hay nada disponible.
        """
        gen = run_generation or self.store.active_generation()
        if not gen:
            return None

        if self._count_sent(gen) >= self.max_sent:
            return None

        pending = self.store.list_jobs(
            status=JobStatus.PENDIENTE,
            run_generation=gen,
            limit=1,
        )
        if not pending:
            return None

        row = pending[0]
        request = JobRequest.from_dict(json.loads(row["job_json"]))
        job_id = request.job_id

        req_payload = self._to_superserver_request(request)
        self._write_spool(req_payload)

        self.store.set_job_status(job_id, gen, JobStatus.ENVIADO)
        self.store.record_attempt(
            job_id=job_id,
            run_generation=gen,
            worker_id=None,
            status=JobStatus.ENVIADO.value,
            started_at=time.time(),
        )
        return job_id

    def dispatch_all(self, run_generation: str | None = None) -> list[str]:
        """Despacha todos los trabajos pendientes que quepan en la ventana."""
        sent: list[str] = []
        while True:
            job_id = self.dispatch_one(run_generation)
            if job_id is None:
                break
            sent.append(job_id)
        return sent

    def run_once(self, run_generation: str | None = None) -> list[str]:
        """Un ciclo completo: despacha pendientes y devuelve la lista enviada."""
        return self.dispatch_all(run_generation)
