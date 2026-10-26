"""Colector asíncrono de resultados de SuperServer.

Escanea el directorio de retornos de SuperServer
(``/var/lib/taildeck/returns/<project>``), lee los resultados terminados, los
valida contra la generación activa y los guarda en el ``JobStore``.

El colector también escribe el ack en ``/var/lib/taildeck/spool/acks`` para que
el plano de control de SuperServer pueda limpiar el trabajo.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from motor.core.instance import project_id, returns_dir
from motor.core.job_store import GenerationMismatchError, JobStatus
from motor.core.pipeline_contracts import JobResult
from motor.pool_ack import escribir_ack


class CollectorError(Exception):
    """Error del colector."""


class PipelineCollector:
    """Recoge resultados de SuperServer y los integra en el JobStore."""

    def __init__(
        self,
        job_store,
        *,
        project_root: str,
        returns_dir_override: str | None = None,
        ack: bool = True,
        verify_artifacts: bool = False,
        on_result=None,
    ):
        self.store = job_store
        self.project_root = project_root
        self.project_id = project_id(project_root)
        self.returns_dir = returns_dir_override or returns_dir(project_root)
        self.ack = ack
        # En la casa los artefactos llegan después del resultado; el aplicador
        # los verifica al moverlos. En un entorno con el sandbox del worker
        # accesible se puede activar esta comprobación.
        self.verify_artifacts = verify_artifacts
        # Hook opcional tras guardar un resultado (coordinador de sesiones).
        self.on_result = on_result

    def _result_file(self, job_dir: str) -> str | None:
        """Devuelve la ruta del fichero de resultado si existe."""
        candidates = [
            os.path.join(job_dir, "result", "result.json"),
            os.path.join(job_dir, "result.json"),
            os.path.join(job_dir, "result", "efectos.json"),
            os.path.join(job_dir, "efectos.json"),
        ]
        for path in candidates:
            if os.path.isfile(path):
                return path
        return None

    def _is_applied_marker(self, job_dir: str) -> bool:
        # `.aplicado`: efectos ya aplicados en la casa (aplicador).
        # `.pipeline_collected`: resultado ya ingerido en el JobStore (evita
        # releer el mismo result.json en cada ciclo del colector).
        return os.path.exists(os.path.join(job_dir, ".aplicado")) or os.path.exists(
            os.path.join(job_dir, ".pipeline_collected")
        )

    def _write_collected_marker(self, job_dir: str) -> None:
        try:
            with open(os.path.join(job_dir, ".pipeline_collected"), "w", encoding="utf-8") as fh:
                fh.write(str(time.time()))
        except OSError:
            pass

    def _read_result(self, job_dir: str) -> dict[str, Any] | None:
        path = self._result_file(job_dir)
        if not path:
            return None
        try:
            with open(path, encoding="utf-8") as fh:
                return json.load(fh)
        except (OSError, json.JSONDecodeError):
            return None

    def _job_id_from_dir(self, job_dir: str) -> str:
        return os.path.basename(os.path.abspath(job_dir))

    def collect_one(self, job_dir: str) -> str | None:
        """Procesa un directorio de retorno concreto.

        Devuelve el ``job_id`` procesado o None si no había resultado válido.
        """
        if self._is_applied_marker(job_dir):
            return None

        data = self._read_result(job_dir)
        if not data:
            return None

        job_id = self._job_id_from_dir(job_dir)

        # El resultado puede venir en formato nuevo (JobResult) o en el formato
        # heredado de efectos. En el formato heredado no tenemos generación y
        # debemos rechazarlo en el pipeline nuevo.
        if "unit_result" not in data:
            self._mark_error(job_dir, job_id, "formato heredado sin unit_result")
            return None

        try:
            result = JobResult.from_dict(data)
        except (KeyError, TypeError, ValueError) as exc:
            self._mark_error(job_dir, job_id, f"resultado inválido: {exc}")
            return None

        run_generation = result.unit_result.instance.run_generation
        if not self.store.is_active_generation(run_generation):
            self._mark_error(
                job_dir,
                job_id,
                f"generación {run_generation} no activa; resultado rechazado",
            )
            return None

        # Verificar que los artefactos declarados están completos. Cuando la
        # comprobación está activa (sandbox del worker accesible), no se acepta
        # un resultado cuyos ficheros aún no existen.
        artifacts = result.unit_result.artifacts or {}
        if self.verify_artifacts and artifacts:
            missing = [p for p in artifacts.values() if not os.path.exists(p)]
            if missing:
                self._mark_error(
                    job_dir, job_id, f"artefactos incompletos: {missing}"
                )
                return None

        try:
            result_id = self.store.save_result(result)
        except GenerationMismatchError as exc:
            self._mark_error(job_dir, job_id, str(exc))
            return None

        if self.ack:
            escribir_ack(job_id, status="received", source="pipeline_collector")

        if self.on_result is not None:
            try:
                self.on_result(result, result_id)
            except Exception:  # noqa: BLE001 — la recolección no se rompe por un hook
                pass

        self._write_collected_marker(job_dir)
        return job_id

    def _mark_error(self, job_dir: str, job_id: str, error: str) -> None:
        """Escribe un marcador de error para evitar releer el mismo directorio."""
        try:
            marker = os.path.join(job_dir, ".pipeline_error")
            with open(marker, "w", encoding="utf-8") as fh:
                fh.write(f"{time.time()}\t{error}\n")
        except OSError:
            pass
        # También actualizamos el estado en el store si existe el trabajo.
        active_gen = self.store.active_generation()
        if active_gen:
            self.store.set_job_status(
                job_id, active_gen, JobStatus.REQUIERE_INTERVENCION, error=error
            )

    def collect_all(self) -> list[str]:
        """Escanea todo el directorio de retornos y procesa los resultados listos."""
        processed: list[str] = []
        if not os.path.isdir(self.returns_dir):
            return processed

        for name in sorted(os.listdir(self.returns_dir)):
            job_dir = os.path.join(self.returns_dir, name)
            if not os.path.isdir(job_dir):
                continue
            job_id = self.collect_one(job_dir)
            if job_id:
                processed.append(job_id)
        return processed

    def run_once(self) -> list[str]:
        """Un ciclo completo de recolección."""
        return self.collect_all()
