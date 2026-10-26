"""Almacén duradero local de trabajos del pipeline.

Implementación sobre SQLite con modo WAL. Cada instancia tiene su propia base de
datos en ``motor/jobs/<instance>.db``. La base de datos es un registro de
control, no contiene imágenes ni embeddings.

Responsabilidades:
- Registrar eventos de captura, unidades, trabajos e intentos.
- Registrar resultados recibidos y su estado de aplicación.
- Guardar claves de idempotencia para evitar efectos duplicados.
- Gestionar generaciones de ejecución y rechazar resultados obsoletos.
- Permitir recuperación tras reinicios.

La conexión se abre y cierra por operación para evitar problemas con hilos y
procesos. Todas las transacciones usan ``BEGIN IMMEDIATE`` para reducir
excepciones ``DATABASE IS LOCKED``.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterator

from motor.core.pipeline_contracts import (
    AnalysisUnit,
    InstanceRef,
    JobRequest,
    JobResult,
    JobStatus,
    MotionEventRef,
    ResultKind,
    UnitResult,
)


class JobStoreError(Exception):
    """Error del almacén de trabajos."""


class GenerationMismatchError(JobStoreError):
    """El resultado pertenece a una generación distinta a la activa."""


SCHEMA = """
CREATE TABLE IF NOT EXISTS generations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instance TEXT NOT NULL,
    run_generation TEXT NOT NULL,
    started_at REAL NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0,
    UNIQUE(instance, run_generation)
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL,
    instance TEXT NOT NULL,
    run_generation TEXT NOT NULL,
    event_json TEXT NOT NULL,
    started_at REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'abierto',
    closed_at REAL,
    UNIQUE(instance, run_generation, event_id)
);

CREATE TABLE IF NOT EXISTS units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id TEXT NOT NULL,
    instance TEXT NOT NULL,
    run_generation TEXT NOT NULL,
    event_id TEXT NOT NULL,
    unit_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pendiente',
    UNIQUE(instance, run_generation, unit_id)
);

CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    instance TEXT NOT NULL,
    run_generation TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    job_json TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    trace_id TEXT NOT NULL,
    submitted_at REAL NOT NULL,
    status TEXT NOT NULL DEFAULT 'pendiente',
    result_id INTEGER,
    UNIQUE(instance, run_generation, job_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(instance, run_generation, status);
CREATE INDEX IF NOT EXISTS idx_jobs_unit ON jobs(instance, run_generation, unit_id);

CREATE TABLE IF NOT EXISTS attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    instance TEXT NOT NULL,
    run_generation TEXT NOT NULL,
    worker_id TEXT,
    started_at REAL,
    finished_at REAL,
    status TEXT NOT NULL,
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_attempts_job ON attempts(instance, run_generation, job_id);

CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT NOT NULL,
    instance TEXT NOT NULL,
    run_generation TEXT NOT NULL,
    result_json TEXT NOT NULL,
    received_at REAL NOT NULL,
    applied_at REAL,
    status TEXT NOT NULL DEFAULT 'recibido',
    error TEXT
);

CREATE INDEX IF NOT EXISTS idx_results_job ON results(instance, run_generation, job_id);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    result_id INTEGER NOT NULL,
    application_type TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    applied_at REAL NOT NULL,
    metadata_json TEXT,
    UNIQUE(result_id, application_type, target_type, target_id)
);

CREATE INDEX IF NOT EXISTS idx_applications_target ON applications(target_type, target_id);

CREATE TABLE IF NOT EXISTS idempotency_keys (
    key TEXT PRIMARY KEY,
    result_id INTEGER NOT NULL,
    applied_at REAL NOT NULL
);
"""


class JobStore:
    """Almacén duradero de trabajos, resultados e idempotencia."""

    def __init__(self, project_root: str, instance: str):
        self.project_root = project_root
        self.instance = instance
        self._db_dir = os.path.join(project_root, "motor", "jobs")
        self._db_path = os.path.join(self._db_dir, f"{instance}.db")
        self._local = threading.local()
        os.makedirs(self._db_dir, exist_ok=True)
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Conexión
    # ------------------------------------------------------------------

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        """Context manager que entrega una conexión SQLite configurada.

        Cada llamada abre su propia conexión para evitar transacciones anidadas
        cuando un método público invoca a otro.
        """
        conn = sqlite3.connect(
            self._db_path,
            timeout=30.0,
            isolation_level=None,
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._conn() as conn:
            conn.executescript(SCHEMA)

    def _begin(self, conn: sqlite3.Connection) -> None:
        conn.execute("BEGIN IMMEDIATE")

    # ------------------------------------------------------------------
    # Generaciones
    # ------------------------------------------------------------------

    def create_generation(self, run_generation: str) -> int:
        """Crea una nueva generación y la marca como activa, desactivando las anteriores."""
        with self._conn() as conn:
            self._begin(conn)
            now = time.time()
            conn.execute(
                "UPDATE generations SET is_active = 0 WHERE instance = ?",
                (self.instance,),
            )
            cur = conn.execute(
                """
                INSERT INTO generations(instance, run_generation, started_at, is_active)
                VALUES (?, ?, ?, 1)
                ON CONFLICT(instance, run_generation) DO UPDATE SET is_active = 1
                """,
                (self.instance, run_generation, now),
            )
            new_id = cur.lastrowid
            # Cancelar trabajos pendientes de generaciones anteriores.
            conn.execute(
                """
                UPDATE jobs SET status = ?
                WHERE instance = ? AND run_generation != ? AND status IN (?, ?, ?)
                """,
                (
                    JobStatus.CANCELADO.value,
                    self.instance,
                    run_generation,
                    JobStatus.PENDIENTE.value,
                    JobStatus.ENVIADO.value,
                    JobStatus.REINTENTO.value,
                ),
            )
            conn.execute("COMMIT")
            return int(new_id)

    def active_generation(self) -> str | None:
        """Devuelve la generación activa de la instancia, o None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT run_generation FROM generations WHERE instance = ? AND is_active = 1 ORDER BY id DESC LIMIT 1",
                (self.instance,),
            ).fetchone()
            return row["run_generation"] if row else None

    def is_active_generation(self, run_generation: str) -> bool:
        active = self.active_generation()
        return active is not None and active == run_generation

    def generations(self) -> list[dict[str, Any]]:
        """Lista todas las generaciones conocidas."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, run_generation, started_at, is_active FROM generations WHERE instance = ? ORDER BY id DESC",
                (self.instance,),
            ).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------

    def _insert_event(
        self,
        conn: sqlite3.Connection,
        event: MotionEventRef,
        status: str = "abierto",
    ) -> int:
        """Inserta/actualiza un evento dentro de una transacción abierta."""
        ref = event.camera.instance
        if ref.instance != self.instance:
            raise JobStoreError("La instancia del evento no coincide con el almacén")
        cur = conn.execute(
            """
            INSERT INTO events(event_id, instance, run_generation, event_json, started_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(instance, run_generation, event_id) DO UPDATE SET
                event_json = excluded.event_json,
                status = excluded.status
            """,
            (
                event.event_id,
                ref.instance,
                ref.run_generation,
                json.dumps(event.to_dict(), ensure_ascii=False),
                event.started_at,
                status,
            ),
        )
        return int(cur.lastrowid)

    def save_event(self, event: MotionEventRef, status: str = "abierto") -> int:
        with self._conn() as conn:
            self._begin(conn)
            rowid = self._insert_event(conn, event, status)
            conn.execute("COMMIT")
            return rowid

    def close_event(self, event_id: str, run_generation: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE events SET status = 'cerrado', closed_at = ? WHERE instance = ? AND run_generation = ? AND event_id = ?",
                (time.time(), self.instance, run_generation, event_id),
            )

    def get_event(self, event_id: str, run_generation: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM events WHERE instance = ? AND run_generation = ? AND event_id = ?",
                (self.instance, run_generation, event_id),
            ).fetchone()
            return dict(row) if row else None

    # ------------------------------------------------------------------
    # Unidades
    # ------------------------------------------------------------------

    def _insert_unit(
        self,
        conn: sqlite3.Connection,
        unit: AnalysisUnit,
        status: str = "pendiente",
    ) -> int:
        """Inserta/actualiza una unidad dentro de una transacción abierta."""
        ref = unit.event.camera.instance
        if ref.instance != self.instance:
            raise JobStoreError("La instancia de la unidad no coincide con el almacén")
        cur = conn.execute(
            """
            INSERT INTO units(unit_id, instance, run_generation, event_id, unit_json, created_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(instance, run_generation, unit_id) DO UPDATE SET
                unit_json = excluded.unit_json,
                status = excluded.status
            """,
            (
                unit.unit_id,
                ref.instance,
                ref.run_generation,
                unit.event.event_id,
                json.dumps(unit.to_dict(), ensure_ascii=False),
                unit.created_at,
                status,
            ),
        )
        return int(cur.lastrowid)

    def save_unit(self, unit: AnalysisUnit, status: str = "pendiente") -> int:
        with self._conn() as conn:
            self._begin(conn)
            rowid = self._insert_unit(conn, unit, status)
            conn.execute("COMMIT")
            return rowid

    def get_unit(self, unit_id: str, run_generation: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM units WHERE instance = ? AND run_generation = ? AND unit_id = ?",
                (self.instance, run_generation, unit_id),
            ).fetchone()
            return dict(row) if row else None

    # ------------------------------------------------------------------
    # Trabajos
    # ------------------------------------------------------------------

    def submit_job(self, request: JobRequest) -> int:
        unit = request.unit
        ref = unit.event.camera.instance
        if ref.instance != self.instance:
            raise JobStoreError("La instancia del trabajo no coincide con el almacén")
        with self._conn() as conn:
            self._begin(conn)
            # Asegurar que la unidad existe en la misma transacción.
            self._insert_unit(conn, unit)
            cur = conn.execute(
                """
                INSERT INTO jobs(job_id, instance, run_generation, unit_id, job_json, priority, trace_id, submitted_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(instance, run_generation, job_id) DO UPDATE SET
                    priority = excluded.priority,
                    job_json = excluded.job_json
                """,
                (
                    request.job_id,
                    ref.instance,
                    ref.run_generation,
                    unit.unit_id,
                    json.dumps(request.to_dict(), ensure_ascii=False),
                    request.priority,
                    unit.trace_id,
                    request.submitted_at,
                    JobStatus.PENDIENTE.value,
                ),
            )
            conn.execute("COMMIT")
            return int(cur.lastrowid)

    def set_job_status(
        self,
        job_id: str,
        run_generation: str,
        status: JobStatus,
        error: str | None = None,
        result_id: int | None = None,
    ) -> bool:
        with self._conn() as conn:
            self._begin(conn)
            fields = ["status = ?"]
            params: list[Any] = [status.value]
            if error is not None:
                fields.append("error = ?")
                params.append(error)
            if result_id is not None:
                fields.append("result_id = ?")
                params.append(result_id)
            params.extend([self.instance, run_generation, job_id])
            sql = f"UPDATE jobs SET {', '.join(fields)} WHERE instance = ? AND run_generation = ? AND job_id = ?"
            cur = conn.execute(sql, params)
            conn.execute("COMMIT")
            return cur.rowcount > 0

    def get_job(self, job_id: str, run_generation: str) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE instance = ? AND run_generation = ? AND job_id = ?",
                (self.instance, run_generation, job_id),
            ).fetchone()
            return dict(row) if row else None

    def list_jobs(
        self,
        status: JobStatus | None = None,
        run_generation: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        with self._conn() as conn:
            sql = "SELECT * FROM jobs WHERE instance = ?"
            params: list[Any] = [self.instance]
            if run_generation:
                sql += " AND run_generation = ?"
                params.append(run_generation)
            if status:
                sql += " AND status = ?"
                params.append(status.value)
            sql += " ORDER BY priority DESC, submitted_at ASC LIMIT ?"
            params.append(limit)
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Intentos
    # ------------------------------------------------------------------

    def record_attempt(
        self,
        job_id: str,
        run_generation: str,
        worker_id: str | None,
        status: str,
        error: str | None = None,
        started_at: float | None = None,
        finished_at: float | None = None,
    ) -> int:
        with self._conn() as conn:
            self._begin(conn)
            cur = conn.execute(
                """
                INSERT INTO attempts(job_id, instance, run_generation, worker_id, started_at, finished_at, status, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    self.instance,
                    run_generation,
                    worker_id,
                    started_at,
                    finished_at,
                    status,
                    error,
                ),
            )
            conn.execute("COMMIT")
            return int(cur.lastrowid)

    # ------------------------------------------------------------------
    # Resultados
    # ------------------------------------------------------------------

    def save_result(self, result: JobResult) -> int:
        unit_result = result.unit_result
        ref = unit_result.instance
        if ref.instance != self.instance:
            raise JobStoreError("La instancia del resultado no coincide con el almacén")
        if not self.is_active_generation(ref.run_generation):
            raise GenerationMismatchError(
                f"Generación {ref.run_generation} no es la activa para {self.instance}"
            )
        with self._conn() as conn:
            self._begin(conn)
            cur = conn.execute(
                """
                INSERT INTO results(job_id, instance, run_generation, result_json, received_at, status)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT DO NOTHING
                """,
                (
                    result.job_id,
                    ref.instance,
                    ref.run_generation,
                    json.dumps(result.to_dict(), ensure_ascii=False),
                    result.received_at,
                    "recibido",
                ),
            )
            result_id = cur.lastrowid
            if result_id:
                conn.execute(
                    "UPDATE jobs SET status = ?, result_id = ? WHERE instance = ? AND run_generation = ? AND job_id = ?",
                    (
                        JobStatus.RESULTADO_RECIBIDO.value,
                        result_id,
                        ref.instance,
                        ref.run_generation,
                        result.job_id,
                    ),
                )
            conn.execute("COMMIT")
            return int(result_id or 0)

    def get_result(self, result_id: int) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM results WHERE id = ? AND instance = ?",
                (result_id, self.instance),
            ).fetchone()
            return dict(row) if row else None

    # ------------------------------------------------------------------
    # Idempotencia
    # ------------------------------------------------------------------

    def is_applied(self, key: str) -> bool:
        """Indica si una clave de idempotencia ya fue aplicada."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM idempotency_keys WHERE key = ?",
                (key,),
            ).fetchone()
            return row is not None

    def record_application(
        self,
        key: str,
        result_id: int,
        application_type: str,
        target_type: str,
        target_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        """Registra una aplicación de forma idempotente.

        Devuelve True si se registró ahora, False si la clave ya existía.
        """
        with self._conn() as conn:
            self._begin(conn)
            now = time.time()
            try:
                conn.execute(
                    "INSERT INTO idempotency_keys(key, result_id, applied_at) VALUES (?, ?, ?)",
                    (key, result_id, now),
                )
            except sqlite3.IntegrityError:
                conn.execute("ROLLBACK")
                return False
            conn.execute(
                """
                INSERT INTO applications(result_id, application_type, target_type, target_id, applied_at, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    result_id,
                    application_type,
                    target_type,
                    target_id,
                    now,
                    json.dumps(metadata or {}, ensure_ascii=False),
                ),
            )
            conn.execute("COMMIT")
            return True

    def set_result_applied(self, result_id: int) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE results SET status = ?, applied_at = ? WHERE id = ? AND instance = ?",
                (JobStatus.APLICADO.value, time.time(), result_id, self.instance),
            )

    # ------------------------------------------------------------------
    # Recuperación
    # ------------------------------------------------------------------

    def pending_or_sent(self, run_generation: str | None = None) -> list[dict[str, Any]]:
        """Trabajos que aún no han recibido resultado."""
        gen = run_generation or self.active_generation()
        if not gen:
            return []
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM jobs
                WHERE instance = ? AND run_generation = ? AND status IN (?, ?)
                ORDER BY priority DESC, submitted_at ASC
                """,
                (
                    self.instance,
                    gen,
                    JobStatus.PENDIENTE.value,
                    JobStatus.ENVIADO.value,
                ),
            ).fetchall()
            return [dict(r) for r in rows]

    def unapplied_results(self, run_generation: str | None = None) -> list[dict[str, Any]]:
        """Resultados recibidos que aún no se han aplicado."""
        gen = run_generation or self.active_generation()
        if not gen:
            return []
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM results
                WHERE instance = ? AND run_generation = ? AND status = ?
                ORDER BY received_at ASC
                """,
                (self.instance, gen, "recibido"),
            ).fetchall()
            return [dict(r) for r in rows]

    def jobs_without_recent_attempt(
        self,
        run_generation: str,
        older_than_s: float = 300.0,
    ) -> list[dict[str, Any]]:
        """Trabajos enviados sin intento reciente (candidatos a recuperación)."""
        cutoff = time.time() - older_than_s
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT j.* FROM jobs j
                WHERE j.instance = ? AND j.run_generation = ? AND j.status = ?
                  AND NOT EXISTS (
                      SELECT 1 FROM attempts a
                      WHERE a.job_id = j.job_id
                        AND a.instance = j.instance
                        AND a.run_generation = j.run_generation
                        AND a.started_at > ?
                  )
                ORDER BY j.submitted_at ASC
                """,
                (self.instance, run_generation, JobStatus.ENVIADO.value, cutoff),
            ).fetchall()
            return [dict(r) for r in rows]
