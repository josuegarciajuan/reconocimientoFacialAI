#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detección de cruces de línea — motor/cruces.py

Motor puro y testeable extraído de `procesa_videosV6.py`, con correcciones:
  P1. Falsos positivos por luz: filtro de área mín/máx + ratio de aspecto + persistencia.
  P2. Duplicados: seguimiento ligero (IoU) + histéresis + ventana de dedup por línea.
  P3. Foto exacta: el evento guarda el frame del instante del cruce.
  P4. Config centralizada (dataclass), sin parámetros mágicos.

Usa `cv2.createBackgroundSubtractorMOG2` (disponible en opencv-python-headless;
el legacy usaba `cv2.bgsegm.createBackgroundSubtractorMOG` que NO está en headless).

Sin acoplamiento a BD/PHP: devuelve objetos `CrossingEvent`; la persistencia la hace
el orquestador (integración con `cruces_lineas` en Fase 4).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class Line:
    x1: float
    y1: float
    x2: float
    y2: float
    line_id: str = ""


@dataclass
class CrossingEvent:
    line_id: str
    direction: int          # 1: lado A -> lado B ; 2: lado B -> lado A (calibrar con el panel)
    x: float
    y: float
    timestamp: float
    frame: np.ndarray       # frame en el instante del cruce (para la foto)


@dataclass
class CrossingConfig:
    area_min: float = 800.0
    area_max: float = 0.9 * 640 * 480     # descarta cambios globales (flash de luz)
    aspect_min: float = 0.2
    aspect_max: float = 5.0
    min_track_frames: int = 3             # persistencia mínima del objeto (anti-parpadeo)
    track_ttl: int = 20                   # frames sin ver al objeto antes de olvidarlo
    iou_threshold: float = 0.25           # solape para asociar el mismo objeto entre frames
    hysteresis: float = 10.0              # px de distancia a la línea para considerar "cruzado"
    dedup_seconds: float = 3.0            # ventana mínima entre cruces de la misma línea
    history: int = 150
    var_threshold: float = 25.0           # MOG2 (más bajo = más sensible)
    detect_shadows: bool = False


def signed_distance(line: Line, p: tuple[float, float]) -> float:
    """Distancia perpendicular con signo (px) del punto a la línea."""
    dx = line.x2 - line.x1
    dy = line.y2 - line.y1
    length = math.hypot(dx, dy)
    if length == 0:
        return 0.0
    return (dx * (p[1] - line.y1) - dy * (p[0] - line.x1)) / length


def iou(b1, b2) -> float:
    x1, y1, w1, h1 = b1
    x2, y2, w2, h2 = b2
    ix1, iy1 = max(x1, x2), max(y1, y2)
    ix2, iy2 = min(x1 + w1, x2 + w2), min(y1 + h1, y2 + h2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    union = (w1 * h1) + (w2 * h2) - inter
    return inter / union if union > 0 else 0.0


class _Track:
    __slots__ = ("tid", "bbox", "centroid", "frames", "prev_dist", "armed", "stale")

    def __init__(self, tid, bbox, centroid):
        self.tid = tid
        self.bbox = bbox
        self.centroid = centroid
        self.frames = 1
        self.prev_dist = 0.0
        self.armed = True
        self.stale = 0


class CrossingDetector:
    def __init__(self, line: Line, cfg: CrossingConfig | None = None):
        self.line = line
        self.cfg = cfg or CrossingConfig()
        self.fgbg = cv2.createBackgroundSubtractorMOG2(
            history=self.cfg.history,
            varThreshold=self.cfg.var_threshold,
            detectShadows=self.cfg.detect_shadows,
        )
        self.kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        self.tracks: list[_Track] = []
        self._next_id = 0
        self._last_cross_time: dict[str, float] = {}

    def process(self, frame: np.ndarray, timestamp: float) -> list[CrossingEvent]:
        """Procesa un frame y devuelve los cruces detectados (normalmente 0 o 1)."""
        fg = self.fgbg.apply(frame)
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, self.kernel)
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, self.kernel)
        fg = cv2.dilate(fg, None, iterations=2)

        contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        cands = []  # (bbox, centroid)
        for c in contours:
            area = cv2.contourArea(c)
            if area < self.cfg.area_min or area > self.cfg.area_max:
                continue
            x, y, w, h = cv2.boundingRect(c)
            ar = h / max(1, w)
            if not (self.cfg.aspect_min <= ar <= self.cfg.aspect_max):
                continue
            cands.append(((x, y, w, h), (x + w / 2, y + h / 2)))

        # envejecer todos los tracks; se resetea al emparejar
        for t in self.tracks:
            t.stale += 1

        # emparejar por IoU (greedy)
        matched: dict[int, _Track] = {}  # índice de cand -> track
        used_tracks = set()
        for i, (bb, _) in enumerate(cands):
            best_t, best_iou = None, 0.0
            for t in self.tracks:
                if t.tid in used_tracks:
                    continue
                v = iou(t.bbox, bb)
                if v > best_iou:
                    best_iou, best_t = v, t
            if best_t is not None and best_iou >= self.cfg.iou_threshold:
                matched[i] = best_t
                used_tracks.add(best_t.tid)

        events: list[CrossingEvent] = []
        for i, t in matched.items():
            bb, centroid = cands[i]
            t.stale = 0
            t.bbox = bb
            t.frames += 1
            dist = signed_distance(self.line, centroid)
            # cruce = cambio de signo de la distancia (paso de un lado al otro)
            if t.frames >= self.cfg.min_track_frames and t.armed:
                if (t.prev_dist > 0 > dist) or (t.prev_dist < 0 < dist):
                    last = self._last_cross_time.get(self.line.line_id, -float("inf"))
                    if timestamp - last >= self.cfg.dedup_seconds:
                        direction = 1 if (t.prev_dist > 0 and dist < 0) else 2
                        events.append(CrossingEvent(
                            line_id=self.line.line_id,
                            direction=direction,
                            x=centroid[0], y=centroid[1],
                            timestamp=timestamp,
                            frame=frame.copy(),
                        ))
                        self._last_cross_time[self.line.line_id] = timestamp
                        t.armed = False
            # re-armar solo cuando el objeto se aleja claramente de la línea (anti-jitter)
            if abs(dist) > self.cfg.hysteresis:
                t.armed = True
            t.prev_dist = dist
            t.centroid = centroid

        # tracks nuevos
        for i, (bb, centroid) in enumerate(cands):
            if i not in matched:
                self.tracks.append(_Track(self._next_id, bb, centroid))
                self._next_id += 1

        # olvidar tracks obsoletos
        self.tracks = [t for t in self.tracks if t.stale <= self.cfg.track_ttl]

        return events
