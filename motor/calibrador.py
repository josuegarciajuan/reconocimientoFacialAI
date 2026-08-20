#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Probe del calibrador guiado (La Forja · Templar) — motor/calibrador.py

Ejecuta un RITUAL de calibración en vivo sobre una cámara RTSP usando el MISMO
código de producción (motor/core/model.analyze, motor/core/motion.MotionDetector,
motor/core/quality.face_sharpness) y escribe datos runtime (gitignored):

  - motor/calibrador/resultados/<job_id>.json     métricas + recomendación del ritual
  - motor/calibrador/frames/<job_id>.jpg          último frame anotado (para el panel)
  - motor/calibrador/recomendaciones/<camara>.json recomendación vigente (badges en Editar)

Rituales (Fase 1):
  A · Alcance: el operador se pone a distintas distancias; se miden tamaño (px) y
      nitidez de las caras detectadas -> recomienda RF_SR_EMBED_MIN_FACE /
      RF_MIN_SHARPNESS (y avisa si no ve caras con el det_size actual).
  B · Paso veloz: el operador pasa rápido delante de la cámara; se mide el fps real
      del stream, cuántos frames con cara se capturaron y si el MotionDetector con
      los parámetros ACTUALES de la cámara dispara -> recomienda fps/sensibilidad.

Reglas:
- NUNCA aplica nada: solo mide y propone (un humano revisa y aplica en el panel).
- El resaltado en el frame es lo que ve el operador: verde = cara aprovechable,
  ámbar = detectada pero pequeña (necesita SR) o borrosa, sin caja = no la ve.

Uso (lo lanza acciones_ajax.php en segundo plano):
    motor/venv/bin/python motor/calibrador.py <camara_id> <url_rtsp> <ritual> <job_id> <segundos> \
        --ruta /root/reconocimientoFacial \
        --parametros "seg,porc,dontCare,fps,resize_pct,sens" \
        [--det-size 1280] [--min-sharpness 55] [--sr-embed-min-face 96] [--min-score 0.4]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime

import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.env import get_float, get_int  # noqa: E402
from motor.core.model import analyze  # noqa: E402
from motor.core.motion import MotionConfig, MotionDetector  # noqa: E402
from motor.core.quality import face_sharpness  # noqa: E402

ANOTAR_MS = 400          # cada cuántos ms se refresca el frame anotado (panel)
FACE_SAMPLE = 2          # analizar caras 1 de cada 2 frames (CPU acotada)
DISP_WIDTH = 800         # ancho del frame anotado para el panel
SIN_SENAL_S = 6.0        # abortar si el stream no entrega frames en X segundos
GREEN = (0, 200, 0)
AMBER = (0, 140, 255)
RED = (0, 0, 255)
WHITE = (255, 255, 255)


def _escribir(path: str, data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _redondear5(v: float) -> int:
    return int(round(float(v) / 5.0) * 5)


def anotar_frame(frame, faces_info, hud: list[str], det_size: int) -> np.ndarray:
    """Pinta cajas (verde=ok, ámbar=SR/borrosa) y el HUD sobre el frame."""
    for f in faces_info:
        x1, y1, x2, y2 = f["bbox"]
        color = GREEN if f["ok"] else AMBER
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        txt = f"{f['px']}px S={f['sharp']:.0f}"
        cv2.putText(frame, txt, (x1, max(14, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)
    y = 24
    for line in hud:
        cv2.putText(frame, line, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, WHITE, 2)
        y += 24
    # Nota del det_size usado (contexto de la medición)
    cv2.putText(frame, f"det_size={det_size} (muestreo 1/{FACE_SAMPLE})",
                (10, frame.shape[0] - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)
    return frame


def recomendacion_ritual_a(obs_px: list, obs_sharp: list, actual: dict) -> dict:
    """Recomendaciones globales (RF_*) del ritual A a partir de las observaciones."""
    out = {}
    if not obs_px:
        out["RF_DET_SIZE"] = {
            "actual": actual["RF_DET_SIZE"],
            "recomendado": max(actual["RF_DET_SIZE"], 1280),
            "motivo": "No se detectó ninguna cara durante el ritual. Si el operador "
                      "estaba en escena, prueba subir RF_DET_SIZE a 1280 (el detector "
                      "pierde caras lejanas a 640).",
        }
        return out
    px = np.array(obs_px, dtype=float)
    sharp = np.array(obs_sharp, dtype=float)

    # Cara mínima para SR antes de embedding: p25 del tamaño observado (las caras
    # pequeñas de la cámara deben pasar por SR), acotado [48, actual] y a múltiplos de 5.
    p25 = float(np.percentile(px, 25))
    rec = _clamp(_redondear5(p25), 48, max(96, int(actual["RF_SR_EMBED_MIN_FACE"])))
    out["RF_SR_EMBED_MIN_FACE"] = {
        "actual": actual["RF_SR_EMBED_MIN_FACE"],
        "recomendado": rec,
        "motivo": f"El 25% de las caras vistas miden <= {p25:.0f} px de ancho. "
                  f"Con SR antes del embedding las caras de ese tamaño mejoran su matching.",
    }

    # Nitidez mínima: p10 del enfoque observado (no descartar las caras válidas de lejos).
    p10 = float(np.percentile(sharp, 10))
    rec_sharp = _clamp(_redondear5(p10), 20, int(actual["RF_MIN_SHARPNESS"]))
    out["RF_MIN_SHARPNESS"] = {
        "actual": actual["RF_MIN_SHARPNESS"],
        "recomendado": rec_sharp,
        "motivo": f"El 10% de las caras vistas tiene enfoque <= {p10:.0f}. Bajar el "
                  f"umbral a {rec_sharp} admite esas caras lejanas sin dejar entrar borrosas.",
    }

    out["_resumen"] = {
        "caras_vistas": int(len(px)),
        "px_min": int(px.min()), "px_p25": int(p25), "px_max": int(px.max()),
        "sharp_min": round(float(sharp.min()), 1), "sharp_p10": round(p10, 1),
        "sharp_max": round(float(sharp.max()), 1),
    }
    return out


def recomendacion_ritual_b(real_fps: float, frames_con_cara: int, racha_max: int,
                           disparos: int, actual: dict) -> dict:
    """Recomendaciones POR CÁMARA (fps/sensibilidad) del ritual B."""
    paso_ok = (racha_max >= 2) or (disparos >= 1)
    por_camara = {}
    fps_actual = int(actual["fps"])
    sens_actual = int(actual["sensibilidad"])

    if real_fps < fps_actual:
        fps_rec = fps_actual
        motivo = (f"El stream entrega {real_fps:.1f} fps reales, por debajo de los "
                  f"{fps_actual} configurados: subir FPS no añade frames (la cámara no "
                  f"da más). Se mantiene {fps_actual}.")
    elif paso_ok:
        fps_rec = _clamp(int(round(real_fps)), 10, 30)
        motivo = (f"El stream entrega {real_fps:.1f} fps reales y el paso rápido se "
                  f"capturó bien (racha de {racha_max} frames con cara, {disparos} "
                  f"disparo(s)). FPS {fps_rec} es la cadencia natural de la cámara.")
    else:
        fps_rec = _clamp(max(int(round(real_fps)), fps_actual + 2), 10, 30)
        motivo = (f"El paso rápido NO se capturó bien ({racha_max} frames con cara, "
                  f"{disparos} disparos). Se sube FPS a {fps_rec} (máximo que entrega "
                  f"el stream: {real_fps:.1f}) para no perder movimiento rápido.")

    por_camara["fps"] = {"actual": fps_actual, "recomendado": fps_rec, "motivo": motivo}

    if sens_actual > 1:
        if not paso_ok or real_fps >= 10:
            por_camara["sensibilidad"] = {
                "actual": sens_actual,
                "recomendado": 1,
                "motivo": f"Con salto de frames {sens_actual} se pierde resolución "
                          f"temporal y el paso rápido no se capturó bien. Se recomienda 1 "
                          f"(analizar todos los frames) mientras la CPU lo permita.",
            }
        else:
            por_camara["sensibilidad"] = {
                "actual": sens_actual,
                "recomendado": sens_actual,
                "motivo": "El paso rápido se capturó bien con el salto actual: se mantiene.",
            }

    por_camara["_resumen"] = {
        "fps_real": round(real_fps, 1),
        "frames_con_cara": int(frames_con_cara),
        "racha_max_frames_cara": int(racha_max),
        "disparos_movimiento": int(disparos),
        "paso_capturado": bool(paso_ok),
    }
    return por_camara


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("camara_id", type=int)
    ap.add_argument("url_rtsp")
    ap.add_argument("ritual", choices=["A", "B"])
    ap.add_argument("job_id")
    ap.add_argument("segundos", type=int)
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--parametros", default="", help="seg,porc,dontCare,fps,resize_pct,sens")
    ap.add_argument("--det-size", type=int, default=None)
    ap.add_argument("--min-sharpness", type=float, default=None)
    ap.add_argument("--sr-embed-min-face", type=int, default=None)
    ap.add_argument("--min-score", type=float, default=0.4)
    args = ap.parse_args()

    ruta = args.ruta
    resultados_path = os.path.join(ruta, "motor/calibrador/resultados", args.job_id + ".json")
    frame_path = os.path.join(ruta, "motor/calibrador/frames", args.job_id + ".jpg")
    reco_path = os.path.join(ruta, "motor/calibrador/recomendaciones", str(args.camara_id) + ".json")

    # Parámetros actuales de la cámara (para el MotionDetector del ritual B).
    p = [x.strip() for x in args.parametros.split(",")] + [""] * 6
    seg_actual = int(p[0] or 2)
    porc_actual = int(p[1] or 60)
    dc_actual = int(p[2] or 220)
    fps_actual = int(p[3] or 14)
    resize_pct = float(p[4] or 60)
    sens_actual = int(p[5] or 1)
    resize = resize_pct / 100.0

    # Globales actuales (desde .env; si faltan, defaults de código).
    det_size = args.det_size or get_int(ruta, "RF_DET_SIZE", 1280)
    min_sharpness = args.min_sharpness if args.min_sharpness is not None else get_float(ruta, "RF_MIN_SHARPNESS", 55.0)
    sr_embed = args.sr_embed_min_face or get_int(ruta, "RF_SR_EMBED_MIN_FACE", 96)

    t0 = time.time()
    fin = t0 + max(5, min(60, args.segundos))
    try:
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|timeout;5000000"
        cap = cv2.VideoCapture(args.url_rtsp)
        if not cap.isOpened():
            raise RuntimeError("no se pudo abrir el stream RTSP")

        cfg_mov = MotionConfig(segundos_analizar=seg_actual, porcentaje_mov=porc_actual,
                               dontCare=dc_actual, fps=fps_actual, sensibilidad=sens_actual,
                               threshold=get_int(ruta, "RF_MOV_THRESHOLD", 21),
                               blur=get_int(ruta, "RF_MOV_BLUR", 21),
                               dilate=get_int(ruta, "RF_MOV_DILATE", 2))
        detector = MotionDetector(cfg_mov)

        # Métricas
        n_frames = 0
        n_frames_cara = 0
        racha = 0
        racha_max = 0
        disparos = 0
        prev_hay = False
        obs_px: list = []
        obs_sharp: list = []
        ultimo_frame = None
        ultima_anotacion = 0.0
        ultimo_frame_ts = time.time()

        while time.time() < fin:
            ret, frame = cap.read()
            if not ret or frame is None:
                if time.time() - ultimo_frame_ts > SIN_SENAL_S:
                    raise RuntimeError(f"sin señal de la cámara durante {SIN_SENAL_S:.0f}s")
                continue
            ultimo_frame_ts = time.time()
            n_frames += 1

            # ---- Movimiento (ritual B) con los parámetros actuales ----
            frame_mov = cv2.resize(frame, None, fx=resize, fy=resize)
            # Emular el gate de sensibilidad del worker (1 de cada N frames analizados).
            if n_frames % max(1, sens_actual) == 0:
                _, hay = detector.process(frame_mov)
                if hay and not prev_hay:
                    disparos += 1
                prev_hay = hay

            # ---- Caras (ritual A y B) con muestreo ----
            if n_frames % FACE_SAMPLE == 0:
                faces = analyze(frame, det_size=(det_size, det_size), min_score=args.min_score)
                faces_info = []
                if faces:
                    n_frames_cara += 1
                    racha += 1
                    racha_max = max(racha_max, racha)
                    for f in faces:
                        x1, y1, x2, y2 = f.bbox
                        px = x2 - x1
                        sharp = face_sharpness(frame, f)
                        ok = px >= min(64, sr_embed) and sharp >= min_sharpness
                        obs_px.append(px)
                        obs_sharp.append(sharp)
                        faces_info.append({"bbox": [x1, y1, x2, y2], "px": px,
                                           "sharp": round(sharp, 1), "ok": ok,
                                           "yaw": round(f.yaw, 1)})
                else:
                    racha = 0
            else:
                faces_info = []
                racha = 0

            # ---- Frame anotado (refresco periódico) ----
            ahora = time.time()
            restante = max(0, fin - ahora)
            fps_real = n_frames / max(0.001, ahora - t0)
            hud = [
                f"RITUAL {args.ritual} · cam {args.camara_id} · quedan {restante:.0f}s",
                f"fps real: {fps_real:.1f}  |  frames: {n_frames}",
                f"caras: {n_frames_cara} (racha {racha_max})  |  disparos mov: {disparos}",
                "verde = cara aprovechable · ámbar = pequeña (SR) o borrosa",
            ]
            if args.ritual == "A":
                hud.append("Ponte a distintas distancias (cerca, media, lejos).")
            else:
                hud.append("Pasa rápido delante de la cámara varias veces.")
            frame_anot = anotar_frame(frame.copy(), faces_info, hud, det_size)
            if frame_anot.shape[1] > DISP_WIDTH:
                sc = DISP_WIDTH / frame_anot.shape[1]
                frame_anot = cv2.resize(frame_anot, None, fx=sc, fy=sc)
            ultimo_frame = frame_anot
            if ahora - ultima_anotacion >= ANOTAR_MS / 1000.0:
                ultima_anotacion = ahora
                try:
                    os.makedirs(os.path.dirname(frame_path), exist_ok=True)
                    cv2.imwrite(frame_path, frame_anot)
                except Exception:
                    pass

        cap.release()
        if ultimo_frame is None:
            raise RuntimeError("no se capturó ningún frame")

        fps_real = n_frames / max(0.001, time.time() - t0)
        duracion = time.time() - t0

        if args.ritual == "A":
            actual_glob = {
                "RF_DET_SIZE": det_size,
                "RF_MIN_SHARPNESS": int(min_sharpness),
                "RF_SR_EMBED_MIN_FACE": sr_embed,
            }
            recomendaciones = recomendacion_ritual_a(obs_px, obs_sharp, actual_glob)
            resumen = recomendaciones.pop("_resumen", {})
            resultado = {
                "camara_id": args.camara_id, "ritual": "A", "estado": "ok",
                "job": args.job_id, "timestamp": datetime.now().isoformat(timespec="seconds"),
                "duracion_s": round(duracion, 1), "fps_real": round(fps_real, 1),
                "frames": n_frames, "det_size_usado": det_size,
                "resumen": resumen,
                "recomendaciones": recomendaciones,
            }
            _escribir(reco_path, {
                "camara_id": args.camara_id, "actualizados": datetime.now().isoformat(timespec="seconds"),
                "ritual": "A", "recomendaciones": recomendaciones, "por_camara": {},
            })
        else:
            actual_cam = {"fps": fps_actual, "sensibilidad": sens_actual}
            por_camara = recomendacion_ritual_b(fps_real, n_frames_cara, racha_max,
                                                disparos, actual_cam)
            resumen = por_camara.pop("_resumen", {})
            resultado = {
                "camara_id": args.camara_id, "ritual": "B", "estado": "ok",
                "job": args.job_id, "timestamp": datetime.now().isoformat(timespec="seconds"),
                "duracion_s": round(duracion, 1), "fps_real": round(fps_real, 1),
                "frames": n_frames, "parametros_usados": {
                    "segundos_analizar": seg_actual, "porcentaje_mov": porc_actual,
                    "dontCare": dc_actual, "fps": fps_actual,
                    "redimesionframe_pct": int(resize_pct), "sensibilidad": sens_actual},
                "resumen": resumen,
                "recomendaciones": por_camara,
            }
            _escribir(reco_path, {
                "camara_id": args.camara_id, "actualizados": datetime.now().isoformat(timespec="seconds"),
                "ritual": "B", "recomendaciones": {}, "por_camara": por_camara,
            })

        _escribir(resultados_path, resultado)
        print(json.dumps({"estado": "ok", "job": args.job_id}, ensure_ascii=False))
        return 0

    except Exception as e:  # noqa: BLE001
        _escribir(resultados_path, {
            "camara_id": args.camara_id, "ritual": args.ritual, "estado": "error",
            "job": args.job_id, "timestamp": datetime.now().isoformat(timespec="seconds"),
            "error": str(e),
        })
        print(json.dumps({"estado": "error", "job": args.job_id, "error": str(e)},
                         ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
