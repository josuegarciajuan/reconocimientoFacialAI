"""Detección de movimiento por diferencia de frames — motor/core/motion.py

Lógica pura y testeable extraída de `guarda_movimientosV3.py` (mismo patrón que
`cruces.py`): la decisión "¿hay movimiento en este frame?" y "¿dispara la
grabación?" sin acoplamiento a cámara/argv/BD. El worker de captura instancia
`MotionDetector` por cámara y lo alimenta con los frames ya redimensionados.

Reglas:
- Sin acoplamiento a BD/PHP: `guarda_movimientosV3.py` mantiene el estado de
  grabación (pre-roll, writer, parando/grabando); aquí solo la matemática.
- Parámetros globales configurables (`.env` RF_MOV_*): umbral de diferencia,
  kernel de blur e iteraciones de dilate (antes hardcodeados 21/21/2).
  `dontCare`, `segundos_analizar`, `porcentaje_mov`, `fps` y `sensibilidad`
  siguen siendo por cámara (argv de capturador.php).
- `sensibilidad > 1` NO rompe la detección: el buffer sigue llenándose hasta
  `frames_a_analizar` entradas (solo tarda `sensibilidad`× más), por lo que la
  ventana de reloj pasa a `segundos_analizar × sensibilidad` y se muestrea 1 de
  cada N frames (menos CPU, menor resolución temporal). Comportamiento
  preservado idéntico al legacy.
"""
from __future__ import annotations

from dataclasses import dataclass

import cv2


@dataclass
class MotionConfig:
    segundos_analizar: int = 2      # ventana de decisión (segundos)
    porcentaje_mov: int = 60        # % de frames con movimiento para disparar
    dontCare: int = 220             # área mínima del contorno (px², frame redimensionado)
    fps: int = 14                   # frecuencia de muestreo (throttle + fps del MP4)
    sensibilidad: int = 1           # analizar 1 de cada N frames (más alto = menos CPU)
    threshold: int = 21             # umbral de diferencia de píxel (RF_MOV_THRESHOLD)
    blur: int = 21                  # kernel GaussianBlur (RF_MOV_BLUR)
    dilate: int = 2                 # iteraciones de dilate (RF_MOV_DILATE)
    dontCare_boost: int | None = None                # área mínima en modo asedio (None = sin cambio)
    frames_con_movimiento_boost: int | None = None   # frames para disparar en modo asedio (None = sin cambio)

    @property
    def frames_a_analizar(self) -> int:
        """Tamaño del buffer de decisión (en frames ANALIZADOS).

        Se mantiene la semántica legacy (`segundos_analizar × fps`): con
        `sensibilidad > 1` el buffer solo recibe 1 de cada N frames, por lo que
        cubre `segundos_analizar × sensibilidad` segundos de reloj. No se divide
        por `sensibilidad` para no alterar el comportamiento actual.
        """
        return int(self.segundos_analizar * self.fps)

    @property
    def frames_con_movimiento(self) -> int:
        """Nº de frames con movimiento necesarios en el buffer para disparar."""
        return max(1, round(self.frames_a_analizar * self.porcentaje_mov / 100))

    @property
    def tiempo_espera_fps_ms(self) -> int:
        return int(1000 / self.fps)


def hay_movimiento(motion_list, frames_con_movimiento: int) -> bool:
    """True si hay >= `frames_con_movimiento` frames con movimiento en el buffer.

    Los valores no-1 del buffer (None/0) no cuentan: mismo criterio que el
    `hay_movimiento()` legacy de guarda_movimientosV3.py.
    """
    num = sum(1 for m in motion_list if m == 1)
    return num >= frames_con_movimiento


class MotionDetector:
    """Detector de movimiento frame a frame (absdiff + umbral + contorno máximo).

    Uso (idéntico al bucle legacy de guarda_movimientosV3.py):

        det = MotionDetector(MotionConfig(...))
        while True:
            frame = cv2.resize(frame_original, ...)   # el worker redimensiona
            motion, hay = det.process(frame)          # motion None solo el 1er frame
            if motion is not None:
                haymovimiento = hay                   # actualizar solo si se analizó
            if haymovimiento and not grabando:
                ... empieza a grabar ...

    El gate de `sensibilidad` (analizar 1 de cada N frames) lo aplica el WORKER
    llamando a process() solo cuando toca (igual que el legacy): así el pre-roll
    y el buffer conservan exactamente la cadencia original. Esta clase analiza
    SIEMPRE el frame que recibe (apto también para replay de calibración).
    """

    def __init__(self, cfg: MotionConfig | None = None):
        self.cfg = cfg or MotionConfig()
        self.prevFrame = None
        self.motion_list: list = []      # buffer rodante (tamaño frames_a_analizar)
        self.boost = False               # modo asedio: umbral fino (alarmas)

    def set_boost(self, activo: bool) -> None:
        """Activa/desactiva el modo asedio (alarmas "La Almenara").

        En modo asedio el detector baja el área mínima (dontCare_boost) y el nº
        de frames para disparar (frames_con_movimiento_boost): así cualquier
        mínimo movimiento cuenta y la grabación continua es posible.
        """
        self.boost = bool(activo)

    def _dontCare(self) -> int:
        if self.boost and self.cfg.dontCare_boost is not None:
            return self.cfg.dontCare_boost
        return self.cfg.dontCare

    def _frames_con_movimiento(self) -> int:
        if self.boost and self.cfg.frames_con_movimiento_boost is not None:
            return self.cfg.frames_con_movimiento_boost
        return self.cfg.frames_con_movimiento

    def hay_ahora(self) -> bool:
        """Re-lectura del buffer actual (equivalente a `hay_movimiento(motion_list)`
        de guarda_movimientosV3.py en sus re-comprobaciones)."""
        return hay_movimiento(self.motion_list, self._frames_con_movimiento())

    def process(self, frame):
        """Analiza un frame (BGR, ya redimensionado). Devuelve `(motion, hay)`.

        - `motion`: 0/1 tras el análisis; None solo en el primer frame (que solo
          inicializa prevFrame).
        - `hay`: decisión de disparo con el buffer tras este análisis. Solo es
          válida cuando `motion` no es None.
        """
        cfg = self.cfg
        output = cv2.GaussianBlur(frame, (cfg.blur, cfg.blur), 0)

        if self.prevFrame is None:
            self.prevFrame = output
            return None, False

        frameDelta = cv2.absdiff(self.prevFrame, output)
        frameDelta = cv2.cvtColor(frameDelta, cv2.COLOR_BGR2GRAY)
        thresh = cv2.threshold(frameDelta, cfg.threshold, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=cfg.dilate)
        cnts, _ = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)

        # Solo el contorno de mayor área: como la decisión es un umbral
        # (`area >= dontCare`), comprobar el máximo es equivalente a "¿alguno
        # supera dontCare?" (si el máximo no lo supera, ninguno lo hace).
        if cnts:
            max_area = max(cv2.contourArea(c) for c in cnts)
            motion = 1 if max_area >= self._dontCare() else 0
        else:
            motion = 0

        self.prevFrame = output
        self.motion_list.append(motion)
        self.motion_list = self.motion_list[-cfg.frames_a_analizar:]

        return motion, hay_movimiento(self.motion_list, self._frames_con_movimiento())
