"""Modelo de visión: singleton de InsightFace (buffalo_l) + dataclass Face.

Carga una sola instancia de FaceAnalysis (RetinaFace det_10g + ArcFace w600k_r50)
y expone `analyze(img)` -> list[Face].
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Optional

import numpy as np

_lock = threading.Lock()
_app = None


@dataclass
class Face:
    bbox: tuple[int, int, int, int]          # x1, y1, x2, y2
    det_score: float
    embedding: np.ndarray                    # 512-d, L2-normalizado
    pose: tuple[float, float, float]         # (yaw, pitch, roll) en grados
    landmarks: Optional[np.ndarray] = None   # (106, 2) si está disponible

    @property
    def yaw(self) -> float:
        return self.pose[0]

    @property
    def pitch(self) -> float:
        return self.pose[1]

    @property
    def roll(self) -> float:
        return self.pose[2]


def _build_app(det_size: tuple[int, int]):
    from insightface.app import FaceAnalysis

    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=det_size)
    return app


def get_app(det_size: tuple[int, int] = (640, 640)):
    global _app
    if _app is None:
        with _lock:
            if _app is None:
                _app = _build_app(det_size)
    return _app


def _to_face(f) -> Face:
    bbox = tuple(int(round(float(v))) for v in f.bbox)
    emb = np.asarray(f.normed_embedding, dtype=np.float32)
    pose = tuple(float(v) for v in f.pose)
    lm = None
    try:
        if getattr(f, "landmark_2d_106", None) is not None:
            lm = np.asarray(f.landmark_2d_106, dtype=np.float32)
    except Exception:
        lm = None
    return Face(bbox=bbox, det_score=float(f.det_score), embedding=emb, pose=pose, landmarks=lm)


def analyze(img: np.ndarray, det_size: tuple[int, int] = (640, 640), min_score: float = 0.5) -> list[Face]:
    """Detecta caras y devuelve sus embeddings normalizados (una sola pasada)."""
    app = get_app(det_size)
    faces = app.get(img)
    return [_to_face(f) for f in faces if float(f.det_score) >= min_score]
