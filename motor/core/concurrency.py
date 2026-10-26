"""Configuración de concurrencia derivada de recursos y entorno.

Los valores se calculan a partir de CPU/memoria y pueden sobrescribirse con
variables de entorno para ajustar por nodo sin tocar código:

- ``RF_WORKERS``             número de trabajadores concurrentes
- ``RF_THREADS_PER_WORKER``  hilos de cómputo por trabajador
- ``RF_BATCH_SIZE``          tamaño máximo de lote
- ``RF_BATCH_WAIT_MS``       espera máxima de lote (ms)
- ``RF_WORKER_MEM_MB``       memoria estimada por trabajador (MB)
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class ConcurrencyConfig:
    workers: int
    threads_per_worker: int
    batch_size: int
    batch_wait_s: float

    def to_dict(self) -> dict:
        return {
            "workers": self.workers,
            "threads_per_worker": self.threads_per_worker,
            "batch_size": self.batch_size,
            "batch_wait_s": self.batch_wait_s,
        }


def derive_workers(
    cpu_count: int,
    mem_mb: float,
    *,
    per_worker_mem_mb: float = 2048.0,
    max_workers: int = 8,
    min_workers: int = 1,
) -> int:
    """Nº de trabajadores que caben en CPU y memoria sin sobresuscribir."""
    by_cpu = max(1, int(cpu_count))
    # mem_mb <= 0 significa "desconocida": no se limita por memoria.
    if mem_mb <= 0:
        by_mem = by_cpu
    else:
        by_mem = int(max(0.0, mem_mb) // max(1.0, per_worker_mem_mb)) if per_worker_mem_mb > 0 else by_cpu
    workers = min(by_cpu, by_mem)
    return max(int(min_workers), min(int(max_workers), workers))


def _int(env: Mapping[str, str], key: str, default: int, minimum: int = 1) -> int:
    try:
        v = int(str(env.get(key, default)).strip())
    except (TypeError, ValueError):
        return default
    return max(minimum, v)


def from_env(
    env: Mapping[str, str] | None = None,
    *,
    cpu_count: int | None = None,
    mem_mb: float | None = None,
) -> ConcurrencyConfig:
    """Construye la configuración efectiva (env > derivado)."""
    env = env if env is not None else os.environ
    cpu = int(cpu_count if cpu_count is not None else (os.cpu_count() or 1))
    mem = float(mem_mb if mem_mb is not None else 0.0)
    per_worker = float(env.get("RF_WORKER_MEM_MB", "2048") or 2048)

    if "RF_WORKERS" in env:
        workers = _int(env, "RF_WORKERS", 1)
    elif mem > 0:
        workers = derive_workers(cpu, mem, per_worker_mem_mb=per_worker)
    else:
        workers = max(1, min(8, cpu // 2))

    threads = _int(env, "RF_THREADS_PER_WORKER", max(1, cpu // max(1, workers)))
    batch_size = _int(env, "RF_BATCH_SIZE", 32)
    try:
        wait_ms = float(env.get("RF_BATCH_WAIT_MS", "50"))
    except (TypeError, ValueError):
        wait_ms = 50.0
    return ConcurrencyConfig(
        workers=workers,
        threads_per_worker=threads,
        batch_size=batch_size,
        batch_wait_s=max(0.0, wait_ms / 1000.0),
    )
