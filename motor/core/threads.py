"""Límite de hilos de CPU del motor — anti-sobresuscripción.

El host de producción (10 cores) mantiene a la vez hasta ~10 procesos del motor
(11 guarda_movimientos, clasificador, varios procesa_video, photo_worker...).
Sin límites, cada proceso levanta pools de hilos propios:

- ONNX Runtime usa por defecto un pool *intra-op* del tamaño de cores FÍSICOS
  por cada sesión; `buffalo_l` crea 5 sesiones (det_10g, 2d106det, 1k3d68,
  genderage, w600k_r50) -> ~50 hilos por proceso. Medido en producción:
  `clasificador` 55 hilos, `procesa_video` 65 hilos, runqueue 49-50 sobre 10
  cores y ~79.000 cambios de contexto/s (CPU al 100 % con poco trabajo útil).
- OpenCV y Torch también crean sus propios pools.

Este módulo centraliza los topes, todos por variable de entorno para afinarlos
sin tocar código:

- RF_ORT_THREADS   : hilos intra-op por sesión ONNX (default 2). Lo aplica
                     `motor/core/model.py` inyectando SessionOptions, porque
                     insightface 0.7.3 no propaga `sess_options`.
- RF_CV_THREADS    : hilos internos de OpenCV (default 1). `cv2.setNumThreads`.
- RF_TORCH_THREADS : hilos de torch (default 1; rf-photo lo sube).

Ninguno de estos topes cambia el RESULTADO numérico: solo cómo se reparte el
trabajo entre hilos. La precisión (TAR/FAR) es idéntica.

`limit_threads()` es idempotente y tolerante a fallos (sin cv2/torch no rompe).
"""
from __future__ import annotations

import os


def _int_env(name: str, default: int) -> int:
    try:
        return max(1, int(os.environ.get(name, str(default))))
    except (TypeError, ValueError):
        return default


def ort_threads() -> int:
    """Hilos intra-op por sesión ONNX (RF_ORT_THREADS, default 2)."""
    return _int_env("RF_ORT_THREADS", 2)


def cv_threads() -> int:
    return _int_env("RF_CV_THREADS", 1)


def torch_threads() -> int:
    return _int_env("RF_TORCH_THREADS", 1)


def limit_threads(limit_cv: bool = True, limit_torch: bool = True) -> None:
    """Fija los topes de hilos del proceso actual (idempotente).

    Llamar al inicio del worker (main), después de los imports. Si cv2/torch no
    están instalados, se ignora ese tope sin romper el pipeline.
    """
    if limit_cv:
        try:
            import cv2

            cv2.setNumThreads(cv_threads())
        except Exception:  # noqa: BLE001
            pass
    if limit_torch:
        try:
            import torch

            torch.set_num_threads(torch_threads())
        except Exception:  # noqa: BLE001
            pass
