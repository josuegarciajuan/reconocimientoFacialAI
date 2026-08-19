"""Avatar por persona: recorte de cabeza con fondo transparente (monigote de los Caminos).

Dado el crop 150x150 de una cara (`admin/caras_procesadas/<foto_id>.jpg`), produce
un PNG cuadrado con canal alfa donde solo se ve la cabeza: máscara elíptica
centrada con los landmarks de RetinaFace cuando están disponibles (con margen
superior para el pelo) o centrada en el crop como fallback.

La selección de la "mejor cara frontal" reutiliza `quality.is_frontal()` +
`quality.face_sharpness()` sobre las fotos candidatas de la persona.
"""
from __future__ import annotations

import os
from typing import Iterable, Optional

import cv2
import numpy as np

from .model import Face


def head_ellipse_mask(
    size: int,
    landmarks: Optional[np.ndarray] = None,
    pad_top: float = 0.12,
    pad_side: float = 0.10,
    feather: float = 0.15,
) -> np.ndarray:
    """Máscara alfa (0..1) de elipse sobre la cabeza de un crop cuadrado `size`.

    Con `landmarks` (N,2) en coordenadas del crop, la elipse se centra en su
    media (desplazada un poco hacia arriba, donde está el pelo) y sus ejes se
    derivan de la dispersión de los puntos. Sin landmarks, elipse centrada que
    cubre el crop con leve recorte lateral (los crops 150x150 ya vienen
    centrados en la cara).
    """
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    cx = cy = size / 2.0
    rx = size * (0.5 - pad_side)
    ry = size * (0.5 - pad_top)

    if landmarks is not None and len(landmarks) >= 3:
        xs = landmarks[:, 0]
        ys = landmarks[:, 1]
        cx = float(np.clip(float(xs.mean()), size * 0.15, size * 0.85))
        cy = float(np.clip(float(ys.mean()), size * 0.20, size * 0.80))
        rx = float(np.clip(float(max(xs.std(), size * 0.09)) * 2.4 + size * pad_side,
                           size * 0.35, size * 0.49))
        ry = float(np.clip(float(max(ys.std(), size * 0.10)) * 2.6 + size * pad_top,
                           size * 0.40, size * 0.52))
        cy -= size * 0.05  # sube el centro: deja margen para el pelo

    d2 = ((xx - cx) / max(rx, 1e-6)) ** 2 + ((yy - cy) / max(ry, 1e-6)) ** 2
    band = 1.0 + max(feather, 1e-6)
    alpha = np.clip((band - d2) / max(feather, 1e-6), 0.0, 1.0)
    return alpha * alpha * (3.0 - 2.0 * alpha)  # smoothstep: borde suave


def _caja_cabeza(img_shape, face: Face, pad_top=0.45, pad_lat=0.25, pad_bot=0.75):
    """Caja cuadrada (x0, y0, side) centrada en la cabeza a partir del bbox."""
    h, w = img_shape[:2]
    x1, y1, x2, y2 = face.bbox
    bw, bh = x2 - x1, y2 - y1
    if bw <= 0 or bh <= 0:
        return None
    top = max(0, int(y1 - bh * pad_top))
    bot = min(h, int(y1 + bh * pad_bot))
    left = max(0, int(x1 - bw * pad_lat))
    right = min(w, int(x2 + bw * pad_lat))
    ch, cw = bot - top, right - left
    if ch <= 0 or cw <= 0:
        return None
    side = max(ch, cw)
    cx0, cy0 = (left + right) // 2, (top + bot) // 2
    x0 = max(0, min(w - side, cx0 - side // 2))
    y0 = max(0, min(h - side, cy0 - side // 2))
    return x0, y0, side


def crop_head_png(img_bgr: np.ndarray, face: Optional[Face] = None, out_size: int = 96) -> np.ndarray:
    """Recorte cuadrado de la cabeza con fondo transparente (BGRA, `out_size`x`out_size`).

    Si `face` trae landmarks (106 o 5 kps) se usan para la máscara; si no, se
    aplica la elipse centrada sobre el crop.
    """
    if img_bgr is None or img_bgr.size == 0:
        return None
    h, w = img_bgr.shape[:2]
    if h <= 0 or w <= 0:
        return None

    if face is not None and (face.bbox[2] - face.bbox[0]) > 0 and (face.bbox[3] - face.bbox[1]) > 0:
        caja = _caja_cabeza(img_bgr.shape, face)
        if caja is None:
            return None
        x0, y0, side = caja
        crop = img_bgr[y0:y0 + side, x0:x0 + side]
        lm = getattr(face, "landmarks", None)
    else:
        size = min(h, w)
        x0, y0 = (w - size) // 2, (h - size) // 2
        crop = img_bgr[y0:y0 + size, x0:x0 + size]
        lm = None

    side = crop.shape[0]
    if side <= 0:
        return None
    mask = head_ellipse_mask(side, landmarks=lm)
    bgra = cv2.cvtColor(crop, cv2.COLOR_BGR2BGRA)
    bgra[:, :, 3] = (mask * 255.0).astype(np.uint8)
    return cv2.resize(bgra, (out_size, out_size), interpolation=cv2.INTER_AREA)


def _puntua_crop(img_bgr: np.ndarray, det_size=(640, 640), min_score: float = 0.5) -> float:
    """Puntuación 0..1 de un crop: frontalidad * nitidez; fallback por nitidez pura."""
    from .quality import face_sharpness, is_frontal
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    var = cv2.Laplacian(gray, cv2.CV_64F).var()
    nitidez = float(np.clip(var / 200.0, 0.0, 1.0))  # normalización empírica
    try:
        from .model import analyze
        faces = analyze(img_bgr, det_size=det_size, min_score=min_score)
        if not faces:
            return 0.5 * nitidez          # pose desconocida: peso neutro
        f = max(faces, key=lambda f: f.det_score)
        frontal = 1.0 if is_frontal(f) else 0.4
        return float(np.clip(frontal * nitidez + 0.15 * frontal, 0.0, 1.0))
    except Exception:
        return 0.5 * nitidez


def best_frontal(fotos: Iterable[tuple[int, str]], det_size=(640, 640), min_score: float = 0.5) -> Optional[int]:
    """Elige la foto con mejor cara frontal+nítida entre [(id, ruta_jpg), ...].

    Devuelve el `id` ganador o None si ninguna foto es legible.
    """
    mejor_id: Optional[int] = None
    mejor_score = -1.0
    for fid, path in fotos:
        try:
            img = cv2.imread(str(path))
            if img is None or img.size == 0:
                continue
        except Exception:
            continue
        score = _puntua_crop(img, det_size=det_size, min_score=min_score)
        if score > mejor_score:
            mejor_score = score
            mejor_id = fid
    return mejor_id


def generar_avatar(foto_id: int, src_jpg: str, out_png: str, out_size: int = 96) -> Optional[str]:
    """Genera el PNG del avatar para una foto concreta. Devuelve la ruta o None."""
    img = cv2.imread(src_jpg)
    if img is None or img.size == 0:
        return None
    bgra = crop_head_png(img, face=None, out_size=out_size)
    if bgra is None:
        return None
    os.makedirs(os.path.dirname(os.path.abspath(out_png)), exist_ok=True)
    ok = cv2.imwrite(out_png, bgra)
    return out_png if ok else None
