"""Capa de apariencia (L1b): torso/ropa por color y textura.

Descriptor del crop de torso:
  - histograma HSV normalizado (H 32 bins, S 32, V 32) -> 96 dims
  - layout de color en grilla 4x4 (medias H/S/V por celda) -> 48 dims
  total 144 dims (L2-normalizado).

Similitud (0..1):
  0.5 * intersección de histogramas  +  0.5 * (1 - L1 normalizado de la grilla)

Confianza de instancia:
  c_torso = visibilidad (1 si hay crop válido) * frescura TTL
            (1.0 hoy -> 0.0 tras torso_ttl_days días; lineal)

Regla de la fusión: si no hay crop de torso (persona muy cerca o de cara a
cámara sin cuerpo visible), la capa queda SIN señal (available=False, c=0) y
su peso se redistribuye automáticamente en la fusión.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import cv2
import numpy as np

GRID = (4, 4)


@dataclass
class Appearance:
    desc: np.ndarray            # descriptor 144-d
    ts: float = 0.0             # epoch de captura (para la frescura TTL)
    src: str = ""               # path del crop (traza/depuración)


def torso_descriptor(img: np.ndarray, bbox: tuple[int, int, int, int]) -> np.ndarray:
    """Descriptor del crop de torso contenido en `bbox` de `img`."""
    x1, y1, x2, y2 = bbox
    h, w = img.shape[:2]
    x1, y1 = max(0, int(x1)), max(0, int(y1))
    x2, y2 = min(w, int(x2)), min(h, int(y2))
    if x2 - x1 < 8 or y2 - y1 < 8:
        return np.zeros(144, dtype=np.float32)
    crop = img[y1:y2, x1:x2]
    crop = cv2.resize(crop, (64, 128), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    # 1) histograma HSV normalizado (suma = 1: la intersección queda en 0..1)
    hist_h = cv2.calcHist([hsv], [0], None, [32], [0, 180])
    hist_s = cv2.calcHist([hsv], [1], None, [32], [0, 256])
    hist_v = cv2.calcHist([hsv], [2], None, [32], [0, 256])
    hist = np.concatenate([hist_h, hist_s, hist_v]).ravel().astype(np.float32)
    s = hist.sum()
    if s > 0:
        hist /= s

    # 2) layout de color en grilla (medias H/S/V por celda, 0..1 por canal)
    gh, gw = GRID
    small = cv2.resize(hsv, (gw, gh), interpolation=cv2.INTER_AREA)
    grid = small.reshape(gh * gw, 3).astype(np.float32) / np.array([180.0, 256.0, 256.0])
    grid = grid.ravel()

    # NOTA: NO se L2-normaliza el vector completo: la normalización conjunta
    # aplastaba el histograma (suma 1) frente a la grilla y dejaba la similitud
    # dominada solo por el layout. Cada bloque mantiene su propia escala, que es
    # la que usa appearance_similarity (intersección para hist, L1 para grid).
    return np.concatenate([hist, grid]).astype(np.float32)


def _hist_intersection(a: np.ndarray, b: np.ndarray) -> float:
    """Intersección de histogramas con suavizado (robusto a deriva de bin).

    Los histogramas de colores sólidos son picos: sin suavizar, un cambio de 2
    unidades en el color mueve el pico de bin y la intersección cae a 0.
    Un blur 1D de 5 taps reparte la masa y la intersección refleja la cercanía.
    """
    def _smooth(h):
        h = h.reshape(96, 1).astype(np.float32)
        return cv2.GaussianBlur(h, (1, 5), 1.0).ravel()
    return float(np.minimum(_smooth(a), _smooth(b)).sum())


def appearance_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Similitud 0..1 entre dos descriptores de torso."""
    if a is None or b is None or a.size == 0 or b.size == 0:
        return 0.0
    if a.shape != b.shape:
        return 0.0
    hist_a, grid_a = a[:96], a[96:]
    hist_b, grid_b = b[:96], b[96:]
    sim_hist = _hist_intersection(hist_a, hist_b)          # 0..1
    sim_grid = 1.0 - float(np.abs(grid_a - grid_b).sum()) / 2.0   # 0..1
    return float(np.clip(0.5 * sim_hist + 0.5 * sim_grid, 0.0, 1.0))


def freshness(ts: float, now: float | None = None, ttl_days: float = 30.0) -> float:
    """Frescura TTL: 1.0 recién capturado -> 0.0 tras ttl_days días (lineal)."""
    now = now if now is not None else time.time()
    if ttl_days <= 0:
        return 1.0
    age_days = max(0.0, (now - ts) / 86400.0)
    return float(np.clip(1.0 - age_days / ttl_days, 0.0, 1.0))


def layer_score(query_desc: np.ndarray,
                gallery: list[Appearance],
                now: float | None = None,
                ttl_days: float = 30.0) -> tuple[float, float, bool]:
    """(s_torso, c_torso, available) de la capa L1b.

    s_torso = mejor similitud contra la galería de la persona candidata.
    c_torso = visibilidad * frescura de la mejor coincidencia.
    available = hay query y galería no vacía.
    """
    if query_desc is None or query_desc.size == 0 or not gallery:
        return 0.0, 0.0, False
    now = now if now is not None else time.time()
    best_s, best_f = 0.0, 0.0
    for g in gallery:
        s = appearance_similarity(query_desc, g.desc)
        f = freshness(g.ts, now, ttl_days)
        # la confianza combina similitud y frescura de ESA coincidencia
        c = s * f
        if c > best_s * best_f or (s > best_s and f >= best_f):
            if s * f > best_s * best_f:
                best_s, best_f = s, f
    c = best_s * best_f
    return float(best_s), float(c), True
