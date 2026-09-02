"""Matching por mejor coincidencia coseno (multi-plantilla) + capa L1a.

F2+: expone (score, confidence) por capa, matching pose-consciente (comparar
solo contra encodings de clase de pose comparable) y candidatos top-1/top-2
más la banda "podría-ser-la-misma" para la cascada de fusión (F3).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import Config
from .store import FaceStore
from .zones import pose_compatible, pose_confidence


@dataclass
class LayerScore:
    """Puntuación de una capa de la cascada: (score, confidence, available)."""
    score: float = 0.0
    confidence: float = 0.0
    available: bool = True
    reason: str = ""


@dataclass
class MatchResult:
    verdict: str                        # "match" | "uncertain" | "review" | "new"
    person: str | None = None
    best_score: float = 0.0
    second_score: float = 0.0
    scores: dict = field(default_factory=dict)
    confidence: float = 0.0             # confianza agregada de la capa cara (L1a)
    layer_scores: dict = field(default_factory=dict)   # nombre capa -> LayerScore
    candidates: list = field(default_factory=list)     # top-1, top-2 + banda


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


def scores_per_person_pose_aware(query: np.ndarray, store: FaceStore,
                                 cfg: Config, pose: str | None) -> dict[str, float]:
    """Similitudes por persona con matching pose-consciente y FALLBACK global.

    Con pose conocida, se compara SOLO contra encodings de pose comparable
    (discriminación perfil/frontal). Si una persona NO tiene NI UN encoding
    comparable, se cae al coseno GLOBAL (`best_cosine`): la galería nunca
    queda invisible en el ranking. Antes devolvía 0.0 y ocultaba a la persona
    correcta cuando la pose del query era nueva para ella (fragmentación de
    identidades, fix 2026-08-21).
    """
    out: dict[str, float] = {}
    for cod in store.persons():
        p = store.person(cod)
        if not p or not p.get("encodings"):
            continue
        encs = np.asarray(p["encodings"], dtype=np.float32)
        poses = p.get("poses") or [None] * len(encs)
        mask = np.asarray([pose_compatible(pose, po) for po in poses], dtype=bool)
        if mask.any():
            out[cod] = float(np.max(encs[mask] @ query))
        else:
            out[cod] = best_cosine(query, encs)   # fallback: no ocultar la galería
    return out


def face_confidence(s1: float, s2: float, sharpness: float, cfg: Config) -> float:
    """Confianza de instancia de la capa cara (F2+).

    Combina nitidez normalizada + margen top1-top2 + nivel absoluto del coseno.
    Sub-pesos configurables (c_w_sharp / c_w_margin / c_w_level).
    """
    sharp_n = float(np.clip(sharpness / 100.0, 0.0, 1.0)) if sharpness > 0 else 0.0
    margin_n = float(np.clip((s1 - s2) / 0.10, 0.0, 1.0))
    level_n = float(np.clip((s1 - 0.20) / 0.30, 0.0, 1.0))
    c = cfg.c_w_sharp * sharp_n + cfg.c_w_margin * margin_n + cfg.c_w_level * level_n
    return float(np.clip(c, 0.0, 1.0))


def decide(scores: dict[str, float], cfg: Config, sharpness: float = 0.0,
           pose: str | None = None, store: FaceStore | None = None) -> MatchResult:
    """Decisión ganador/segundo de la capa L1a (cara) con (score, confidence).

    Si `pose` y `store` se dan, usa el ranking pose-consciente.
    """
    if not scores:
        return MatchResult(verdict="new", scores={}, confidence=0.0)
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (p1, s1) = ranked[0]
    (p2, s2) = ranked[1] if len(ranked) > 1 else (None, 0.0)
    conf = face_confidence(s1, s2, sharpness, cfg)
    if s1 >= cfg.secure_threshold:
        return MatchResult("match", p1, s1, s2, dict(scores), confidence=conf)
    if s1 >= cfg.match_threshold and (s1 - s2) >= cfg.margin:
        return MatchResult("match", p1, s1, s2, dict(scores), confidence=conf)
    if s1 >= cfg.match_threshold:
        return MatchResult("uncertain", p1, s1, s2, dict(scores), confidence=conf)
    return MatchResult("new", None, s1, s2, dict(scores), confidence=conf)


def match_group(query_embeddings: list[np.ndarray], store: FaceStore, cfg: Config,
                sharpness: float = 0.0, pose: str | None = None) -> MatchResult:
    """Agrega un grupo de caras (misma persona en la escena): la similitud por persona
    es el MAXIMO de la mejor coincidencia de cada cara del grupo.

    Se usa max (no media) para que una sola cara frontal y nítida del grupo no quede
    diluida por caras en pose/perfil de la misma batería; alineado con la decisión
    multi-plantilla que ya usa `best_cosine` (max)."""
    if not query_embeddings:
        return MatchResult(verdict="new", scores={}, confidence=0.0)
    agg: dict[str, list[float]] = {}
    for q in query_embeddings:
        if pose is not None and store is not None:
            sp = scores_per_person_pose_aware(q, store, cfg, pose)
        else:
            sp = scores_per_person(q, store)
        for cod, s in sp.items():
            agg.setdefault(cod, []).append(s)
    scores = {cod: float(np.max(v)) for cod, v in agg.items()}
    return decide(scores, cfg, sharpness=sharpness, pose=pose, store=store)


def select_candidates(scores: dict[str, float], cfg: Config) -> list[str]:
    """Candidatos de la cascada: top-1 y top-2 SIEMPRE + cualquiera dentro de
    la banda "podría-ser-la-misma" (score >= top1 - escalate_band)."""
    if not scores:
        return []
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top1 = ranked[0][1]
    cands = [c for c, s in ranked if s >= top1 - cfg.escalate_band]
    if len(ranked) >= 2 and ranked[1][0] not in cands:
        cands.append(ranked[1][0])
    return cands


def top_scores(scores: dict[str, float], n: int = 5) -> list[dict]:
    """Top-N (persona, score) ordenado para auditoría (A1): nunca scores crudos."""
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return [{"person": cod, "score": round(float(s), 4)} for cod, s in ranked[:n]]


def exact_band_persons(embs: list[np.ndarray], store: FaceStore,
                       cos: float = 0.999) -> tuple[list[str], float]:
    """Personas con un encoding idéntico/casi idéntico a ALGÚN embedding del query.

    C5: un rostro exactamente igual al ya enrolado NO puede crear una identidad
    nueva. Devuelve (personas_en_banda_exacta, mejor_coseno). Si hay UN solo
    candidato -> match directo autónomo; si hay varios (contaminación cruzada)
    -> conflicto: el llamador crea perfil nuevo + revisión (nunca auto-fusión).
    """
    hits: dict[str, float] = {}
    for q in embs:
        qq = np.asarray(q, dtype=np.float32)
        for cod in store.persons():
            g = store.person_encodings(cod)
            if g is None or len(g) == 0:
                continue
            s = float(np.max(g @ qq))
            if s >= cos:
                hits[cod] = max(hits.get(cod, 0.0), s)
    ranked = sorted(hits.items(), key=lambda kv: kv[1], reverse=True)
    return [c for c, _ in ranked], (ranked[0][1] if ranked else 0.0)
