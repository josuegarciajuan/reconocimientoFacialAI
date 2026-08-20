#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Vigilancia diaria de deriva (cámara posiblemente movida) — motor/vigilar_deriva.py

Comprueba 1 vez/día (timer systemd rf-vigilar-deriva) si alguna cámara cambió de
posición, usando una FIRMA ESTRUCTURAL robusta frente a cambios de entorno
(una caja que aparece hoy y mañana no, o una persona que pasa, NO deben avisar):

  1. Fondo MEDIANA de ~1 frame/segundo durante --captura-s s (suprime objetos
     transitorios que ocupan <50% de los frames).
  2. Ecualización adaptativa (CLAHE) -> tolera cambios de luz.
  3. Mapa de BORDES (Sobel) -> densidad de bordes por celda (rejilla 8x6, 48
     valores z-score). Paredes/puertas/suelo apenas cambian aunque muevan una
     caja; si la cámara se gira o desplaza, la estructura completa cambia.
  4. Comparación con una REFERENCIA DE LARGO PLAZO (media exponencial EMA) que
     SOLO se actualiza los días de alta similitud: un cambio temporal de un día
     no se "hornea" en la referencia.
  5. REGLA ANTI-FALSA-ALARMA: se avisa solo si la similitud cae por debajo de
     --min-sim durante 2 DÍAS CONSECUTIVOS (la caja de un día se descarta; una
     cámara movida persiste).

Salida (datos runtime, gitignored bajo motor/calibrador/deriva/):
  - <camara_id>.json  estado por cámara (referencia, n_dias, última similitud)
  - alertas.json      alertas activas (las lee el panel para el aviso)

Uso:
    motor/venv/bin/python motor/vigilar_deriva.py --ruta /root/reconocimientoFacial \
        [--local N] [--solo-camara N] [--captura-s 30] [--min-sim 0.75]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from datetime import datetime

import cv2
import numpy as np

# Rejilla de celdas de densidad de bordes (ancho x alto)
GRID_W, GRID_H = 8, 6
CAPTURE_W = 320
EMA_ALPHA = 0.10          # peso de la observación de HOY en la referencia (0.1 = muy estable)
MIN_FRAMES = 8            # mínimo de frames capturados para calcular la mediana
MAX_FRAMES = 40


def _php_ws(ruta: str, *args) -> str:
    try:
        r = subprocess.run(["php", os.path.join(ruta, "ws.php"), *[str(a) for a in args]],
                           capture_output=True, text=True, timeout=30, cwd=ruta)
        return r.stdout.strip()
    except Exception:
        return ""


def _camaras(ruta: str, local: int) -> list[dict]:
    """Cámaras activas (sistema=0, encendida=1) vía ws.php camaras_activas."""
    out = _php_ws(ruta, "camaras_activas", local)
    try:
        data = json.loads(out)
        return [c for c in data if isinstance(c, dict) and c.get("id") and c.get("url_conexion")]
    except Exception:
        return []


def _dir_deriva(ruta: str) -> str:
    d = os.path.join(ruta, "motor/calibrador/deriva")
    os.makedirs(d, exist_ok=True)
    return d


def _capturar_frames(url: str, segundos: int) -> list[np.ndarray]:
    """Captura ~1 frame gris (320px) por segundo durante `segundos`. [] si no hay señal."""
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|timeout;5000000"
    cap = cv2.VideoCapture(url)
    if not cap.isOpened():
        return []
    frames: list[np.ndarray] = []
    t0 = time.time()
    fin = t0 + max(5, segundos)
    ultimo_ts = 0.0
    while time.time() < fin and len(frames) < MAX_FRAMES:
        ret, frame = cap.read()
        if not ret or frame is None:
            if time.time() - t0 > 8 and not frames:
                break  # sin señal desde el inicio
            time.sleep(0.5)
            continue
        ahora = time.time()
        if ahora - ultimo_ts >= 1.0:
            ultimo_ts = ahora
            h, w = frame.shape[:2]
            sc = CAPTURE_W / max(1, w)
            gray = cv2.cvtColor(cv2.resize(frame, (CAPTURE_W, int(h * sc))),
                                cv2.COLOR_BGR2GRAY)
            frames.append(gray)
    cap.release()
    return frames


def _descriptor(frames: list[np.ndarray]) -> np.ndarray:
    """Fondo mediana -> CLAHE -> bordes Sobel -> densidad por celda (48, z-score)."""
    stack = np.stack(frames, axis=0).astype(np.uint8)
    med = np.median(stack, axis=0).astype(np.uint8)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    eq = clahe.apply(med)
    gx = cv2.Sobel(eq, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(eq, cv2.CV_32F, 0, 1, ksize=3)
    mag = cv2.magnitude(gx, gy)
    mag = (mag / max(1.0, float(mag.max())) * 255.0).astype(np.uint8)

    h, w = mag.shape
    cw, ch = w / GRID_W, h / GRID_H
    feats = []
    for r in range(GRID_H):
        for c in range(GRID_W):
            cell = mag[int(r * ch):int((r + 1) * ch), int(c * cw):int((c + 1) * cw)]
            feats.append(float(cell.mean()))
    v = np.asarray(feats, dtype=np.float64)
    std = v.std()
    if std < 1e-6:
        return np.zeros_like(v)
    return (v - v.mean()) / std


def _sim(a: np.ndarray, b: np.ndarray) -> float:
    """Correlación (coseno de vectores z-score) en [-1, 1]."""
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-9 or nb < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _celdas_cambiadas(today: np.ndarray, ref: np.ndarray, top: int = 3) -> list[dict]:
    """Top celdas con mayor diferencia (para localizar dónde cambió la escena)."""
    idx = np.argsort(np.abs(today - ref))[::-1][:top]
    out = []
    for i in idx:
        r, c = divmod(int(i), GRID_W)
        out.append({"fila": r + 1, "col": c + 1, "delta": round(float(today[i] - ref[i]), 3)})
    return out


def _decidir_dia(st: dict | None, today: np.ndarray, min_sim: float,
                 hoy: str) -> tuple[dict, dict | None]:
    """Actualiza el estado de deriva de una cámara con la firma de HOY (lógica pura).

    Regla anti-falsa-alarma: avisa (alerta) solo si la similitud cae por debajo de
    `min_sim` durante 2 DÍAS CONSECUTIVOS. La referencia EMA solo se actualiza en
    días estables (un cambio temporal de un día no se "hornea" en la referencia).

    Devuelve (nuevo_estado, alerta_evento|None).
    """
    if st is None or st.get("referencia") is None:
        # Primer día: fijar referencia sin comparar (no se avisa).
        return ({
            "referencia": today.tolist(), "n_dias": 1,
            "ultima_sim": None, "dias_bajos": 0, "alerta": False,
            "fecha_referencia": hoy, "fecha_ultimo_check": hoy,
        }, None)

    ref = np.asarray(st["referencia"], dtype=np.float64)
    sim = _sim(today, ref)
    dias_bajos = int(st.get("dias_bajos", 0))
    alerta = bool(st.get("alerta", False))
    alerta_evento = None

    if sim >= min_sim:
        # Escena estable: actualizar EMA (solo en días buenos) y desactivar alerta.
        ref_new = EMA_ALPHA * today + (1.0 - EMA_ALPHA) * ref
        dias_bajos = 0
        alerta = False
    else:
        dias_bajos += 1
        if dias_bajos >= 2:
            alerta = True
            alerta_evento = {
                "fecha": hoy, "similitud": round(sim, 3), "dias_bajos": dias_bajos,
                "celdas": _celdas_cambiadas(today, ref),
            }
        ref_new = ref  # no se contamina la referencia con el día raro

    nuevo = {
        "referencia": ref_new.tolist(),
        "n_dias": int(st.get("n_dias", 0)) + 1,
        "ultima_sim": round(sim, 3),
        "dias_bajos": dias_bajos,
        "alerta": alerta,
        "fecha_referencia": st.get("fecha_referencia"),
        "fecha_ultimo_check": hoy,
    }
    return nuevo, alerta_evento


def _leer(f: str) -> dict | None:
    try:
        with open(f) as fh:
            return json.load(fh)
    except Exception:
        return None


def _escribir(f: str, data) -> None:
    try:
        os.makedirs(os.path.dirname(f), exist_ok=True)
        with open(f, "w") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
    except Exception:
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--local", type=int, default=0, help="local_id (0 = todas)")
    ap.add_argument("--solo-camara", type=int, default=0, help="solo esta cámara")
    ap.add_argument("--captura-s", type=int, default=30)
    ap.add_argument("--min-sim", type=float, default=0.75)
    ap.add_argument("--reset-camara", type=int, default=0,
                    help="borra la referencia de esta cámara (restablecer) y sale")
    args = ap.parse_args()

    deriva_dir = _dir_deriva(args.ruta)
    alertas_path = os.path.join(deriva_dir, "alertas.json")

    # Restablecer referencia de una cámara (desde el panel).
    if args.reset_camara > 0:
        f = os.path.join(deriva_dir, str(args.reset_camara) + ".json")
        if os.path.isfile(f):
            os.remove(f)
        alertas = _leer(alertas_path) or {}
        alertas.pop(str(args.reset_camara), None)
        _escribir(alertas_path, alertas)
        print(f"referencia de la cámara {args.reset_camara} restablecida")
        return 0

    cams = _camaras(args.ruta, args.local)
    if args.solo_camara > 0:
        cams = [c for c in cams if int(c["id"]) == args.solo_camara]
    if not cams:
        print("sin cámaras activas para vigilar")
        return 0

    hoy = datetime.now().isoformat(timespec="seconds")
    alertas = _leer(alertas_path) or {}

    for c in cams:
        cam_id = int(c["id"])
        print(f"[{cam_id}] capturando firma ({args.captura_s}s)…", flush=True)
        frames = _capturar_frames(c["url_conexion"], args.captura_s)
        if len(frames) < MIN_FRAMES:
            print(f"[{cam_id}] señal insuficiente ({len(frames)} frames): se omite, "
                  "se conserva la referencia anterior", flush=True)
            continue
        today = _descriptor(frames)

        f = os.path.join(deriva_dir, str(cam_id) + ".json")
        st = _leer(f)
        nuevo, alerta_evento = _decidir_dia(st, today, args.min_sim, hoy)

        if alerta_evento is not None:
            alertas[str(cam_id)] = alerta_evento
            print(f"[{cam_id}] ALERTA: similitud {alerta_evento['similitud']} durante "
                  f"{alerta_evento['dias_bajos']} días consecutivos; celdas más cambiadas: "
                  f"{alerta_evento['celdas']}", flush=True)
        else:
            # Sin evento de alerta hoy: limpiar cualquier alerta previa (escena estable).
            alertas.pop(str(cam_id), None)
            if st is None or st.get("referencia") is None:
                print(f"[{cam_id}] referencia inicial fijada (n_dias=1)", flush=True)
            elif nuevo["ultima_sim"] is not None and nuevo["ultima_sim"] < args.min_sim:
                print(f"[{cam_id}] similitud {nuevo['ultima_sim']} < {args.min_sim} "
                      f"(día {nuevo['dias_bajos']}/2), sin aviso todavía", flush=True)
            else:
                print(f"[{cam_id}] similitud {nuevo['ultima_sim']} >= {args.min_sim}: ok, "
                      "EMA actualizada", flush=True)

        _escribir(f, nuevo)

    _escribir(alertas_path, alertas)
    print(f"alerta(s) activa(s): {len(alertas)}")
    return 0


if __name__ == "__main__":
    main()
