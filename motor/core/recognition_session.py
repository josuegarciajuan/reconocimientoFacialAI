"""Reconocimiento incremental y publicación temprana.

Una ``RecognitionSession`` agrupa las detecciones de un evento de movimiento,
las agrupa por identidad y produce:

- ``TEMPRANO``: mejor hipótesis disponible, siempre provisional.
- ``FINAL``: decisión cerrada tras cerrar la sesión y aplicar reglas de
  evidencia/calidad/margen.

La galería es inyectable (``GalleryMatcher``) para poder probar sin BD. Si no se
inyecta, las caras quedan sin identificar y la sesión solo agrupa.
"""
from __future__ import annotations

import dataclasses
import math
import time
from typing import Any, Protocol

from motor.core.pipeline_contracts import (
    CameraRef,
    FaceDetection,
    RecognitionCandidate,
    ResultKind,
    UnitResult,
)


# ---------------------------------------------------------------------------
# Galería inyectable
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class MatchResult:
    """Resultado de comparar un embedding con la galería."""

    person_id: int | None
    label: str | None
    score: float
    second_score: float = 0.0
    method: str = "embedding"

    @property
    def margin(self) -> float:
        return max(0.0, float(self.score) - float(self.second_score))


class GalleryMatcher(Protocol):
    """Interfaz mínima de la galería."""

    def match(self, embedding: list[float]) -> MatchResult | None:
        ...


class NullGallery:
    """Galería vacía: todo queda sin identificar (para pruebas / bootstrap)."""

    def match(self, embedding: list[float]) -> MatchResult | None:
        return None


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class SessionConfig:
    """Umbrales de agrupación y confirmación."""

    cluster_cosine: float = 0.50
    match_min_score: float = 0.45
    match_min_margin: float = 0.08
    min_faces_confirm: int = 1
    min_quality_confirm: float = 0.0
    early_min_faces: int = 1


DEFAULT_SESSION_CONFIG = SessionConfig()


# ---------------------------------------------------------------------------
# Clústeres
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class _Cluster:
    cluster_id: str
    faces: list[FaceDetection] = dataclasses.field(default_factory=list)
    _sum: list[float] | None = None
    _count: int = 0

    def add(self, face: FaceDetection) -> None:
        self.faces.append(face)
        if face.embedding:
            if self._sum is None:
                self._sum = [0.0] * len(face.embedding)
            if len(face.embedding) == len(self._sum):
                for i, v in enumerate(face.embedding):
                    self._sum[i] += float(v)
                self._count += 1

    @property
    def centroid(self) -> list[float] | None:
        if not self._sum or self._count <= 0:
            return None
        n = math.sqrt(sum(v * v for v in self._sum)) or 1.0
        return [v / n for v in self._sum]

    @property
    def size(self) -> int:
        return len(self.faces)

    @property
    def best_quality(self) -> float:
        return max((f.quality_score for f in self.faces), default=0.0)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


# ---------------------------------------------------------------------------
# Sesión
# ---------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class SessionKey:
    """Clave de una sesión de reconocimiento."""

    camera: CameraRef
    event_id: str

    def to_dict(self) -> dict[str, Any]:
        return {"camera": self.camera.to_dict(), "event_id": self.event_id}


class RecognitionSession:
    """Sesión incremental de reconocimiento para un evento."""

    def __init__(
        self,
        key: SessionKey,
        *,
        config: SessionConfig | None = None,
        gallery: GalleryMatcher | None = None,
    ):
        self.key = key
        self.config = config or DEFAULT_SESSION_CONFIG
        self.gallery = gallery or NullGallery()
        self.created_at = time.time()
        self.updated_at = self.created_at
        self._results: list[UnitResult] = []
        self._faces: list[FaceDetection] = []
        self._seen: set[tuple[Any, ...]] = set()
        self._closed = False
        self._clusters: list[_Cluster] = []
        self._dirty = True

    # -- estado ---------------------------------------------------------

    @property
    def is_closed(self) -> bool:
        return self._closed

    def close(self) -> None:
        self._closed = True

    def add(self, result: UnitResult) -> int:
        """Añade una unidad. Devuelve cuántas caras nuevas se incorporaron.

        Acepta unidades fuera de orden y descarta duplicados por
        (frame_idx, bbox redondeado).
        """
        if self._closed:
            raise RuntimeError("No se puede añadir resultados a una sesión cerrada")
        self._results.append(result)
        added = 0
        for face in result.faces:
            key = (
                int(face.frame_idx),
                round(float(face.bbox.x1), 1),
                round(float(face.bbox.y1), 1),
                round(float(face.bbox.x2), 1),
                round(float(face.bbox.y2), 1),
            )
            if key in self._seen:
                continue
            self._seen.add(key)
            self._faces.append(face)
            added += 1
        if added:
            self._faces.sort(key=lambda f: (f.frame_ts, f.frame_idx))
            self._dirty = True
        self.updated_at = time.time()
        return added

    # -- agrupación -----------------------------------------------------

    def _rebuild_clusters(self) -> None:
        clusters: list[_Cluster] = []
        for face in self._faces:
            target: _Cluster | None = None
            if face.embedding:
                best_sim = -1.0
                for cluster in clusters:
                    centroid = cluster.centroid
                    if centroid is None:
                        continue
                    sim = _cosine(face.embedding, centroid)
                    if sim >= self.config.cluster_cosine and sim > best_sim:
                        best_sim = sim
                        target = cluster
            if target is None:
                target = _Cluster(
                    cluster_id=f"c{len(clusters)}",
                )
                clusters.append(target)
            target.add(face)
        self._clusters = clusters
        self._dirty = False

    @property
    def clusters(self) -> list[_Cluster]:
        if self._dirty:
            self._rebuild_clusters()
        return self._clusters

    # -- resultados -----------------------------------------------------

    def _last_result(self) -> UnitResult:
        return max(self._results, key=lambda r: r.generated_at)

    def _candidates(self, *, confirm: bool) -> list[RecognitionCandidate]:
        clusters = [
            c for c in self.clusters
            if c.size >= self.config.early_min_faces
        ]
        centroids = [c.centroid for c in clusters]
        # Si la galería soporta lotes, se consulta todo de una vez (una sola
        # multiplicación de matrices). El resultado es idéntico al individual.
        matches: list = [None] * len(clusters)
        pairs = [(i, c) for i, c in enumerate(centroids) if c]
        if pairs:
            batch_fn = getattr(self.gallery, "match_batch", None)
            if callable(batch_fn):
                results = batch_fn([c for _i, c in pairs])
                for (i, _c), r in zip(pairs, results):
                    matches[i] = r
            else:
                for i, c in pairs:
                    matches[i] = self.gallery.match(c)

        candidates: list[RecognitionCandidate] = []
        for cluster, match in zip(clusters, matches):
            score = 0.0
            person_id = None
            label = None
            method = "cluster"
            if match is not None:
                score = float(match.score)
                person_id = match.person_id
                label = match.label
                method = match.method
            confirmed = False
            if confirm and match is not None and person_id is not None:
                confirmed = (
                    score >= self.config.match_min_score
                    and match.margin >= self.config.match_min_margin
                    and cluster.size >= self.config.min_faces_confirm
                    and cluster.best_quality >= self.config.min_quality_confirm
                )
            candidates.append(
                RecognitionCandidate(
                    candidate_id=f"{self.key.event_id}:{cluster.cluster_id}",
                    person_id=person_id,
                    person_label=label,
                    score=score,
                    method=method,
                    is_confirmed=confirmed,
                )
            )
        return candidates

    def early_result(self) -> UnitResult | None:
        """Mejor hipótesis provisional (nunca confirmada)."""
        if not self._results:
            return None
        last = self._last_result()
        candidates = self._candidates(confirm=False)
        return UnitResult(
            unit_id=f"session:{self.key.event_id}:early",
            instance=last.instance,
            trace_id=last.trace_id,
            kind=ResultKind.TEMPRANO,
            generated_at=time.time(),
            faces=list(self._faces),
            bodies=[],
            candidates=candidates,
            artifacts={},
            event_id=self.key.event_id,
            local_id=self.key.camera.local_id,
            camera_id=self.key.camera.camera_id,
            metrics={
                "units": len(self._results),
                "faces": len(self._faces),
                "clusters": len(self.clusters),
            },
        )

    def final_result(self) -> UnitResult | None:
        """Resultado final tras cerrar la sesión."""
        if not self._closed or not self._results:
            return None
        last = self._last_result()
        candidates = self._candidates(confirm=True)
        return UnitResult(
            unit_id=f"session:{self.key.event_id}:final",
            instance=last.instance,
            trace_id=last.trace_id,
            kind=ResultKind.FINAL,
            generated_at=time.time(),
            faces=list(self._faces),
            bodies=[],
            candidates=candidates,
            artifacts={},
            event_id=self.key.event_id,
            local_id=self.key.camera.local_id,
            camera_id=self.key.camera.camera_id,
            metrics={
                "units": len(self._results),
                "faces": len(self._faces),
                "clusters": len(self.clusters),
                "confirmed": sum(1 for c in candidates if c.is_confirmed),
            },
        )

    # -- diagnóstico ----------------------------------------------------

    def stats(self) -> dict[str, Any]:
        return {
            "event_id": self.key.event_id,
            "camera": self.key.camera.camera_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "closed": self._closed,
            "units": len(self._results),
            "faces": len(self._faces),
            "clusters": len(self.clusters),
            "confirmed": sum(1 for c in self._candidates(confirm=True) if c.is_confirmed),
        }

    def age_s(self) -> float:
        return max(0.0, time.time() - self.updated_at)


# ---------------------------------------------------------------------------
# Almacén de sesiones
# ---------------------------------------------------------------------------


class SessionStore:
    """Almacén de sesiones de reconocimiento por evento."""

    def __init__(self):
        self._sessions: dict[SessionKey, RecognitionSession] = {}

    def get_or_create(
        self,
        key: SessionKey,
        *,
        config: SessionConfig | None = None,
        gallery: GalleryMatcher | None = None,
    ) -> RecognitionSession:
        session = self._sessions.get(key)
        if session is None:
            session = RecognitionSession(key, config=config, gallery=gallery)
            self._sessions[key] = session
        return session

    def get(self, key: SessionKey) -> RecognitionSession | None:
        return self._sessions.get(key)

    def close(self, key: SessionKey) -> RecognitionSession | None:
        session = self._sessions.get(key)
        if session:
            session.close()
        return session

    def remove(self, key: SessionKey) -> None:
        self._sessions.pop(key, None)

    def keys(self) -> list[SessionKey]:
        return list(self._sessions.keys())

    def all_stats(self) -> dict[str, dict[str, Any]]:
        return {
            f"{k.camera.camera_id}:{k.event_id}": v.stats()
            for k, v in self._sessions.items()
        }
