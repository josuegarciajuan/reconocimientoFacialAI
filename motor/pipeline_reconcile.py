"""Reconciliador de trabajos del pipeline.

Recupera trabajos que se quedaron en estado ``enviado`` sin intentos recientes,
trata de obtener su estado real desde el directorio de retornos y, si no hay
rastro, los vuelve a marcar como pendientes (hasta un máximo de reintentos) o
los eleva a ``requiere_intervencion``.

También detecta resultados recibidos que no se han aplicado y los deja listos
para el aplicador.
"""
from __future__ import annotations

import json
import os
import time
from typing import Any

from motor.core.instance import returns_dir
from motor.core.job_store import JobStatus


class PipelineReconcile:
    """Recupera trabajos inconclusos del pipeline."""

    def __init__(
        self,
        job_store,
        *,
        project_root: str,
        returns_dir_override: str | None = None,
        stale_after_s: float = 300.0,
        max_retries: int = 3,
    ):
        self.store = job_store
        self.project_root = project_root
        self.returns_dir = returns_dir_override or returns_dir(project_root)
        self.stale_after_s = stale_after_s
        self.max_retries = max_retries

    def _result_exists(self, job_id: str) -> bool:
        job_dir = os.path.join(self.returns_dir, job_id)
        if not os.path.isdir(job_dir):
            return False
        candidates = [
            os.path.join(job_dir, "result", "result.json"),
            os.path.join(job_dir, "result.json"),
            os.path.join(job_dir, "result", "efectos.json"),
            os.path.join(job_dir, "efectos.json"),
        ]
        return any(os.path.isfile(p) for p in candidates)

    def _attempt_count(self, job_id: str, run_generation: str) -> int:
        with self.store._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS c FROM attempts WHERE instance = ? AND run_generation = ? AND job_id = ?",
                (self.store.instance, run_generation, job_id),
            ).fetchone()
            return int(row["c"]) if row else 0

    def reconcile_generation(self, run_generation: str) -> dict[str, Any]:
        """Reconcilia una generación concreta.

        Devuelve estadísticas de la operación.
        """
        stats = {"recovered": 0, "retried": 0, "intervened": 0, "with_result": 0, "unchanged": 0}

        # Trabajos enviados sin intento reciente.
        stale = self.store.jobs_without_recent_attempt(
            run_generation, older_than_s=self.stale_after_s
        )
        for row in stale:
            job_id = row["job_id"]

            # Si ya hay un resultado, solo falta aplicarlo.
            if self._result_exists(job_id):
                self.store.set_job_status(
                    job_id, run_generation, JobStatus.RESULTADO_RECIBIDO
                )
                stats["with_result"] += 1
                continue

            attempts = self._attempt_count(job_id, run_generation)
            if attempts >= self.max_retries:
                self.store.set_job_status(
                    job_id,
                    run_generation,
                    JobStatus.REQUIERE_INTERVENCION,
                    error=f"sin resultado tras {attempts} intentos",
                )
                stats["intervened"] += 1
            else:
                self.store.set_job_status(
                    job_id, run_generation, JobStatus.REINTENTO
                )
                stats["retried"] += 1

        # Resultados recibidos que aún no se han aplicado quedan para el aplicador.
        unapplied = self.store.unapplied_results(run_generation)
        stats["unapplied_results"] = len(unapplied)

        # Trabajos en estado REINTENTO los pasamos a PENDIENTE para que el
        # despachador los vuelva a enviar.
        with self.store._conn() as conn:
            cur = conn.execute(
                "UPDATE jobs SET status = ? WHERE instance = ? AND run_generation = ? AND status = ?",
                (
                    JobStatus.PENDIENTE.value,
                    self.store.instance,
                    run_generation,
                    JobStatus.REINTENTO.value,
                ),
            )
            stats["recovered"] = cur.rowcount

        return stats

    def reconcile(self) -> dict[str, Any]:
        """Reconcilia la generación activa."""
        active = self.store.active_generation()
        if not active:
            return {"active_generation": None, "stats": {}}
        return {
            "active_generation": active,
            "stats": self.reconcile_generation(active),
        }

    def run_once(self) -> dict[str, Any]:
        """Un ciclo completo de reconciliación."""
        return self.reconcile()
