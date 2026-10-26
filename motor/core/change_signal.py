"""Señal de cambios y reconciliación periódica.

Permite sustituir escaneos completos de directorios/colas por notificaciones,
manteniendo una reconciliación de respaldo por tiempo para no perder eventos
si una notificación se pierde.

- ``ChangeSignal``: espera bloqueante con timeout, versionada e idempotente.
- ``PeriodicReconciler``: ejecuta un callback como mucho una vez por intervalo.
"""
from __future__ import annotations

import threading
import time
from typing import Callable


class ChangeSignal:
    """Aviso de cambio con versión y espera con timeout."""

    def __init__(self):
        self._cond = threading.Condition()
        self._version = 0
        self._closed = False

    @property
    def version(self) -> int:
        with self._cond:
            return self._version

    def notify(self) -> int:
        """Incrementa la versión y despierta a todos los que esperan."""
        with self._cond:
            self._version += 1
            self._cond.notify_all()
            return self._version

    def wait(self, timeout: float | None = None, last_version: int | None = None) -> bool:
        """Espera hasta que cambie la versión o venza el timeout.

        Devuelve True si hubo cambio (versión distinta de ``last_version``).
        """
        with self._cond:
            if last_version is not None and self._version != last_version:
                return True
            self._cond.wait(timeout=timeout)
            return last_version is None or self._version != last_version

    def wait_for_change(self, last_version: int, timeout: float | None = None) -> int:
        """Espera un cambio posterior a ``last_version`` y devuelve la versión."""
        with self._cond:
            if self._version == last_version:
                self._cond.wait(timeout=timeout)
            return self._version

    def close(self) -> None:
        with self._cond:
            self._closed = True
            self._cond.notify_all()

    @property
    def closed(self) -> bool:
        with self._cond:
            return self._closed


class PeriodicReconciler:
    """Ejecuta un callback de reconciliación como máximo una vez por intervalo."""

    def __init__(
        self,
        interval_s: float,
        callback: Callable[[], object],
        *,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.interval_s = max(0.0, float(interval_s))
        self.callback = callback
        self._clock = clock
        self._last: float | None = None
        self._runs = 0
        self._errors = 0

    def run_if_due(self, now: float | None = None) -> bool:
        """Ejecuta el callback si venció el intervalo. Devuelve True si ejecutó."""
        t = self._clock() if now is None else float(now)
        if self._last is not None and (t - self._last) < self.interval_s:
            return False
        self._last = t
        self._runs += 1
        try:
            self.callback()
        except Exception:  # noqa: BLE001 — la reconciliación no debe tumbar el bucle
            self._errors += 1
        return True

    def force(self) -> bool:
        """Ejecuta el callback ignorando el intervalo."""
        self._last = None
        return self.run_if_due()

    def stats(self) -> dict[str, float | int]:
        return {
            "interval_s": self.interval_s,
            "runs": self._runs,
            "errors": self._errors,
        }
