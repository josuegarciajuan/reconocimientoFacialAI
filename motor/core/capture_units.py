"""Publicación progresiva de unidades durante la grabación.

Durante un clip de movimiento, este módulo escribe el vídeo en segmentos
cerrados (unidades) y emite un descriptor por unidad en cuanto se cierra. Así el
análisis puede empezar antes de que termine el clip.

Diseño:
- Una sola codificación: los segmentos son la fuente del análisis y, al cerrar
  el clip, se concatenan sin recodificar (`ffmpeg -c copy`) para producir el
  vídeo completo de archivo.
- Si la concatenación falla, los segmentos se conservan y el clip se marca como
  ``parcial``; nunca se publica un MP4 incompleto como si estuviera completo.
- La captura no espera respuestas: solo escribe ficheros y un descriptor JSON.

Uso:
    pub = CaptureUnitPublisher(out_dir, local_id, camera_id, size, fps, cfg,
                               unit_frames, event_id)
    for frame in frames:
        pub.write(frame)
    resumen = pub.close()          # cierra el último segmento
    pub.concat(final_path)         # vídeo completo (stream copy)
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from motor.core.video import H264VideoWriter, VideoConfig

FFMPEG = shutil.which("ffmpeg") or "ffmpeg"


@dataclass
class UnitInfo:
    """Descriptor de una unidad cerrada."""

    unit_id: str
    segment_path: str
    frame_start: int
    frame_end: int          # exclusivo
    ts_start: float
    ts_end: float
    fps: float
    local_id: str
    camera_id: str
    event_id: str
    closed_at: float = field(default_factory=time.time)

    @property
    def frame_count(self) -> int:
        return max(0, self.frame_end - self.frame_start)

    def to_dict(self) -> dict:
        return {
            "unit_id": self.unit_id,
            "segment_path": self.segment_path,
            "frame_start": self.frame_start,
            "frame_end": self.frame_end,
            "ts_start": self.ts_start,
            "ts_end": self.ts_end,
            "fps": self.fps,
            "local_id": self.local_id,
            "camera_id": self.camera_id,
            "event_id": self.event_id,
            "closed_at": self.closed_at,
            "frame_count": self.frame_count,
        }


class CaptureUnitPublisher:
    """Escribe un clip en segmentos y publica un descriptor por unidad."""

    def __init__(
        self,
        out_dir: str,
        local_id: str,
        camera_id: str,
        size: tuple[int, int],
        fps: float,
        cfg: VideoConfig | None = None,
        unit_frames: int = 300,
        event_id: str = "",
        on_unit_closed: Callable[[UnitInfo], None] | None = None,
        stderr_path: str | None = None,
        ts_base: float | None = None,
    ):
        self.out_dir = out_dir
        self.local_id = str(local_id)
        self.camera_id = str(camera_id)
        self.size = size
        self.fps = max(1.0, float(fps))
        self.cfg = cfg or VideoConfig(fps=int(round(self.fps)))
        self.unit_frames = max(1, int(unit_frames))
        self.event_id = event_id or f"{camera_id}-{int(time.time())}"
        self.on_unit_closed = on_unit_closed
        self.stderr_path = stderr_path

        os.makedirs(self.out_dir, exist_ok=True)
        self._writer: H264VideoWriter | None = None
        self._segment_path: str = ""
        self._global_frame = 0
        self._unit_start_frame = 0
        self._unit_index = 0
        self._closed = False
        self.units: list[UnitInfo] = []
        # `ts_base` permite alinear los timestamps con el inicio real del clip
        # (incluido el pre-roll) en lugar del instante de creación del objeto.
        self._ts_base = float(ts_base) if ts_base is not None else time.time()
        self._open_segment()

    # ------------------------------------------------------------------
    # Segmentos
    # ------------------------------------------------------------------
    def _segment_name(self, index: int) -> str:
        return f"{self.event_id}_u{index:06d}.mp4"

    def _open_segment(self) -> None:
        self._unit_start_frame = self._global_frame
        self._segment_path = os.path.join(
            self.out_dir, self._segment_name(self._unit_index)
        )
        tmp = self._segment_path + ".tmp"
        self._writer = H264VideoWriter(
            tmp, self.size, int(round(self.fps)), self.cfg,
            stderr_path=self.stderr_path,
        )

    def _close_segment(self) -> UnitInfo | None:
        if self._writer is None:
            return None
        writer, self._writer = self._writer, None
        size = writer.close()
        tmp = self._segment_path + ".tmp"
        if size is None:
            # Segmento corrupto: se descarta y se avanza el índice.
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            self._unit_index += 1
            return None
        try:
            os.replace(tmp, self._segment_path)
        except OSError:
            return None

        frame_end = self._global_frame
        ts_start = self._ts_base + self._unit_start_frame / self.fps
        ts_end = self._ts_base + frame_end / self.fps
        unit = UnitInfo(
            unit_id=f"{self.event_id}:u{self._unit_index:06d}",
            segment_path=self._segment_path,
            frame_start=self._unit_start_frame,
            frame_end=frame_end,
            ts_start=ts_start,
            ts_end=ts_end,
            fps=self.fps,
            local_id=self.local_id,
            camera_id=self.camera_id,
            event_id=self.event_id,
        )
        self.units.append(unit)
        self._unit_index += 1
        self._write_descriptor(unit)
        if self.on_unit_closed is not None:
            try:
                self.on_unit_closed(unit)
            except Exception:  # noqa: BLE001 — la captura nunca se rompe por el callback
                pass
        return unit

    def _write_descriptor(self, unit: UnitInfo) -> None:
        """Escribe `<segmento>.unit.json` de forma atómica."""
        path = unit.segment_path + ".unit.json"
        tmp = path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(unit.to_dict(), fh, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
        except OSError:
            pass

    # ------------------------------------------------------------------
    # Escritura
    # ------------------------------------------------------------------
    def write(self, frame: np.ndarray) -> None:
        """Escribe un frame; rota el segmento al alcanzar ``unit_frames``."""
        if self._closed or self._writer is None:
            return
        self._writer.write(frame)
        self._global_frame += 1
        if (self._global_frame - self._unit_start_frame) >= self.unit_frames:
            self._close_segment()
            if not self._closed:
                self._open_segment()

    def close(self) -> list[UnitInfo]:
        """Cierra el segmento actual y devuelve la lista de unidades."""
        if self._closed:
            return list(self.units)
        self._closed = True
        self._close_segment()
        return list(self.units)

    # ------------------------------------------------------------------
    # Concatenación
    # ------------------------------------------------------------------
    def concat(self, final_path: str, timeout: int = 600) -> bool:
        """Concatena los segmentos en ``final_path`` sin recodificar.

        Escribe a `final_path.tmp` y lo publica con rename atómico solo si ffmpeg
        termina correctamente y el fichero resultante no está vacío.
        """
        if self._writer is not None:
            self.close()
        segments = [u.segment_path for u in self.units if os.path.exists(u.segment_path)]
        if not segments:
            return False
        if len(segments) == 1:
            try:
                shutil.copy2(segments[0], final_path + ".tmp")
                os.replace(final_path + ".tmp", final_path)
                return True
            except OSError:
                return False

        list_path = os.path.join(self.out_dir, f".concat_{int(time.time())}.txt")
        try:
            with open(list_path, "w", encoding="utf-8") as fh:
                for seg in segments:
                    # El demuxer concat exige rutas escapadas con comillas simples.
                    fh.write("file '" + seg.replace("'", "'\\''") + "'\n")
            tmp_out = final_path + ".tmp"
            cmd = [
                FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", list_path,
                "-c", "copy", "-movflags", "+faststart", "-f", "mp4", tmp_out,
            ]
            r = subprocess.run(cmd, capture_output=True, timeout=timeout, check=False)
            if r.returncode != 0 or not os.path.exists(tmp_out):
                return False
            if os.path.getsize(tmp_out) <= 0:
                return False
            os.replace(tmp_out, final_path)
            return True
        except Exception:  # noqa: BLE001
            return False
        finally:
            try:
                if os.path.exists(list_path):
                    os.remove(list_path)
            except OSError:
                pass


def unit_frames_for(fps: float, seconds: float, minimum: int = 30) -> int:
    """Número de frames por unidad para una duración objetivo."""
    return max(int(minimum), int(round(max(1.0, fps) * max(1.0, seconds))))
