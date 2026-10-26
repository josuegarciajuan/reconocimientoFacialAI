"""Galería cacheada para el camino crítico.

Optimizaciones:
- Matriz de embeddings normalizada por versión de galería (no se reconstruye
  por cara).
- Caché LRU de puntuaciones por embedding exacto (evita recomputar la misma
  cara entre unidades/eventos).
- ``match_batch`` vectorizado para lotes de caras.

No cambia la semántica: usa el mismo coseno y devuelve el mejor y el segundo
mejor candidato, como la galería directa.
"""
from __future__ import annotations

import hashlib
import math
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Iterable

from motor.core.recognition_session import MatchResult

try:  # numpy es opcional para el fallback
    import numpy as _np
except Exception:  # noqa: BLE001
    _np = None


@dataclass(frozen=True, slots=True)
class GalleryEntry:
    """Entrada de galería."""

    person_id: int
    label: str
    embedding: tuple[float, ...]


@dataclass
class GallerySnapshot:
    """Matriz normalizada de una versión de galería."""

    version: str
    entries: list[GalleryEntry]
    _matrix: Any = field(default=None, repr=False)
    _person_ids: list[int] = field(default_factory=list)
    _labels: list[str] = field(default_factory=list)
    _dim: int = 0

    def build(self) -> None:
        self._person_ids = [e.person_id for e in self.entries]
        self._labels = [e.label for e in self.entries]
        if not self.entries:
            self._matrix = None
            self._dim = 0
            return
        self._dim = len(self.entries[0].embedding)
        if _np is not None:
            m = _np.asarray([e.embedding for e in self.entries], dtype=_np.float32)
            norms = _np.linalg.norm(m, axis=1, keepdims=True)
            self._matrix = m / _np.maximum(norms, 1e-9)
        else:
            self._matrix = None

    @property
    def size(self) -> int:
        return len(self.entries)

    @property
    def dim(self) -> int:
        return self._dim

    def scores(self, embedding: list[float] | tuple[float, ...]) -> list[float]:
        """Coseno contra todas las entradas."""
        if not self.entries:
            return []
        if _np is not None and self._matrix is not None:
            q = _np.asarray(embedding, dtype=_np.float32)
            n = float(_np.linalg.norm(q)) or 1.0
            q = q / n
            if len(q) != self._dim:
                return [0.0] * len(self.entries)
            return [float(x) for x in (self._matrix @ q)]
        # Fallback puro Python.
        out: list[float] = []
        qn = math.sqrt(sum(float(v) * float(v) for v in embedding)) or 1.0
        for e in self.entries:
            if len(e.embedding) != len(embedding):
                out.append(0.0)
                continue
            dot = sum(float(a) * float(b) for a, b in zip(e.embedding, embedding))
            en = math.sqrt(sum(float(v) * float(v) for v in e.embedding)) or 1.0
            out.append(dot / (qn * en))
        return out

    def top2(self, embedding: list[float] | tuple[float, ...]) -> MatchResult | None:
        scores = self.scores(embedding)
        if not scores:
            return None
        best_i = max(range(len(scores)), key=scores.__getitem__)
        best = scores[best_i]
        second = 0.0
        for i, s in enumerate(scores):
            if i != best_i and s > second:
                second = s
        return MatchResult(
            person_id=self._person_ids[best_i],
            label=self._labels[best_i],
            score=float(best),
            second_score=float(second),
            method="cached_matrix",
        )


def _embedding_key(embedding: Iterable[float]) -> bytes:
    """Clave estable de un embedding (float32 exacto)."""
    if _np is not None:
        arr = _np.asarray(list(embedding), dtype=_np.float32)
        return hashlib.blake2b(arr.tobytes(), digest_size=16).digest()
    import struct

    vals = [float(v) for v in embedding]
    return hashlib.blake2b(struct.pack(f"{len(vals)}f", *vals), digest_size=16).digest()


class CachedGalleryMatcher:
    """Galería con matriz por versión y caché de puntuaciones."""

    def __init__(self, *, max_cache: int = 8192):
        self.max_cache = max(1, int(max_cache))
        self._lock = threading.Lock()
        self._snapshot: GallerySnapshot | None = None
        self._cache: OrderedDict[bytes, MatchResult | None] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._batch_calls = 0
        self._batch_items = 0

    # -- galería --------------------------------------------------------
    def set_gallery(
        self,
        version: str,
        entries: Iterable[GalleryEntry],
    ) -> GallerySnapshot:
        snap = GallerySnapshot(version=str(version), entries=list(entries))
        snap.build()
        with self._lock:
            if self._snapshot is None or self._snapshot.version != snap.version:
                self._cache.clear()
            self._snapshot = snap
        return snap

    def invalidate(self) -> None:
        with self._lock:
            self._snapshot = None
            self._cache.clear()

    @property
    def version(self) -> str | None:
        with self._lock:
            return self._snapshot.version if self._snapshot else None

    @property
    def size(self) -> int:
        with self._lock:
            return self._snapshot.size if self._snapshot else 0

    # -- match ----------------------------------------------------------
    def match(self, embedding: list[float]) -> MatchResult | None:
        if not embedding:
            return None
        key = _embedding_key(embedding)
        with self._lock:
            if key in self._cache:
                self._hits += 1
                value = self._cache[key]
                self._cache.move_to_end(key)
                return value
            self._misses += 1
            snap = self._snapshot
        result = snap.top2(embedding) if snap is not None else None
        with self._lock:
            self._cache[key] = result
            self._cache.move_to_end(key)
            while len(self._cache) > self.max_cache:
                self._cache.popitem(last=False)
        return result

    def match_batch(self, embeddings: list[list[float]]) -> list[MatchResult | None]:
        """Versión por lotes (vectorizada cuando numpy está disponible)."""
        if not embeddings:
            return []
        with self._lock:
            self._batch_calls += 1
            self._batch_items += len(embeddings)
            snap = self._snapshot
        if snap is None or snap.size == 0:
            return [None] * len(embeddings)

        if _np is not None and snap._matrix is not None:
            m = _np.asarray(embeddings, dtype=_np.float32)
            norms = _np.linalg.norm(m, axis=1, keepdims=True)
            m = m / _np.maximum(norms, 1e-9)
            sims = m @ snap._matrix.T  # (n_query, n_gallery)
            out: list[MatchResult | None] = []
            for row in sims:
                idx = int(row.argmax())
                best = float(row[idx])
                if row.size > 1:
                    second = float(_np.partition(row, -2)[-2])
                else:
                    second = 0.0
                out.append(
                    MatchResult(
                        person_id=snap._person_ids[idx],
                        label=snap._labels[idx],
                        score=best,
                        second_score=second,
                        method="cached_matrix_batch",
                    )
                )
            return out

        return [self.match(e) for e in embeddings]

    # -- diagnóstico ----------------------------------------------------
    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "version": self._snapshot.version if self._snapshot else None,
                "gallery_size": self._snapshot.size if self._snapshot else 0,
                "cache_size": len(self._cache),
                "max_cache": self.max_cache,
                "hits": self._hits,
                "misses": self._misses,
                "batch_calls": self._batch_calls,
                "batch_items": self._batch_items,
            }
