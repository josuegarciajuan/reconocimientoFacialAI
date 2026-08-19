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
_apps: dict[tuple[int, int], object] = {}


@dataclass
class Face:
    bbox: tuple[int, int, int, int]          # x1, y1, x2, y2
    det_score: float
    embedding: np.ndarray                    # 512-d, L2-normalizado
    pose: tuple[float, float, float]         # (yaw, pitch, roll) en grados
    landmarks: Optional[np.ndarray] = None   # (106, 2) si está disponible
    kps: Optional[np.ndarray] = None         # (5, 2) landmarks de detección (para re-embedding SR)

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
    """FaceAnalysis cacheado POR det_size (una instancia por tamaño de detección).

    El coste de detección depende del det_size: los frames completos de cámara
    (1080p) se analizan con `Config.det_size` (1280) y los crops pequeños de
    cara con `Config.crop_det_size` (640), sin que un proceso cargue dos apps
    a no ser que realmente use ambos tamaños.
    """
    global _apps
    key = tuple(det_size)
    app = _apps.get(key)
    if app is not None:
        return app
    with _lock:
        if key not in _apps:
            _apps[key] = _build_app(det_size)
        return _apps[key]


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
    kps = None
    try:
        if getattr(f, "kps", None) is not None:
            kps = np.asarray(f.kps, dtype=np.float32)
    except Exception:
        kps = None
    return Face(bbox=bbox, det_score=float(f.det_score), embedding=emb, pose=pose,
                landmarks=lm, kps=kps)


def analyze(img: np.ndarray, det_size: tuple[int, int] = (640, 640), min_score: float = 0.5) -> list[Face]:
    """Detecta caras y devuelve sus embeddings normalizados (una sola pasada)."""
    app = get_app(det_size)
    faces = app.get(img)
    return [_to_face(f) for f in faces if float(f.det_score) >= min_score]


def reembed_face(img: np.ndarray, kps: np.ndarray) -> np.ndarray | None:
    """Embedding ArcFace sobre `img` alineando con los 5 landmarks `kps`.

    Usado por SR-before-embedding (superres.enhance_embedding): el recorte ya
    super-resuelto se pasa al modelo de RECONOCIMIENTO directamente (sin volver
    a detectar, que es donde el SR de Real-ESRGAN confundía a RetinaFace) con
    los keypoints escalados del crop original. Devuelve el embedding L2-
    normalizado, o None si no hay modelo de reconocimiento disponible.
    """
    app = get_app()
    rec = app.models.get("recognition")
    if rec is None:
        return None
    try:
        from insightface.app.common import Face as IFace
        f = IFace()
        f.kps = np.asarray(kps, dtype=np.float32)
        emb = rec.get(img, f)
        emb = np.asarray(emb, dtype=np.float32).flatten()
        n = float(np.linalg.norm(emb))
        if n < 1e-9:
            return None
        return emb / n
    except Exception:  # noqa: BLE001
        return None
