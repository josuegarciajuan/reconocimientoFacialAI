#!/usr/bin/env python3
"""Servicio operativo del pipeline de reconocimiento facial.

Integra en un solo proceso:

- despacho asíncrono a SuperServer,
- recolección y validación de resultados,
- reconciliación de trabajos,
- coordinación de sesiones con publicación temprana/final,
- retención de segmentos `.units/`,
- emisión periódica de métricas de cola.

El servicio es idempotente y recuperable: al arrancar reconcilia el estado
persistido y continúa donde quedó. Se puede ejecutar con ``--once`` para una
sola pasada (pruebas/operación manual).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import signal
import sys
import threading
import time
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.env import get, get_float, get_int  # noqa: E402
from motor.core.gallery_cache import CachedGalleryMatcher, GalleryEntry  # noqa: E402
from motor.core.instance import project_id  # noqa: E402
from motor.core.job_store import JobStore  # noqa: E402
from motor.core.pipeline_contracts import new_run_generation  # noqa: E402
from motor.core.pipeline_metrics import MetricsRecorder  # noqa: E402
from motor.core.recognition_session import NullGallery, SessionConfig  # noqa: E402
from motor.core.result_publisher import (  # noqa: E402
    JsonlSink,
    NullSink,
    ResultPublisher,
    SessionCoordinator,
    make_collector_hook,
)
from motor.core.retention import (  # noqa: E402
    cleanup_units,
    disk_usage_pct,
    make_reference_check,
    referenced_paths_from_jobs,
)
from motor.pipeline_collector import PipelineCollector  # noqa: E402
from motor.pipeline_dispatcher import PipelineDispatcher  # noqa: E402
from motor.pipeline_reconcile import PipelineReconcile  # noqa: E402

log = logging.getLogger("rf-pipeline")


def _flag(name: str, default: str = "0") -> bool:
    return (os.environ.get(name, default) or "").strip().lower() in (
        "1", "true", "yes", "on", "si", "sí",
    )


class PipelineService:
    """Orquesta los componentes del pipeline."""

    def __init__(
        self,
        project_root: str,
        *,
        local_id: int = 1,
        gallery=None,
        sink=None,
        session_config: SessionConfig | None = None,
        max_sent: int = 20,
        close_after_s: float = 30.0,
        units_max_age_s: float = 6 * 3600.0,
        intervals: dict[str, float] | None = None,
        metrics: MetricsRecorder | None = None,
        spool_dir: str | None = None,
        returns_dir_override: str | None = None,
    ):
        self.project_root = project_root
        self.local_id = int(local_id)
        self.instance = project_id(project_root)
        self.store = JobStore(project_root, self.instance)

        self.metrics = metrics or MetricsRecorder(project_root, self.local_id)
        self.gallery = gallery or NullGallery()
        self.sink = sink or JsonlSink(
            os.path.join(project_root, "motor", "logs", "pipeline_publications.jsonl")
        )
        self.publisher = ResultPublisher(self.store, self.sink)
        self.coordinator = SessionCoordinator(
            self.publisher,
            config=session_config,
            gallery=self.gallery,
            close_after_s=close_after_s,
        )
        dispatcher_kwargs = {"project_root": project_root, "max_sent": max_sent}
        if spool_dir is not None:
            dispatcher_kwargs["spool_dir"] = spool_dir
        self.dispatcher = PipelineDispatcher(self.store, **dispatcher_kwargs)
        self.collector = PipelineCollector(
            self.store,
            project_root=project_root,
            returns_dir_override=returns_dir_override,
            on_result=make_collector_hook(self.coordinator),
        )
        self.reconciler = PipelineReconcile(self.store, project_root=project_root)
        self.units_max_age_s = float(units_max_age_s)

        self.intervals = {
            "dispatch": 2.0,
            "collect": 2.0,
            "reconcile": 30.0,
            "sessions": 10.0,
            "retention": 3600.0,
            "metrics": 30.0,
        }
        if intervals:
            self.intervals.update({k: float(v) for k, v in intervals.items()})

        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self._started_at: float | None = None
        self._cycles: dict[str, int] = {k: 0 for k in self.intervals}
        self._errors: dict[str, int] = {k: 0 for k in self.intervals}
        self._status_lock = threading.Lock()

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------
    def ensure_generation(self) -> str:
        gen = self.store.active_generation()
        if not gen:
            gen = new_run_generation()
            self.store.create_generation(gen)
            log.info("generación creada: %s", gen)
        return gen

    def start(self) -> None:
        if self._threads:
            return
        gen = self.ensure_generation()
        log.info("iniciando pipeline instance=%s generation=%s", self.instance, gen)
        # Reconciliación de arranque: recupera trabajos huérfanos antes de escuchar.
        try:
            self.reconciler.run_once()
        except Exception as exc:  # noqa: BLE001
            log.warning("reconciliación inicial falló: %s", exc)
        self._started_at = time.time()
        loops = [
            ("dispatch", lambda: self.dispatcher.run_once()),
            ("collect", lambda: self.collector.run_once()),
            ("reconcile", lambda: self.reconciler.run_once()),
            ("sessions", lambda: self.coordinator.close_stale()),
            ("retention", lambda: self.cleanup_retention()),
            ("metrics", lambda: self.emit_metrics()),
        ]
        for name, fn in loops:
            t = threading.Thread(
                target=self._loop, args=(name, self.intervals[name], fn),
                name=f"rf-pipeline-{name}", daemon=True,
            )
            t.start()
            self._threads.append(t)

    def _loop(self, name: str, interval: float, fn) -> None:
        while not self._stop.wait(interval):
            try:
                fn()
                with self._status_lock:
                    self._cycles[name] += 1
            except Exception as exc:  # noqa: BLE001
                with self._status_lock:
                    self._errors[name] += 1
                log.warning("ciclo %s falló: %s", name, exc)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=timeout)
        self._threads.clear()
        log.info("pipeline detenido")

    # ------------------------------------------------------------------
    # Pasada única
    # ------------------------------------------------------------------
    def run_once(self) -> dict[str, Any]:
        """Una pasada de cada componente (sin hilos)."""
        gen = self.ensure_generation()
        out: dict[str, Any] = {"generation": gen}
        try:
            out["dispatched"] = len(self.dispatcher.run_once())
        except Exception as exc:  # noqa: BLE001
            out["dispatched_error"] = str(exc)
        try:
            out["collected"] = len(self.collector.run_once())
        except Exception as exc:  # noqa: BLE001
            out["collected_error"] = str(exc)
        try:
            out["reconcile"] = self.reconciler.run_once()
        except Exception as exc:  # noqa: BLE001
            out["reconcile_error"] = str(exc)
        try:
            out["sessions_closed"] = self.coordinator.close_stale()
        except Exception as exc:  # noqa: BLE001
            out["sessions_error"] = str(exc)
        try:
            out["retention"] = self.cleanup_retention().to_dict()
        except Exception as exc:  # noqa: BLE001
            out["retention_error"] = str(exc)
        self.emit_metrics()
        return out

    # ------------------------------------------------------------------
    # Retención y métricas
    # ------------------------------------------------------------------
    def _videos_root(self) -> str:
        return os.path.join(self.project_root, "motor", "videos")

    def cleanup_retention(self):
        """Limpia `.units/` antiguos no referenciados."""
        refs = referenced_paths_from_jobs(self.store.active_jobs())
        check = make_reference_check(refs)
        root = self._videos_root()
        removed: list[str] = []
        kept: list[str] = []
        freed = 0
        if os.path.isdir(root):
            for local in sorted(os.listdir(root)):
                local_dir = os.path.join(root, local)
                if not os.path.isdir(local_dir):
                    continue
                for cam in sorted(os.listdir(local_dir)):
                    cam_dir = os.path.join(local_dir, cam)
                    if not os.path.isdir(cam_dir):
                        continue
                    report = cleanup_units(
                        cam_dir,
                        max_age_s=self.units_max_age_s,
                        is_referenced=check,
                    )
                    removed.extend(report.removed_dirs)
                    kept.extend(report.kept_dirs)
                    freed += report.bytes_freed
        from motor.core.retention import RetentionReport

        return RetentionReport(
            removed_dirs=removed, kept_dirs=kept, bytes_freed=freed, dry_run=False
        )

    def emit_metrics(self) -> None:
        gen = self.store.active_generation()
        if not gen:
            return
        counts = self.store.counts_by_status(gen)
        self.metrics.queue_state(
            pending=counts.get("pendiente", 0),
            sent=counts.get("enviado", 0),
            executing=counts.get("ejecutando", 0),
            received=counts.get("resultado_recibido", 0),
            applying=counts.get("aplicando", 0),
            applied=counts.get("aplicado", 0),
            extra={"generation": gen},
        )

    # ------------------------------------------------------------------
    # Estado
    # ------------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        gen = self.store.active_generation()
        counts = self.store.counts_by_status(gen) if gen else {}
        return {
            "instance": self.instance,
            "generation": gen,
            "running": bool(self._threads),
            "started_at": self._started_at,
            "uptime_s": (time.time() - self._started_at) if self._started_at else 0.0,
            "cycles": dict(self._cycles),
            "errors": dict(self._errors),
            "queues": counts,
            "sessions": self.coordinator.stats(),
            "dispatcher": {"max_sent": self.dispatcher.max_sent},
            "retention": {"units_max_age_s": self.units_max_age_s},
            "disk_pct": disk_usage_pct(self.project_root),
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_gallery(path: str) -> CachedGalleryMatcher | None:
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            raw = json.load(fh)
        entries = [
            GalleryEntry(
                person_id=int(it["person_id"]),
                label=str(it.get("label") or ""),
                embedding=tuple(float(v) for v in it["embedding"]),
            )
            for it in raw
        ]
        gallery = CachedGalleryMatcher()
        gallery.set_gallery(str(os.path.getmtime(path)), entries)
        log.info("galería cargada: %d entradas", len(entries))
        return gallery
    except Exception as exc:  # noqa: BLE001
        log.warning("no se pudo cargar la galería %s: %s", path, exc)
        return None


def build_service(project_root: str, args) -> PipelineService:
    intervals = {
        "dispatch": get_float(None, "RF_PIPELINE_DISPATCH_S", 2.0),
        "collect": get_float(None, "RF_PIPELINE_COLLECT_S", 2.0),
        "reconcile": get_float(None, "RF_PIPELINE_RECONCILE_S", 30.0),
        "sessions": get_float(None, "RF_PIPELINE_SESSIONS_S", 10.0),
        "retention": get_float(None, "RF_PIPELINE_RETENTION_S", 3600.0),
        "metrics": get_float(None, "RF_PIPELINE_METRICS_S", 30.0),
    }
    cfg = SessionConfig(
        cluster_cosine=get_float(None, "RF_CLUSTER_COSINE", 0.50),
        match_min_score=get_float(None, "RF_MATCH_MIN_SCORE", 0.45),
        match_min_margin=get_float(None, "RF_MATCH_MIN_MARGIN", 0.08),
        min_faces_confirm=get_int(None, "RF_MIN_FACES_CONFIRM", 1),
        min_quality_confirm=get_float(None, "RF_MIN_QUALITY_CONFIRM", 0.0),
    )
    gallery = _load_gallery(args.gallery_file) if args.gallery_file else None
    sink = JsonlSink(args.publications) if args.publications else NullSink()
    return PipelineService(
        project_root,
        local_id=args.local,
        gallery=gallery,
        sink=sink,
        session_config=cfg,
        max_sent=get_int(None, "RF_PIPELINE_MAX_SENT", 20),
        close_after_s=get_float(None, "RF_PIPELINE_CLOSE_AFTER_S", 30.0),
        units_max_age_s=get_float(None, "RF_PIPELINE_UNITS_MAX_AGE_H", 6.0) * 3600.0,
        intervals=intervals,
    )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Servicio del pipeline RF")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--local", type=int, default=1)
    ap.add_argument("--once", action="store_true", help="una sola pasada y salir")
    ap.add_argument("--status", action="store_true", help="imprimir estado y salir")
    ap.add_argument("--gallery-file", default=os.environ.get("RF_PIPELINE_GALLERY", ""))
    ap.add_argument(
        "--publications",
        default=os.environ.get(
            "RF_PIPELINE_PUBLICATIONS",
            os.path.join(os.path.dirname(__file__), "logs", "pipeline_publications.jsonl"),
        ),
    )
    ap.add_argument("--log-level", default=os.environ.get("RF_PIPELINE_LOG_LEVEL", "INFO"))
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, str(args.log_level).upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    service = build_service(args.ruta, args)

    if args.status:
        print(json.dumps(service.status(), ensure_ascii=False, indent=2))
        return 0
    if args.once:
        print(json.dumps(service.run_once(), ensure_ascii=False, indent=2))
        return 0

    stop = threading.Event()

    def _handle(signum, _frame):
        log.info("señal %s: deteniendo", signum)
        stop.set()

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)

    if not _flag("RF_PIPELINE_ENABLED", "1"):
        log.warning("RF_PIPELINE_ENABLED=0: el servicio no arranca")
        return 0

    service.start()
    try:
        while not stop.wait(1.0):
            pass
    finally:
        service.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
