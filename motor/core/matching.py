"""Matching por mejor coincidencia coseno (multi-plantilla)."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import Config
from .store import FaceStore


@dataclass
class MatchResult:
    verdict: str                        # "match" | "uncertain" | "new"
    person: str | None = None
    best_score: float = 0.0
    second_score: float = 0.0
    scores: dict = field(default_factory=dict)


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Similitud coseno entre embeddings ya L2-normalizados (producto escalar)."""
    return float(np.dot(a, b))


def best_cosine(query: np.ndarray, gallery: np.ndarray) -> float:
    """Mejor similitud del query contra toda la galería (matriz NxD)."""
    if gallery is None or len(gallery) == 0:
        return 0.0
    return float(np.max(gallery @ query))


def scores_per_person(query: np.ndarray, store: FaceStore) -> dict[str, float]:
    return {cod: best_cosine(query, store.person_encodings(cod)) for cod in store.persons()}


def decide(scores: dict[str, float], cfg: Config) -> MatchResult:
    """Decisión ganador/segundo a partir de las similitudes por persona."""
    if not scores:
        return MatchResult(verdict="new", scores={})
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (p1, s1) = ranked[0]
    (p2, s2) = ranked[1] if len(ranked) > 1 else (None, 0.0)
    if s1 >= cfg.secure_threshold:
        return MatchResult("match", p1, s1, s2, dict(scores))
    if s1 >= cfg.match_threshold and (s1 - s2) >= cfg.margin:
        return MatchResult("match", p1, s1, s2, dict(scores))
    if s1 >= cfg.match_threshold:
        return MatchResult("uncertain", p1, s1, s2, dict(scores))
    return MatchResult("new", None, s1, s2, dict(scores))


def match_group(query_embeddings: list[np.ndarray], store: FaceStore, cfg: Config) -> MatchResult:
    """Agrega un grupo de caras (misma persona en la escena): la similitud por persona
    es el MAXIMO de la mejor coincidencia de cada cara del grupo.

    Se usa max (no media) para que una sola cara frontal y nítida del grupo no quede
    diluida por caras en pose/perfil de la misma batería; alineado con la decisión
    multi-plantilla que ya usa `best_cosine` (max)."""
    if not query_embeddings:
        return MatchResult(verdict="new", scores={})
    agg: dict[str, list[float]] = {}
    for q in query_embeddings:
        for cod, s in scores_per_person(q, store).items():
            agg.setdefault(cod, []).append(s)
    scores = {cod: float(np.max(v)) for cod, v in agg.items()}
    return decide(scores, cfg)
