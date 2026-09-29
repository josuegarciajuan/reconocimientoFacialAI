"""Metadata estable para distinguir evidencia nativa de imágenes procesadas."""
from __future__ import annotations

import cv2
import numpy as np


def select_max_resolution_frame(primary, members, battery):
    """Devuelve el frame completo de mayor área entre los candidatos del grupo."""
    candidates = [primary]
    for member in members or []:
        try:
            image = battery[member[1]]["img"]
        except (IndexError, KeyError, TypeError):
            continue
        if isinstance(image, np.ndarray) and image.ndim >= 2:
            candidates.append(image)
    return max(candidates, key=lambda image: int(image.shape[0]) * int(image.shape[1]))


def build_image_metadata(original, original_bbox, processed, *, sr_applied: bool,
                         display_upscaled: bool) -> dict:
    """Build bounded, JSON-safe image provenance and quality metadata."""
    oh, ow = original.shape[:2]
    ph, pw = processed.shape[:2]
    x1, y1, x2, y2 = (int(round(v)) for v in original_bbox)
    face_w, face_h = max(0, x2 - x1), max(0, y2 - y1)
    face_side = max(face_w, face_h)
    quality = "insufficient" if face_side < 32 else "limited" if face_side < 64 else "usable"
    sharpness = float(cv2.Laplacian(cv2.cvtColor(original, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
    return {
        "original_width": int(ow), "original_height": int(oh),
        "processed_width": int(pw), "processed_height": int(ph),
        "original_face_width": int(face_w), "original_face_height": int(face_h),
        "original_sharpness": round(max(0.0, min(sharpness, 1_000_000.0)), 3),
        "quality_label": quality,
        "sr_applied": bool(sr_applied),
        "display_upscaled": bool(display_upscaled),
    }
