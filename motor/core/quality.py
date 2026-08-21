"""Métricas de calidad: enfoque (Laplaciano) y pose."""
from __future__ import annotations

import cv2
import numpy as np

from .model import Face


def laplacian_variance(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def face_sharpness(img: np.ndarray, face: Face, pad: int = 0) -> float:
    """Varianza del Laplaciano sobre el recorte de la cara (más alto = más enfocada)."""
    x1, y1, x2, y2 = face.bbox
    h, w = img.shape[:2]
    x1 = max(0, x1 - pad)
    y1 = max(0, y1 - pad)
    x2 = min(w, x2 + pad)
    y2 = min(h, y2 + pad)
    crop = img[y1:y2, x1:x2]
    if crop.size == 0:
        return 0.0
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return laplacian_variance(gray)


def is_focused(face: Face, img: np.ndarray, min_sharpness: float) -> bool:
    return face_sharpness(img, face) >= min_sharpness


def is_frontal(face: Face, yaw_tol: float = 35.0, pitch_tol: float = 25.0) -> bool:
    return abs(face.yaw) <= yaw_tol and abs(face.pitch) <= pitch_tol


def pose_label(face: Face, yaw_frontal: float = 15.0, yaw_45: float = 22.5,
               yaw_90: float = 67.5, pitch_frontal: float = 20.0) -> str:
    """Etiqueta de pose a partir de yaw/pitch. Los signos se calibran en pruebas reales.

    Las bandas son CONTIGUAS (fix 2026-08-21): la frontera de m45 usa `yaw_frontal`
    (15°) en vez de `yaw_45` (22.5°), eliminando el hueco 15-22.5° que devolvía
    "other" para un giro suave de cabeza. "other" queda como red de seguridad para
    pose degenerada (y pose_compatible la trata como ambigua: nunca descarta).
    """
    yaw, pitch, _ = face.pose
    if abs(pitch) <= pitch_frontal and abs(yaw) <= yaw_frontal:
        return "f"
    if yaw > yaw_90:
        return "pi"       # perfil (calibrar lado)
    if yaw < -yaw_90:
        return "pd"
    if yaw > yaw_frontal:
        return "m45i"
    if yaw < -yaw_frontal:
        return "m45d"
    if pitch < -pitch_frontal:
        return "arr"
    if pitch > pitch_frontal:
        return "aba"
    return "other"
