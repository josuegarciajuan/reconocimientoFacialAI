"""Lotes con límite de tamaño y de espera.

Útil para agrupar caras o actualizaciones de galería sin introducir latencia
ilimitada: se vacía cuando se alcanza ``max_size`` o cuando el elemento más
antiguo lleva ``max_wait_s`` esperando.

No usa hilo propio: el productor llama ``add()`` y ``flush_if_due()`` (o
``tick()``) desde su bucle. Esto evita hilos ocultos y facilita las pruebas.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T")


@dataclass
class BatchStats:
    batches_flushed: int = 0
    items_flushed: int = 0
    flushes_by_size: int = 0
    flushes_by_wait: int = 0
    flushes_manual: int = 0

    def to_dict(self) -> dict[str, int]:
        return {
            "batches_flushed": self.batches_flushed,
            "items_flushed": self.items_flushed,
            "flushes_by_size": self.flushes_by_size,
            "flushes_by_wait": self.flushes_by_wait,
            "flushes_manual": self.flushes_manual,
        }


class Batcher(Generic[T]):
    """Acumula elementos y los entrega al callback en lotes."""

    def __init__(
        self,
        flush_fn: Callable[[list[T]], Any],
        *,
        max_size: int = 32,
        max_wait_s: float = 0.05,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.flush_fn = flush_fn
        self.max_size = max(1, int(max_size))
        self.max_wait_s = max(0.0, float(max_wait_s))
        self._clock = clock
        self._lock = threading.Lock()
        self._items: list[T] = []
        self._first_at: float | None = None
        self.stats = BatchStats()

    @property
    def pending(self) -> int:
        with self._lock:
            return len(self._items)

    def add(self, item: T) -> bool:
        """Añade un elemento. Devuelve True si se vació por tamaño."""
        batch: list[T] | None = None
        with self._lock:
            if not self._items:
                self._first_at = self._clock()
            self._items.append(item)
            if len(self._items) >= self.max_size:
                batch = self._take_locked()
                self.stats.flushes_by_size += 1
        if batch is not None:
            self._emit(batch)
            return True
        return False

    def _take_locked(self) -> list[T] | None:
        if not self._items:
            return None
        batch = self._items
        self._items = []
        self._first_at = None
        return batch

    def _emit(self, batch: list[T]) -> None:
        self.stats.batches_flushed += 1
        self.stats.items_flushed += len(batch)
        try:
            self.flush_fn(batch)
        except Exception:  # noqa: BLE001 — el productor no debe romperse por el consumidor
            pass

    def flush(self) -> int:
        """Vacía manualmente. Devuelve el número de elementos entregados."""
        with self._lock:
            batch = self._take_locked()
            if batch is not None:
                self.stats.flushes_manual += 1
        if batch is None:
            return 0
        self._emit(batch)
        return len(batch)

    def flush_if_due(self) -> int:
        """Vacía si el lote lleva más de ``max_wait_s`` esperando."""
        with self._lock:
            if not self._items or self._first_at is None:
                return 0
            waited = self._clock() - self._first_at
            if waited < self.max_wait_s:
                return 0
            batch = self._take_locked()
            self.stats.flushes_by_wait += 1
        if batch is None:
            return 0
        self._emit(batch)
        return len(batch)

    def tick(self) -> int:
        """Alias de ``flush_if_due`` para llamar desde el bucle del productor."""
        return self.flush_if_due()

    def stats_dict(self) -> dict[str, int]:
        with self._lock:
            return self.stats.to_dict()
