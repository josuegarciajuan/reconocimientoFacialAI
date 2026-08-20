#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Probe del calibrador guiado (La Forja · Templar) — motor/calibrador.py

Ejecuta un RITUAL de calibración en vivo sobre una cámara RTSP usando el MISMO
código de producción (motor/core/model.analyze, motor/core/motion.MotionDetector,
motor/cruces.CrossingDetector, motor/core/quality.face_sharpness) y escribe
datos runtime (gitignored):

  - motor/calibrador/resultados/<job_id>.json     métricas + recomendación del ritual
  - motor/calibrador/frames/<job_id>.jpg          último frame anotado (para el panel)
  - motor/calibrador/recomendaciones/<camara>.json recomendación vigente (badges en Editar)

Rituales:
  A · Alcance: el operador se pone a distintas distancias; se miden tamaño (px) y
      nitidez de las caras -> recomienda RF_SR_EMBED_MIN_FACE / RF_MIN_SHARPNESS.
  B · Paso veloz: el operador pasa rápido delante de la cámara; se mide fps real,
      frames con cara y disparos con los parámetros ACTUALES -> recomienda fps/sensibilidad.
  C · Disparo (2 fases): C1 caminar despacio (DEBE disparar) y C2 agitar la mano
      lejos (NO debe disparar). Combina ambas fases -> recomienda dontCare,
      porcentaje_mov y RF_MOV_THRESHOLD.
  D · Cruce de línea: el operador cruza la línea N veces; el detector de producción
      (MOG2+tracking) cuenta cruces y dirección -> recomienda RF_CRUCE_AREA_MIN.
  E · Identidad (OFFLINE, sin cámara): corre motor/eval/eval.py (TAR/FAR) sobre el
      set etiquetado motor/eval/data -> recomienda RF_MATCH_THRESHOLD / RF_MARGIN /
      RF_SECURE_THRESHOLD.
  F · Enfoque: el operador sostiene la cara a la distancia MÁXIMA de reconocimiento;
      se mide el enfoque -> recomienda RF_MIN_SHARPNESS.

Reglas:
- NUNCA aplica nada: solo mide y propone (un humano revisa y aplica en el panel).
- El resaltado en el frame es lo que ve el operador: verde = cara aprovechable,
  ámbar = detectada pero pequeña (necesita SR) o borrosa, sin caja = no la ve.

Uso (lo lanza acciones_ajax.php en segundo plano):
    motor/venv/bin/python motor/calibrador.py <camara_id> <url_rtsp> <ritual> <job_id> <segundos> \
        --ruta /root/reconocimientoFacial \
        --parametros "seg,porc,dontCare,fps,resize_pct,sens" \
        [--fase c1|c2] [--esperados N] \
        [--det-size 1280] [--min-sharpness 55] [--sr-embed-min-face 96] [--min-score 0.4]

El ritual E ignora la URL (pasar "-"): no necesita cámara.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
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
CYAN = (255, 200, 0)
MAGENTA = (255, 0, 200)


def _escribir(path: str, data: dict) -> None:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _leer_json(path: str) -> dict | None:
    try:
        with open(path) as fh:
            return json.load(fh)
    except Exception:
        return None


def _clamp(v, lo, hi):
    return max(lo, min(hi, v))


def _redondear5(v: float) -> int:
    return int(round(float(v) / 5.0) * 5)


def _php_ws(ruta: str, *args) -> str:
    try:
        r = subprocess.run(["php", os.path.join(ruta, "ws.php"), *[str(a) for a in args]],
                           capture_output=True, text=True, timeout=30, cwd=ruta)
        return r.stdout.strip()
    except Exception:
        return ""


def _cargar_lineas(ruta: str, camara_id: int) -> list:
    """Líneas de la cámara vía ws.php (mismo contrato que procesa_video.py)."""
    from motor.cruces import Line  # noqa: E402
    lineas = []
    ids = _php_ws(ruta, "listado_lineas", camara_id)
    for lid in [x.strip() for x in ids.split(",") if x.strip()]:
        coords = _php_ws(ruta, "coordenadas_linea", lid).split(",")
        if len(coords) == 4:
            try:
                lineas.append(Line(float(coords[0]), float(coords[1]),
                                   float(coords[2]), float(coords[3]), line_id=lid))
            except ValueError:
                pass
    return lineas


def _reco_path(ruta: str, camara_id: int) -> str:
    return os.path.join(ruta, "motor/calibrador/recomendaciones", str(camara_id) + ".json")


def _merge_reco(ruta: str, camara_id: int, ritual: str,
                recomendaciones: dict | None = None,
                por_camara: dict | None = None,
                extra: dict | None = None) -> None:
    """Fusiona las recomendaciones del ritual con las vigentes de la cámara."""
    path = _reco_path(ruta, camara_id)
    prev = _leer_json(path) or {}
    rec = dict(prev.get("recomendaciones") or {})
    rec.update(recomendaciones or {})
    pc = dict(prev.get("por_camara") or {})
    pc.update(por_camara or {})
    data = {
        "camara_id": camara_id,
        "actualizados": datetime.now().isoformat(timespec="seconds"),
        "ritual": ritual,
        "recomendaciones": rec,
        "por_camara": pc,
    }
    if extra:
        data.update(extra)
    _escribir(path, data)


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


# ---------------------------------------------------------------------------
# Recomendaciones
# ---------------------------------------------------------------------------

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

    p25 = float(np.percentile(px, 25))
    rec = _clamp(_redondear5(p25), 48, max(96, int(actual["RF_SR_EMBED_MIN_FACE"])))
    out["RF_SR_EMBED_MIN_FACE"] = {
        "actual": actual["RF_SR_EMBED_MIN_FACE"],
        "recomendado": rec,
        "motivo": f"El 25% de las caras vistas miden <= {p25:.0f} px de ancho. "
                  f"Con SR antes del embedding las caras de ese tamaño mejoran su matching.",
    }

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


def _ajuste_c(fases: dict, actual: dict) -> tuple[dict, dict, str]:
    """Combina las fases C1/C2 en recomendación (por_camara, globales, resumen)."""
    dc = int(actual["dontCare"]); porc = int(actual["porcentaje_mov"]); thr = int(actual["threshold"])
    dc_t = []; porc_t = []; thr_t = []
    motivos = []
    c1 = fases.get("c1"); c2 = fases.get("c2")
    if c1 is not None:
        if c1["disparos"] == 0:
            dc_t.append(max(30, round(dc * 0.6)))
            porc_t.append(max(30, porc - 15))
            thr_t.append(max(10, thr - 4))
            motivos.append(f"c1 caminar NO disparó ({c1['disparos']}): más sensible")
        else:
            motivos.append(f"c1 caminar disparó ({c1['disparos']})")
    if c2 is not None:
        if c2["disparos"] > 0:
            dc_t.append(min(2000, round(dc * 1.4)))
            porc_t.append(min(95, porc + 10))
            motivos.append(f"c2 mano lejos SÍ disparó ({c2['disparos']}): menos sensible")
        else:
            motivos.append(f"c2 mano lejos no disparó")
    if not motivos:
        motivos.append("sin fases registradas todavía")

    por_camara = {}
    glob = {}
    motivo = " · ".join(motivos)
    if dc_t:
        por_camara["dontCare"] = {"actual": dc, "recomendado": round(sum(dc_t) / len(dc_t)),
                                  "motivo": motivo + f" (media de {len(dc_t)} ajuste(s))"}
    if porc_t:
        por_camara["porcentaje_mov"] = {"actual": porc, "recomendado": round(sum(porc_t) / len(porc_t)),
                                        "motivo": motivo + f" (media de {len(porc_t)} ajuste(s))"}
    if thr_t:
        glob["RF_MOV_THRESHOLD"] = {"actual": thr, "recomendado": round(sum(thr_t) / len(thr_t)),
                                    "motivo": motivo}
    if not por_camara and not glob:
        pend = "c2" if "c1" in fases else ("c1" if "c2" in fases else "")
        if pend:
            por_camara["dontCare"] = {"actual": dc, "recomendado": dc,
                                      "motivo": motivo + f". Ejecuta también la fase {pend} "
                                                        "para completar el ajuste."}
        else:
            por_camara["dontCare"] = {"actual": dc, "recomendado": dc,
                                      "motivo": "Fases C1 y C2 correctas: se mantiene la configuración actual."}
    return por_camara, glob, motivo


def recomendacion_ritual_d(esperados: int, detectados: int, area_actual: float) -> dict:
    out = {}
    if detectados == 0 and esperados > 0:
        out["RF_CRUCE_AREA_MIN"] = {
            "actual": area_actual, "recomendado": max(100, round(area_actual * 0.6)),
            "motivo": f"No se detectó ningún cruce de los {esperados} esperados: el área "
                      f"mínima ({area_actual:.0f}) es demasiado alta para esta escena.",
        }
    elif detectados > esperados + 1:
        out["RF_CRUCE_AREA_MIN"] = {
            "actual": area_actual, "recomendado": min(5000, round(area_actual * 1.3)),
            "motivo": f"Se detectaron {detectados} cruces (esperados {esperados}): hay "
                      f"ruido (personas/objetos cercanos a la línea). Sube el área mínima.",
        }
    else:
        out["RF_CRUCE_AREA_MIN"] = {
            "actual": area_actual, "recomendado": area_actual,
            "motivo": f"Detectados {detectados} de {esperados} esperados: configuración "
                      f"correcta para esta escena.",
        }
    return out


def recomendacion_ritual_f(obs_px: list, obs_sharp: list, actual: dict) -> dict:
    out = {}
    if not obs_sharp:
        out["RF_DET_SIZE"] = {
            "actual": actual["RF_DET_SIZE"],
            "recomendado": max(actual["RF_DET_SIZE"], 1280),
            "motivo": "No se detectó ninguna cara en la distancia máxima. Prueba a subir "
                      "RF_DET_SIZE a 1280 o acércate un poco.",
        }
        return out
    sharp = np.array(obs_sharp, dtype=float)
    p25 = float(np.percentile(sharp, 25))
    rec = _clamp(_redondear5(p25), 20, int(actual["RF_MIN_SHARPNESS"]))
    out["RF_MIN_SHARPNESS"] = {
        "actual": actual["RF_MIN_SHARPNESS"],
        "recomendado": rec,
        "motivo": f"Sosteniendo la cara a la distancia máxima de reconocimiento, el 25% "
                  f"del enfoque fue <= {p25:.0f}. Con umbral {rec} esa distancia sigue siendo válida.",
    }
    out["_resumen"] = {
        "n": int(len(obs_px)),
        "px_min": int(min(obs_px)), "px_max": int(max(obs_px)),
        "sharp_min": round(float(sharp.min()), 1), "sharp_p25": round(p25, 1),
    }
    return out


# ---------------------------------------------------------------------------
# Ritual E (offline: TAR/FAR sobre motor/eval/data)
# ---------------------------------------------------------------------------

def ritual_e_offline(ruta: str, camara_id: int, job_id: str,
                     resultados_path: str) -> int:
    data_dir = os.path.join(ruta, "motor/eval/data")
    if not os.path.isdir(data_dir):
        _escribir(resultados_path, {
            "camara_id": camara_id, "ritual": "E", "estado": "error", "job": job_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "error": "No existe el set etiquetado motor/eval/data. Puebla la carpeta con "
                     "3+ personas x 3 poses (frente + perfiles) como indica motor/eval/README.md.",
        })
        return 1

    tmp = resultados_path + ".eval.json"
    cmd = [sys.executable, "-m", "motor.eval.eval", "--data-dir", data_dir,
           "--pose-aware", "--json-out", tmp]
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=1800, cwd=ruta)
    except Exception as e:
        _escribir(resultados_path, {
            "camara_id": camara_id, "ritual": "E", "estado": "error", "job": job_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"), "error": str(e),
        })
        return 1
    if not os.path.isfile(tmp):
        _escribir(resultados_path, {
            "camara_id": camara_id, "ritual": "E", "estado": "error", "job": job_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "error": "El eval no generó resultado (¿hay 3+ personas con 2+ poses en motor/eval/data?).",
        })
        return 1

    with open(tmp) as fh:
        data = json.load(fh)
    try:
        os.remove(tmp)
    except Exception:
        pass

    if data.get("estado") == "error":
        _escribir(resultados_path, {
            "camara_id": camara_id, "ritual": "E", "estado": "error", "job": job_id,
            "timestamp": datetime.now().isoformat(timespec="seconds"), "error": data.get("error", ""),
        })
        return 1

    sugerencia = data.get("sugerencia") or {}
    # Rellenar el "actual" de cada umbral desde el .env (para mostrar actual → recomendado)
    actuales = {
        "RF_MATCH_THRESHOLD": get_float(ruta, "RF_MATCH_THRESHOLD", 0.30),
        "RF_MARGIN": get_float(ruta, "RF_MARGIN", 0.03),
        "RF_SECURE_THRESHOLD": get_float(ruta, "RF_SECURE_THRESHOLD", 0.40),
    }
    for k, v in sugerencia.items():
        if k in actuales and isinstance(v, dict) and "actual" not in v:
            v["actual"] = actuales[k]
    resultado = {
        "camara_id": camara_id, "ritual": "E", "estado": "ok", "job": job_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "n_personas": data.get("n_personas"), "n_imagenes": data.get("n_imagenes"),
        "n_genuinos": data.get("n_genuinos"), "n_impostores": data.get("n_impostores"),
        "tar_far1": data.get("tar_far1"),
        "genuine_mean": data.get("genuine_mean"), "impostor_p95": data.get("impostor_p95"),
        "recomendaciones": sugerencia,
    }
    _escribir(resultados_path, resultado)
    _merge_reco(ruta, camara_id, "E", recomendaciones=sugerencia)
    return 0


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("camara_id", type=int)
    ap.add_argument("url_rtsp")
    ap.add_argument("ritual", choices=["A", "B", "C", "D", "E", "F"])
    ap.add_argument("job_id")
    ap.add_argument("segundos", type=int)
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--parametros", default="", help="seg,porc,dontCare,fps,resize_pct,sens")
    ap.add_argument("--fase", choices=["c1", "c2"], default="c1")
    ap.add_argument("--esperados", type=int, default=3)
    ap.add_argument("--det-size", type=int, default=None)
    ap.add_argument("--min-sharpness", type=float, default=None)
    ap.add_argument("--sr-embed-min-face", type=int, default=None)
    ap.add_argument("--min-score", type=float, default=0.4)
    args = ap.parse_args()

    ruta = args.ruta
    resultados_path = os.path.join(ruta, "motor/calibrador/resultados", args.job_id + ".json")
    frame_path = os.path.join(ruta, "motor/calibrador/frames", args.job_id + ".jpg")

    # Ritual E: no necesita cámara.
    if args.ritual == "E":
        return ritual_e_offline(ruta, args.camara_id, args.job_id, resultados_path)

    # Parámetros actuales de la cámara.
    p = [x.strip() for x in args.parametros.split(",")] + [""] * 6
    seg_actual = int(p[0] or 2)
    porc_actual = int(p[1] or 60)
    dc_actual = int(p[2] or 220)
    fps_actual = int(p[3] or 14)
    resize_pct = float(p[4] or 60)
    sens_actual = int(p[5] or 1)
    resize = resize_pct / 100.0

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

        # Movimiento (rituales B y C) con los parámetros actuales de la cámara.
        cfg_mov = MotionConfig(segundos_analizar=seg_actual, porcentaje_mov=porc_actual,
                               dontCare=dc_actual, fps=fps_actual, sensibilidad=sens_actual,
                               threshold=get_int(ruta, "RF_MOV_THRESHOLD", 21),
                               blur=get_int(ruta, "RF_MOV_BLUR", 21),
                               dilate=get_int(ruta, "RF_MOV_DILATE", 2))
        detector = MotionDetector(cfg_mov)

        # Cruces (ritual D) con los parámetros actuales (RF_CRUCE_*).
        from motor.cruces import CrossingConfig, CrossingDetector  # noqa: E402
        cruce_cfg = CrossingConfig.from_env(ruta)
        lineas = _cargar_lineas(ruta, args.camara_id) if args.ritual == "D" else []
        cruce_dets = [CrossingDetector(l, cruce_cfg) for l in lineas]
        cruces_detectados = []

        usar_caras = args.ritual in ("A", "B", "F")

        # Métricas
        n_frames = 0
        n_frames_cara = 0
        racha = 0
        racha_max = 0
        disparos = 0
        prev_hay = False
        max_area_mov = 0.0
        n_frames_mov = 0
        n_frames_analizados = 0
        obs_px: list = []
        obs_sharp: list = []
        ultimo_frame = None
        ultima_anotacion = 0.0
        ultimo_frame_ts = time.time()

        instrucciones = {
            "A": "Ponte a distintas distancias (cerca, media, lejos).",
            "B": "Pasa rápido delante de la cámara varias veces.",
            "C": "Fase c1: CAMINA despacio (debe disparar).  Fase c2: agita la mano LEJOS (no debe disparar).",
            "D": f"Cruza la línea {args.esperados} veces (espera 2-3 s entre cruce y cruce).",
            "F": "Sostén la cara a la distancia MÁXIMA donde aún deba reconocerte.",
        }
        titulo = f"RITUAL {args.ritual}"
        if args.ritual == "C":
            titulo += f" · {args.fase}"
        elif args.ritual == "D":
            titulo += f" · esperados={args.esperados}"

        while time.time() < fin:
            ret, frame = cap.read()
            if not ret or frame is None:
                if time.time() - ultimo_frame_ts > SIN_SENAL_S:
                    raise RuntimeError(f"sin señal de la cámara durante {SIN_SENAL_S:.0f}s")
                continue
            ultimo_frame_ts = time.time()
            n_frames += 1

            # ---- Movimiento (rituales B y C) ----
            frame_mov = cv2.resize(frame, None, fx=resize, fy=resize)
            if n_frames % max(1, sens_actual) == 0:
                n_frames_analizados += 1
                motion, hay = detector.process(frame_mov)
                if hay and not prev_hay:
                    disparos += 1
                prev_hay = hay
                if motion == 1:
                    n_frames_mov += 1

            # ---- Cruces de línea (ritual D) ----
            if args.ritual == "D":
                for det_linea, linea in zip(cruce_dets, lineas):
                    ts = (time.time() - t0)
                    for ev in det_linea.process(frame, ts):
                        cruces_detectados.append({
                            "linea": linea.line_id, "direccion": ev.direction,
                            "x": round(ev.x), "y": round(ev.y), "t": round(ev.timestamp, 1),
                        })

            # ---- Caras (rituales A, B, F) ----
            faces_info = []
            if usar_caras and n_frames % FACE_SAMPLE == 0:
                faces = analyze(frame, det_size=(det_size, det_size), min_score=args.min_score)
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

            # ---- Frame anotado ----
            ahora = time.time()
            restante = max(0, fin - ahora)
            fps_real = n_frames / max(0.001, ahora - t0)
            hud = [
                f"{titulo} · cam {args.camara_id} · quedan {restante:.0f}s",
                f"fps real: {fps_real:.1f}  |  frames: {n_frames}",
            ]
            if args.ritual in ("B", "C"):
                hud.append(f"disparos mov: {disparos}  |  frames con mov: {n_frames_mov}/{n_frames_analizados}")
            if usar_caras:
                hud.append(f"caras: {n_frames_cara} (racha {racha_max})")
            if args.ritual == "D":
                hud.append(f"cruces detectados: {len(cruces_detectados)} / {args.esperados}")
            hud.append("verde = cara aprovechable · ámbar = pequeña (SR) o borrosa")
            hud.append(instrucciones.get(args.ritual, ""))

            frame_anot = anotar_frame(frame.copy(), faces_info, hud, det_size)
            if args.ritual == "D" and lineas:
                for linea in lineas:
                    cv2.line(frame_anot, (int(linea.x1), int(linea.y1)),
                             (int(linea.x2), int(linea.y2)), CYAN, 2)
                for c in cruces_detectados:
                    cv2.circle(frame_anot, (int(c["x"]), int(c["y"])), 10, MAGENTA, 2)
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

        # ---- Recomendación por ritual ----
        if args.ritual == "A":
            actual_glob = {"RF_DET_SIZE": det_size, "RF_MIN_SHARPNESS": int(min_sharpness),
                           "RF_SR_EMBED_MIN_FACE": sr_embed}
            recomendaciones = recomendacion_ritual_a(obs_px, obs_sharp, actual_glob)
            resumen = recomendaciones.pop("_resumen", {})
            _merge_reco(ruta, args.camara_id, "A", recomendaciones=recomendaciones)
        elif args.ritual == "B":
            actual_cam = {"fps": fps_actual, "sensibilidad": sens_actual}
            por_camara = recomendacion_ritual_b(fps_real, n_frames_cara, racha_max,
                                                disparos, actual_cam)
            resumen = por_camara.pop("_resumen", {})
            recomendaciones = por_camara
            _merge_reco(ruta, args.camara_id, "B", por_camara=por_camara)
        elif args.ritual == "C":
            metricas = {"disparos": disparos, "n_frames": n_frames,
                        "n_frames_mov": n_frames_mov, "n_analizados": n_frames_analizados,
                        "pct_mov": round(100.0 * n_frames_mov / max(1, n_frames_analizados), 1)}
            reco_file = _reco_path(ruta, args.camara_id)
            prev = _leer_json(reco_file) or {}
            fases = dict(prev.get("c_fases") or {})
            fases[args.fase] = metricas
            por_camara, glob, motivo = _ajuste_c(fases, {"dontCare": dc_actual,
                                                         "porcentaje_mov": porc_actual,
                                                         "threshold": get_int(ruta, "RF_MOV_THRESHOLD", 21)})
            recomendaciones = por_camara
            resumen = {"fase": args.fase, **metricas, "ajuste": motivo,
                       "fases_pendientes": [f for f in ("c1", "c2") if f not in fases]}
            _merge_reco(ruta, args.camara_id, "C", recomendaciones=glob,
                        por_camara=por_camara, extra={"c_fases": fases})
            recomendaciones = dict(glob)
            recomendaciones.update(por_camara)
        elif args.ritual == "D":
            if not lineas:
                raise RuntimeError("la cámara no tiene líneas trazadas (pestaña Líneas)")
            recomendaciones = recomendacion_ritual_d(args.esperados, len(cruces_detectados),
                                                     cruce_cfg.area_min)
            resumen = {"esperados": args.esperados, "detectados": len(cruces_detectados),
                       "area_min_actual": cruce_cfg.area_min,
                       "cruces": cruces_detectados}
            _merge_reco(ruta, args.camara_id, "D", recomendaciones=recomendaciones)
        else:  # F
            actual_glob = {"RF_DET_SIZE": det_size, "RF_MIN_SHARPNESS": int(min_sharpness),
                           "RF_SR_EMBED_MIN_FACE": sr_embed}
            recomendaciones = recomendacion_ritual_f(obs_px, obs_sharp, actual_glob)
            resumen = recomendaciones.pop("_resumen", {})
            _merge_reco(ruta, args.camara_id, "F", recomendaciones=recomendaciones)

        resultado = {
            "camara_id": args.camara_id, "ritual": args.ritual, "estado": "ok",
            "job": args.job_id, "timestamp": datetime.now().isoformat(timespec="seconds"),
            "duracion_s": round(duracion, 1), "fps_real": round(fps_real, 1),
            "frames": n_frames, "det_size_usado": det_size,
            "resumen": resumen, "recomendaciones": recomendaciones,
        }
        if args.ritual == "C":
            resultado["fase"] = args.fase
        if args.ritual == "D":
            resultado["esperados"] = args.esperados
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
