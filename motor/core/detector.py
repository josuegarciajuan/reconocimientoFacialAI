"""Detector de caras (wrapper fino sobre el modelo compartido)."""
from __future__ import annotations

import numpy as np

from .model import Face, analyze


class Detector:
    def __init__(self, det_size: int = 640, min_score: float = 0.5):
        self.det_size = det_size
        self.min_score = min_score

    def detect(self, img: np.ndarray) -> list[Face]:
        return analyze(img, det_size=(self.det_size, self.det_size), min_score=self.min_score)
