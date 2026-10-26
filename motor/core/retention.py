"""Retención y limpieza de segmentos de captura (`.units/`).

Los segmentos publicados durante la grabación se conservan mientras algún
trabajo pendiente los necesite. Este módulo elimina los directorios de evento
completamente antiguos y sin referencias, y reporta el espacio liberado.

Reglas:
- Un evento se borra solo si TODOS sus ficheros superan ``max_age_s``.
- Si ``is_referenced(path)`` devuelve True para algún segmento, no se borra.
- ``dry_run`` permite auditar sin tocar disco.
"""
from __future__ import annotations

import dataclasses
import os
import shutil
import time
from typing import Callable, Iterable

ReferenceCheck = Callable[[str], bool]


@dataclasses.dataclass(frozen=True, slots=True)
class RetentionReport:
    removed_dirs: list[str]
    kept_dirs: list[str]
    bytes_freed: int
    dry_run: bool

    def to_dict(self) -> dict:
        return {
            "removed_dirs": self.removed_dirs,
            "kept_dirs": self.kept_dirs,
            "bytes_freed": self.bytes_freed,
            "removed_count": len(self.removed_dirs),
            "kept_count": len(self.kept_dirs),
            "dry_run": self.dry_run,
        }


def _dir_stats(path: str) -> tuple[float, int, list[str]]:
    """Devuelve (mtime más reciente, bytes totales, ficheros)."""
    newest = 0.0
    total = 0
    files: list[str] = []
    for root, _dirs, names in os.walk(path):
        for name in names:
            f = os.path.join(root, name)
            try:
                st = os.stat(f)
            except OSError:
                continue
            files.append(f)
            total += int(st.st_size)
            newest = max(newest, float(st.st_mtime))
    return newest, total, files


def candidate_event_dirs(root: str) -> list[str]:
    """Directorios de evento bajo un árbol `.units/` (o similar)."""
    out: list[str] = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if os.path.isdir(path):
            out.append(path)
    return out


def cleanup_units(
    root: str,
    *,
    max_age_s: float,
    is_referenced: ReferenceCheck | None = None,
    dry_run: bool = False,
    now: float | None = None,
) -> RetentionReport:
    """Elimina eventos antiguos y no referenciados.

    ``root`` puede ser un directorio de cámara (contiene `.units/`) o un
    directorio `.units/` directamente. Se detectan los subdirectorios de evento.
    """
    now = time.time() if now is None else float(now)
    units_root = root
    nested = os.path.join(root, ".units")
    if os.path.isdir(nested):
        units_root = nested

    removed: list[str] = []
    kept: list[str] = []
    freed = 0
    for event_dir in candidate_event_dirs(units_root):
        newest, size, files = _dir_stats(event_dir)
        if not files:
            # Directorio vacío: se puede limpiar sin más.
            kept.append(event_dir)
            continue
        age = now - newest
        referenced = False
        if is_referenced is not None:
            referenced = any(is_referenced(f) for f in files)
        if referenced or age < max_age_s:
            kept.append(event_dir)
            continue
        if dry_run:
            removed.append(event_dir)
            freed += size
        else:
            try:
                shutil.rmtree(event_dir)
                removed.append(event_dir)
                freed += size
            except OSError:
                kept.append(event_dir)

    return RetentionReport(
        removed_dirs=removed,
        kept_dirs=kept,
        bytes_freed=freed,
        dry_run=dry_run,
    )


def referenced_paths_from_jobs(job_rows: Iterable[dict]) -> set[str]:
    """Extrae las rutas de origen de las unidades de trabajos activos."""
    import json

    refs: set[str] = set()
    for row in job_rows:
        try:
            payload = json.loads(row.get("job_json") or "{}")
            unit = payload.get("unit") or {}
            for p in (unit.get("source_paths") or {}).values():
                if p:
                    refs.add(os.path.abspath(str(p)))
        except (json.JSONDecodeError, TypeError, AttributeError):
            continue
    return refs


def make_reference_check(paths: set[str]) -> ReferenceCheck:
    """Crea un comprobador de referencias a partir de un conjunto de rutas."""
    norm = {os.path.abspath(p) for p in paths}

    def _check(path: str) -> bool:
        return os.path.abspath(path) in norm

    return _check


def disk_usage_pct(path: str) -> float:
    """Porcentaje de uso del sistema de ficheros que contiene ``path``."""
    try:
        st = shutil.disk_usage(path)
        if st.total <= 0:
            return 0.0
        return 100.0 * float(st.used) / float(st.total)
    except OSError:
        return 0.0
