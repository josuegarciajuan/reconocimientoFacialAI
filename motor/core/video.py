"""Compresión y almacenamiento de vídeos de movimiento — motor/core/video.py

Módulo genérico y reutilizable para los vídeos de movimiento:

  - `comprimir_video()`: transcodifica un AVI bruto (XVID, enorme) a MP4 H.264 con
    CRF (calidad constante) + faststart (reproducción progresiva en el navegador).
  - `remux_video()`:     reencapsula un MP4 sin recodificar (stream copy) y mueve
    moov al inicio; usado cuando la captura ya es H.264 (archiva_video.py).
  - `guardar_video()`:   escribe una secuencia de frames directamente a MP4 H.264,
    sin pasar por un AVI intermedio (para capturas futuras).
  - `H264VideoWriter`:   escritor MP4 H.264 por streaming (sin retener frames en
    RAM); lo usa `guarda_movimientosV3.py` para capturar pre-roll + vivo + post-roll.
  - `extraer_poster()`:  extrae un frame del vídeo a un JPG de miniatura (UI).
  - `duracion_video()`:  duración en segundos (metadatos para la tabla `videos`).
  - `ruta_video()`:      valida una ruta relativa de la BD contra el árbol de archivo
    (anti path-traversal) y devuelve la ruta absoluta.

Reglas:
- Sin acoplamiento a BD/PHP: la persistencia (tabla `videos`) la hace el orquestador
  (`motor/archiva_video.py`), igual que `cruces.py` no toca BD.
- Codificación vía `ffmpeg` del sistema (libx264): el build headless de OpenCV no
  incluye encoder H.264 (comprobado: `avc1` no abre, `mp4v` sí pero es MPEG-4 legacy).
- `-r <fps>` remuestrea timestamps conservando la duración: el vídeo archivado se ve
  a velocidad natural (ni cámara lenta ni rápida) aunque baje de fps.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass

import cv2
import numpy as np

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
ARCHIVO_DIR = os.path.join("motor", "videos_archivo")  # relativo a la raíz del proyecto


@dataclass
class VideoConfig:
    """Parámetros de compresión. CRF constante = calidad perceptiva estable
    (las escenas estáticas pesan casi nada), preset más lento = fichero menor."""
    crf: int = 26            # 18 ≈ casi sin pérdida ... 30 ≈ compresión fuerte
    preset: str = "medium"   # ultrafast..veryslow (más lento -> más pequeño)
    fps: int = 10            # fps del archivo (conserva la duración)
    gop: int = 20            # intervalo de keyframes (~2 s a 10 fps)
    codec: str = "libx264"
    scale: str | None = None  # p. ej. "960:-2"; None = resolución original
    audio: bool = False       # las cámaras no traen audio; -an ahorra espacio


def _cmd_base(cfg: VideoConfig) -> list[str]:
    cmd = ["-c:v", cfg.codec, "-crf", str(cfg.crf), "-preset", cfg.preset,
           "-g", str(cfg.gop)]
    if cfg.scale:
        cmd += ["-vf", f"scale={cfg.scale}"]
    if not cfg.audio:
        cmd += ["-an"]
    return cmd


def comprimir_video(src: str, dst: str, cfg: VideoConfig | None = None,
                    timeout: int = 600) -> int | None:
    """Transcodifica `src` (AVI/MP4/lo que sea) a MP4 H.264 mínimo peso.

    Devuelve el tamaño en bytes del MP4 generado, o None si falla.
    """
    cfg = cfg or VideoConfig()
    if not os.path.exists(src):
        return None
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    cmd = [FFMPEG, "-y", "-i", src, "-r", str(cfg.fps)] + _cmd_base(cfg) + ["-movflags", "+faststart", dst]
    try:
        subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
    except Exception:
        return None
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return os.path.getsize(dst)
    return None


def remux_video(src: str, dst: str, timeout: int = 300) -> int | None:
    """Reencapsula un MP4 sin recodificar (stream copy) y mueve moov al inicio.

    Cuando la captura ya escribe H.264 directamente (guarda_movimientosV3.py),
    archivar no necesita transcodificar: copiar los streams basta y es muy rápido.
    Devuelve el tamaño en bytes del MP4 generado, o None si falla.
    """
    if not os.path.exists(src):
        return None
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    cmd = [FFMPEG, "-y", "-i", src, "-c", "copy", "-movflags", "+faststart", dst]
    try:
        subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
    except Exception:
        return None
    if os.path.exists(dst) and os.path.getsize(dst) > 0:
        return os.path.getsize(dst)
    return None


def guardar_video(frames: list[np.ndarray], dst: str, fps: int, size: tuple[int, int],
                  cfg: VideoConfig | None = None, timeout: int = 600) -> int | None:
    """Escribe una secuencia de frames BGR a MP4 H.264 (sin AVI intermedio).

    Devuelve el tamaño en bytes del MP4 generado, o None si falla.
    """
    cfg = cfg or VideoConfig()
    if not frames or size[0] <= 0 or size[1] <= 0:
        return None
    w = H264VideoWriter(dst, size, fps, cfg)
    for f in frames:
        w.write(f)
    return w.close(timeout=timeout)


class H264VideoWriter:
    """Escritor MP4 H.264 por streaming (sin AVI intermedio ni lista en RAM).

    Abre un ffmpeg con rawvideo por stdin y escribe frames BGR uno a uno; el
    encoder los comprime al vuelo (CRF) y cierra con `-movflags +faststart`.
    Sustituye al `cv2.VideoWriter(XVID)` de `guarda_movimientosV3.py`: permite
    volcar el pre-roll, el vivo y el post-roll en orden, en un único proceso y
    sin hilos concurrentes escribiendo al mismo destino.

    Uso:
        w = H264VideoWriter(dst, size, fps, cfg)
        for f in frames:
            w.write(f)
        peso = w.close()   # None si falla (idempotente)
    """

    def __init__(self, dst: str, size: tuple[int, int], fps: int,
                 cfg: VideoConfig | None = None):
        cfg = cfg or VideoConfig()
        if size[0] <= 0 or size[1] <= 0:
            raise ValueError("size inválido")
        self.dst = dst
        self._proc = None
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        cmd = [FFMPEG, "-y", "-f", "rawvideo", "-pix_fmt", "bgr24",
               "-s", f"{size[0]}x{size[1]}", "-r", str(fps), "-i", "-",
               "-r", str(cfg.fps)] + _cmd_base(cfg) + ["-movflags", "+faststart", dst]
        try:
            self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE,
                                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            self._proc = None

    def write(self, frame) -> None:
        """Encola un frame BGR para el encoder. No-op si el proceso falló."""
        if self._proc is None or frame is None:
            return
        try:
            self._proc.stdin.write(np.ascontiguousarray(frame).tobytes())
        except Exception:
            pass

    def close(self, timeout: int = 600) -> int | None:
        """Cierra el encoder y devuelve el tamaño del MP4 (None si falla). Idempotente."""
        if self._proc is None:
            return None
        proc, self._proc = self._proc, None
        try:
            proc.stdin.close()
        except Exception:
            pass
        try:
            proc.wait(timeout=timeout)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
            return None
        # Si ffmpeg salió con error, el MP4 está truncado (sin moov atom): devolver
        # None para que guarda_movimientosV3.py DESCARTE el .tmp en vez de renombrarlo
        # a .mp4 (antes se publicaba igual y archiva_video fallaba en bucle con
        # "moov atom not found").
        if proc.returncode != 0:
            return None
        if os.path.exists(self.dst) and os.path.getsize(self.dst) > 0:
            return os.path.getsize(self.dst)
        return None


def extraer_poster(src: str, dst_jpg: str, at: float = 0.0, timeout: int = 60) -> bool:
    """Extrae un frame del vídeo (por defecto el primero) a un JPG de miniatura.

    Devuelve True si el JPG se generó y pesa > 0 bytes.
    """
    if not os.path.exists(src):
        return False
    os.makedirs(os.path.dirname(dst_jpg), exist_ok=True)
    cmd = [FFMPEG, "-y", "-ss", f"{at:.3f}", "-i", src, "-frames:v", "1",
           "-q:v", "3", dst_jpg]
    try:
        subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
    except Exception:
        return False
    return os.path.exists(dst_jpg) and os.path.getsize(dst_jpg) > 0


def duracion_video(path: str) -> float:
    """Duración en segundos (redondeada a centésimas). 0.0 si no se puede leer."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return 0.0
    fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
    n = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    cap.release()
    if fps <= 0 or n <= 0:
        return 0.0
    return round(n / fps, 2)


def dimensiones_video(path: str) -> tuple[int, int]:
    """(ancho, alto) del vídeo; (0, 0) si no se puede leer."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return (0, 0)
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    return (w, h)


def dir_archivo(base: str, local_id, camara_id) -> str:
    """Directorio de archivo `base/motor/videos_archivo/<local>/<cam>` (lo crea)."""
    d = os.path.join(base, ARCHIVO_DIR, str(local_id), str(camara_id))
    os.makedirs(d, exist_ok=True)
    return d


def ruta_archivo(base: str, local_id, camara_id, nombre: str) -> str:
    """Ruta absoluta del MP4 archivado (no valida el nombre; usa basename en llamadas)."""
    return os.path.join(dir_archivo(base, local_id, camara_id), nombre)


def ruta_video(ruta_relativa: str, base: str) -> str | None:
    """Valida una ruta relativa (p. ej. la columna `ruta` de la BD) contra el árbol
    `motor/videos_archivo/` y devuelve su ruta absoluta. None si escapa del árbol."""
    root = os.path.abspath(os.path.join(base, ARCHIVO_DIR))
    abs_path = os.path.abspath(os.path.join(base, str(ruta_relativa)))
    if abs_path != root and not abs_path.startswith(root + os.sep):
        return None
    return abs_path
