#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Perfil de etapas por lote (F16).

Barato y sin dependencias: los puntos calientes hacen

    _t = time.time(); <trabajo>; PROF.add("clave", time.time() - _t)

y el bucle del aplicador emite una línea JSON por lote con los ms acumulados.
Sirve para decidir QUÉ mover al pool antes de tocar el pipeline.
"""
from __future__ import annotations

import json
import os
import threading
import time


class Profiler:
    def __init__(self):
        self._acc: dict[str, float] = {}
        self._lock = threading.Lock()

    def add(self, key: str, seconds: float) -> None:
        if seconds is None:
            return
        try:
            secs = max(0.0, float(seconds))
        except (TypeError, ValueError):
            return
        with self._lock:
            self._acc[key] = self._acc.get(key, 0.0) + secs

    def reset(self) -> None:
        with self._lock:
            self._acc = {}

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return dict(self._acc)

    def emit(self, path: str | None, **fields) -> None:
        """Escribe {ts, ...fields, ms:{clave: ms}} y resetea."""
        acc = self.snapshot()
        record = {"ts": time.time(), "ms": {k: round(v * 1000.0, 1) for k, v in acc.items()}}
        record.update(fields or {})
        if path:
            try:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record, ensure_ascii=False) + "\n")
            except OSError:
                pass
        self.reset()


PROF = Profiler()
