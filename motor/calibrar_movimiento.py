#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Calibración de los parámetros de DETECCIÓN DE MOVIMIENTO — motor/calibrar_movimiento.py

Fundamento: los falsos negativos del disparo de movimiento son invisibles aguas
abajo (sin clip no hay caras/cruces que lo delaten), así que la calibración se
hace OFFLINE reproduciendo vídeos reales a través del MISMO MotionDetector que
usa el worker de captura (motor/core/motion.py).

Fase 2 (2026-08-20):
  - Barrido conjunto de `redimesionframe` (--resizes) con `dontCare`: el área
    mínima se mide sobre el frame REDIMENSIONADO, así que ambos se calibran a
    la vez (desacopla dontCare de la escala del frame).
  - --camara N + --ruta: escribe la recomendación en
    motor/calibrador/recomendaciones/<N>.json (por_camara) para que los badges
    del panel (La Forja · Templar · Editar) la muestren.

Datos (preparar a mano una vez):
  - Positivos  (--positivos): MP4 de movimiento ya archivados (movimiento
    confirmado; p. ej. copiar algunos de motor/videos_archivo/<local>/<cam>/).
  - Negativos  (--negativos): grabaciones de escena vacía SIN movimiento
    (horas valle). Obtenerlas, p. ej. con ffmpeg:
      ffmpeg -rtsp_transport tcp -i "rtsp://usuario:pass@camara/..." \
             -t 900 -an -c copy motor/calib_mov/negativos/vacio1.mp4

Métricas por configuración:
  - recall   = % de positivos que disparan (>= frames_con_movimiento).
  - ttt      = tiempo medio hasta el 1er disparo (s) en los positivos.
  - falsos/h = transiciones no-hay -> hay en los negativos, extrapoladas a 1 h.

Salida: ranking (Pareto recall vs falsos/h) sobre un barrido de parámetros y un
bloque .env recomendado para los knobs GLOBALES (RF_MOV_*). NADA se aplica
automáticamente: un humano revisa antes (anti-drift, mismo criterio que
core/calibration.py valida en held-out antes de desplegar).

Nota: los MP4 archivados se escriben a 10 fps (VideoConfig.fps), por eso el ttt
se calcula con FPS_ARCHIVO=10 aunque el worker muestree a 14.

Uso:
    motor/venv/bin/python motor/calibrar_movimiento.py \
        --positivos motor/calib_mov/positivos \
        --negativos  motor/calib_mov/negativos \
        [--thresholds 18,21,24] [--dilates 1,2] [--dontcares 180,220,260] \
        [--porcentajes 50,60,70] [--segundos 2] [--fps 14] [--resizes 50,60,70] \
        [--max-frames 600] [--camara 13] [--ruta /root/reconocimientoFacial] \
        [--out motor/calib/calib_movimiento.json]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import cv2  # noqa: E402

from motor.core.motion import MotionConfig, MotionDetector  # noqa: E402

FPS_ARCHIVO = 10.0   # fps al que se escriben los MP4 archivados (VideoConfig.fps)


def _parse_csv(val: str, tipo=float):
    return [tipo(x) for x in val.split(",") if x.strip() != ""]


def combos(args) -> list[tuple[float, MotionConfig]]:
    """Barrido (resize_pct, MotionConfig): redimesionframe y dontCare juntos,
    porque dontCare se mide sobre el frame ya redimensionado."""
    out = []
    for rp in _parse_csv(args.resizes, float):
        for thr in _parse_csv(args.thresholds, int):
            for dil in _parse_csv(args.dilates, int):
                for dc in _parse_csv(args.dontcares, int):
                    for pm in _parse_csv(args.porcentajes, int):
                        out.append((rp, MotionConfig(
                            segundos_analizar=args.segundos,
                            porcentaje_mov=pm,
                            dontCare=dc,
                            fps=args.fps,
                            sensibilidad=1,
                            threshold=thr,
                            blur=args.blur,
                            dilate=dil,
                        )))
    return out


def _frames(path: str, resize: float, max_frames: int):
    """Generador: frames BGR ya redimensionados del vídeo (None si no abre)."""
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        return None
    n = 0
    while n < max_frames:
        ret, frame = cap.read()
        if not ret or frame is None:
            break
        yield cv2.resize(frame, None, fx=resize, fy=resize)
        n += 1
    cap.release()


def evaluar_positivos(paths, combos: list[tuple[float, MotionConfig]], max_frames) -> dict:
    """Por índice de combo: {trigger, ttt_sum, n, dur_sum} (ttt en segundos)."""
    res = [{"trigger": 0, "ttt_sum": 0.0, "n": 0, "dur_sum": 0.0} for _ in combos]
    for path in paths:
        for i, (rp, cfg) in enumerate(combos):
            gen = _frames(path, rp / 100.0, max_frames)
            if gen is None:
                print(f"  ! no se pudo abrir positivo: {path}", flush=True)
                continue
            det = MotionDetector(cfg)
            ttt = None
            idx = 0
            dur = 0.0
            for frame in gen:
                dur += 1.0 / FPS_ARCHIVO
                motion, hay = det.process(frame)
                if ttt is None and hay:
                    ttt = idx / FPS_ARCHIVO
                    break
                idx += 1
            res[i]["n"] += 1
            res[i]["dur_sum"] += dur
            if ttt is not None:
                res[i]["trigger"] += 1
                res[i]["ttt_sum"] += ttt
            else:
                # no disparó: cuenta como tiempo máximo (penalización de recall)
                res[i]["ttt_sum"] += dur
    return res


def evaluar_negativos(paths, combos: list[tuple[float, MotionConfig]], max_frames) -> dict:
    """Por índice de combo: {transiciones, dur_h} (falsos disparos por hora)."""
    res = [{"transiciones": 0, "dur_h": 0.0} for _ in combos]
    for path in paths:
        for i, (rp, cfg) in enumerate(combos):
            gen = _frames(path, rp / 100.0, max_frames)
            if gen is None:
                print(f"  ! no se pudo abrir negativo: {path}", flush=True)
                continue
            det = MotionDetector(cfg)
            prev_hay = False
            dur = 0.0
            for frame in gen:
                dur += 1.0 / FPS_ARCHIVO
                motion, hay = det.process(frame)
                if hay and not prev_hay:
                    res[i]["transiciones"] += 1
                prev_hay = hay
            res[i]["dur_h"] += dur / 3600.0
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--positivos", required=True)
    ap.add_argument("--negativos", required=True)
    ap.add_argument("--thresholds", default="18,21,24")
    ap.add_argument("--blur", type=int, default=21)
    ap.add_argument("--dilates", default="1,2")
    ap.add_argument("--dontcares", default="180,220,260")
    ap.add_argument("--porcentajes", default="50,60,70")
    ap.add_argument("--segundos", type=int, default=2)
    ap.add_argument("--fps", type=int, default=14)
    ap.add_argument("--resizes", default="50,60,70",
                    help="redimesionframe (%) a barrer JUNTO a dontCare (el área mínima se mide sobre el frame redimensionado)")
    ap.add_argument("--resize", type=float, default=None,
                    help="(deprecado) uso fijo de resize; usar --resizes")
    ap.add_argument("--max-frames", type=int, default=600)
    ap.add_argument("--camara", type=int, default=0,
                    help="si >0, escribe la recomendación en motor/calibrador/recomendaciones/<camara>.json")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    if args.resize is not None:
        args.resizes = str(args.resize * 100.0)

    combos_l = combos(args)
    print(f"barrido: {len(combos_l)} configuraciones (incluye {len(_parse_csv(args.resizes, float))} resizes)")

    def _videos(d):
        return sorted(
            os.path.join(d, f) for f in os.listdir(d)
            if f.lower().endswith((".mp4", ".avi"))) if os.path.isdir(d) else []

    pos_paths = _videos(args.positivos)
    neg_paths = _videos(args.negativos)
    print(f"positivos: {len(pos_paths)}  negativos: {len(neg_paths)}")
    if not pos_paths or not neg_paths:
        print("ERROR: se necesitan al menos 1 positivo y 1 negativo (.mp4/.avi)")
        return 1

    pos = evaluar_positivos(pos_paths, combos_l, args.max_frames)
    neg = evaluar_negativos(neg_paths, combos_l, args.max_frames)

    filas = []
    for i, (rp, cfg) in enumerate(combos_l):
        p = pos[i]
        n = neg[i]
        recall = p["trigger"] / p["n"] if p["n"] else 0.0
        ttt = p["ttt_sum"] / p["n"] if p["n"] else 0.0
        far = n["transiciones"] / n["dur_h"] if n["dur_h"] > 0 else 0.0
        filas.append({
            "resize": rp, "cfg": cfg, "recall": recall, "ttt_s": round(ttt, 2), "far_h": round(far, 1),
        })
    # Pareto: recall desc, far asc, ttt asc
    filas.sort(key=lambda r: (-r["recall"], r["far_h"], r["ttt_s"]))

    print("\n=== Ranking (recall | falsos/h | ttt_s | params) ===")
    for r in filas[:10]:
        c = r["cfg"]
        print(f"  recall={r['recall']:.2f}  far={r['far_h']:.1f}/h  ttt={r['ttt_s']:.1f}s  "
              f"resize={r['resize']:.0f}% thr={c.threshold} blur={c.blur} dil={c.dilate} "
              f"dontCare={c.dontCare} porc={c.porcentaje_mov} seg={c.segundos_analizar}")

    mejor = filas[0]
    c = mejor["cfg"]
    print("\n=== .env recomendado (REVISAR ANTES DE APLICAR) ===")
    print(f"RF_MOV_THRESHOLD={c.threshold}")
    print(f"RF_MOV_BLUR={c.blur}")
    print(f"RF_MOV_DILATE={c.dilate}")
    print("# per-cámara (panel La Forja): "
          f"redimesionframe={mejor['resize']:.0f}  dontCare={c.dontCare}  "
          f"porcentaje_mov={c.porcentaje_mov}  segundos_analizar={c.segundos_analizar}  "
          f"fps={c.fps}  sensibilidad=1")

    # Recomendación por cámara para el panel (badges de Templar · Editar)
    if args.camara > 0:
        reco = {
            "camara_id": args.camara,
            "actualizados": datetime.now().isoformat(timespec="seconds"),
            "ritual": "sweep_movimiento",
            "recomendaciones": {
                "RF_MOV_THRESHOLD": {"actual": None, "recomendado": c.threshold,
                                     "motivo": "Barrido offline: mejor recall/falsos-h."},
                "RF_MOV_BLUR": {"actual": None, "recomendado": c.blur,
                                "motivo": "Barrido offline: kernel de blur del mejor combo."},
                "RF_MOV_DILATE": {"actual": None, "recomendado": c.dilate,
                                  "motivo": "Barrido offline: dilate del mejor combo."},
            },
            "por_camara": {
                "redimesionframe": {"actual": None, "recomendado": int(round(mejor["resize"])),
                                    "motivo": "Barrido offline: escala del frame del mejor combo "
                                              "(desacoplado de dontCare)."},
                "dontCare": {"actual": None, "recomendado": c.dontCare,
                             "motivo": "Barrido offline: área mínima del mejor combo (sobre el frame "
                                       f"redimensionado a {mejor['resize']:.0f}%)."},
                "porcentaje_mov": {"actual": None, "recomendado": c.porcentaje_mov,
                                   "motivo": "Barrido offline: % de frames con movimiento del mejor combo."},
                "segundos_analizar": {"actual": None, "recomendado": c.segundos_analizar,
                                      "motivo": "Barrido offline: ventana de decisión del mejor combo."},
                "fps": {"actual": None, "recomendado": c.fps,
                        "motivo": "Cadencia del mejor combo (ajustable después con el ritual B)."},
            },
        }
        reco_dir = os.path.join(args.ruta, "motor/calibrador/recomendaciones")
        os.makedirs(reco_dir, exist_ok=True)
        with open(os.path.join(reco_dir, str(args.camara) + ".json"), "w") as fh:
            json.dump(reco, fh, indent=2, ensure_ascii=False)
        print(f"\nRecomendación por cámara escrita en motor/calibrador/recomendaciones/{args.camara}.json")

    if args.out:
        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w") as fh:
            json.dump({
                "ranking": [{
                    "resize": r["resize"], "threshold": r["cfg"].threshold, "blur": r["cfg"].blur,
                    "dilate": r["cfg"].dilate, "dontCare": r["cfg"].dontCare,
                    "porcentaje_mov": r["cfg"].porcentaje_mov,
                    "segundos_analizar": r["cfg"].segundos_analizar,
                    "fps": r["cfg"].fps, "recall": r["recall"],
                    "ttt_s": r["ttt_s"], "far_h": r["far_h"],
                } for r in filas],
            }, fh, indent=2, ensure_ascii=False)
        print(f"\nJSON completo en {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
