"""Embedder de identidad (wrapper fino sobre el modelo compartido)."""
from __future__ import annotations

import numpy as np

from .model import Face, analyze


class Embedder:
    def __init__(self, det_size: int = 640, min_score: float = 0.5):
        self.det_size = det_size
        self.min_score = min_score

    def embed(self, img: np.ndarray) -> list[np.ndarray]:
        return [f.embedding for f in analyze(img, det_size=(self.det_size, self.det_size), min_score=self.min_score)]

    def embed_best(self, img: np.ndarray) -> np.ndarray | None:
        faces = analyze(img, det_size=(self.det_size, self.det_size), min_score=self.min_score)
        if not faces:
            return None
        return max(faces, key=lambda f: f.det_score).embedding
