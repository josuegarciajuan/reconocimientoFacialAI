#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonda de CALIDAD de imagen sobre vídeos archivados — motor/quality_probe.py

Herramienta OFFLINE (solo lectura de vídeos, sin BD ni galería) para decidir si
el pipeline actual y las variantes de super-resolución (MF-SR, x4plus, GFPGAN)
dan una calidad de cara aceptable partiendo de la captura real.

Motivación: en producción las cámaras son gran angular y las caras ocupan
~17-26 px en el fotograma 1080p; el clasificador las marca `low_quality`. Antes
de resetear datos o reprocesar, esta sonda genera tiras comparativas por cara:

  - ORIG : el contexto nativo de la cara (vecino más próximo, para ver la señal
           real capturada, sin inventar píxeles).
  - A    : pipeline actual (1 frame, `sr_model`, restauración según cfg).
  - B    : MF-SR (fusión de hasta k frames, `sr_model`).
  - C    : MF-SR (fusión, `sr_model_photo` = x4plus por defecto).
  - D    : MF-SR + restauración facial forzada (GFPGAN aunque la cara sea <
           `face_restore_min_side`).

Salida: `motor/quality_probe/<ts>/` con una tira por cara + `informe.csv` +
`resumen.json`. Directorio de DATOS (gitignored): git = código, no datos.

Uso:
    motor/venv/bin/python motor/quality_probe.py 1 --ruta . \
        --max-faces 20 --k 6 --face-every 1 [--cam 16] [--limit-videos 8]
"""
from __future__ import annotations

import argparse
import copy
import csv
import json
import os
import sys
import time

import cv2
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config            # noqa: E402
from motor.core.model import analyze            # noqa: E402
from motor.core.quality import face_sharpness   # noqa: E402
from motor.core.superres import photo_busto, photo_busto_fused  # noqa: E402


def quality_label(face_side: int) -> str:
    """Misma etiqueta que motor/core/image_provenance.py (contrato del panel)."""
    return "insufficient" if face_side < 32 else ("limited" if face_side < 64 else "usable")


def _context_crop(frame: np.ndarray, bbox):
    """Recorte de contexto (busto) alrededor de la cara + bbox en coordenadas del recorte.

    Se guarda el recorte (no el frame completo) para no retener 6 MB por frame:
    el busto real tiene suficiente contexto para `photo_busto`/`photo_busto_fused`,
    que solo necesitan la región cabeza-hombros. Devuelve (crop, bbox_local) o
    (None, None) si el recorte es inválido.
    """
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = (int(round(v)) for v in bbox)
    fw, fh = max(1, x2 - x1), max(1, y2 - y1)
    cx = (x1 + x2) // 2
    # ancho ~3.5x cara; alto ~5x cara con margen arriba (pelo) como busto_bbox.
    hw = int(1.75 * fw)
    top = int(1.5 * fh)
    bot = int(3.5 * fh)
    cx1, cx2 = max(0, cx - hw), min(w, cx + hw)
    cy1, cy2 = max(0, y1 - top), min(h, y2 + bot)
    crop = frame[cy1:cy2, cx1:cx2]
    if crop.size == 0:
        return None, None
    bx1 = max(0, x1 - cx1)
    by1 = max(0, y1 - cy1)
    bx2 = min(crop.shape[1], x2 - cx1)
    by2 = min(crop.shape[0], y2 - cy1)
    if bx2 - bx1 < 4 or by2 - by1 < 4:
        return None, None
    return crop, (bx1, by1, bx2, by2)


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))


class _Track:
    """Rastro de una cara a lo largo de un vídeo (para recolectar frames de MF-SR)."""

    __slots__ = ("emb", "last_frame", "crops", "sharp", "bbox_side")

    def __init__(self, emb, frame_idx):
        self.emb = emb
        self.last_frame = frame_idx
        self.crops = []          # [(crop, bbox_local)]
        self.sharp = 0.0
        self.bbox_side = 0


def _collect_tracks(video_path: str, cfg: Config, face_every: int, k: int,
                    cos_min: float, max_gap: int):
    """Recorre un vídeo y agrupa detecciones de la misma cara en `_Track`.

    Agrupación greedy por coseno de embedding + proximidad temporal. Cada track
    guarda hasta `k+1` recortes de contexto (el representativo por nitidez ×
    área no se decide aquí, se hace al final). Devuelve la lista de tracks.
    """
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return []
    tracks: list[_Track] = []
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % face_every == 0:
            faces = analyze(frame, det_size=(cfg.det_size, cfg.det_size),
                            min_score=cfg.capture_min_det_score)
            for f in faces:
                emb = np.asarray(f.embedding, dtype=np.float32)
                # emparejar con el track activo más parecido (misma cara)
                best, best_s = None, -1.0
                for tr in tracks:
                    if frame_idx - tr.last_frame > max_gap:
                        continue
                    s = _cos(emb, tr.emb)
                    if s > best_s:
                        best, best_s = tr, s
                if best is not None and best_s >= cos_min:
                    best.emb = emb
                    best.last_frame = frame_idx
                    crop, bbx = _context_crop(frame, f.bbox)
                    if crop is not None and len(best.crops) < k + 1:
                        best.crops.append((crop, bbx))
                        fw = f.bbox[2] - f.bbox[0]
                        fh = f.bbox[3] - f.bbox[1]
                        best.sharp = max(best.sharp, face_sharpness(frame, f))
                        best.bbox_side = max(best.bbox_side, int(max(fw, fh)))
                else:
                    tr = _Track(emb, frame_idx)
                    crop, bbx = _context_crop(frame, f.bbox)
                    if crop is not None:
                        tr.crops.append((crop, bbx))
                        fw = f.bbox[2] - f.bbox[0]
                        fh = f.bbox[3] - f.bbox[1]
                        tr.sharp = face_sharpness(frame, f)
                        tr.bbox_side = int(max(fw, fh))
                    tracks.append(tr)
        frame_idx += 1
    cap.release()
    return [t for t in tracks if t.crops]


def _pick_frames(track: _Track, k: int):
    """Ordena los recortes del track por nitidez desc y devuelve hasta `k` frames.

    El primero es el representativo (mejor nitidez × √área) para la ruta A; los
    k primeros alimentan la fusión MF-SR.
    """
    scored = []
    for crop, bbx in track.crops:
        fw = bbx[2] - bbx[0]
        fh = bbx[3] - bbx[1]
        # nitidez del recorte ya guardado: como es el mismo dominio que el frame,
        # sirve como criterio relativo entre frames del MISMO track.
        s = float(cv2.Laplacian(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY), cv2.CV_64F).var())
        scored.append((s * (float(fw * fh) ** 0.5), crop, bbx))
    scored.sort(key=lambda t: -t[0])
    return [(c, b) for _s, c, b in scored[:max(1, k)]]


def _strip(images, labels, height=360):
    """Compone una tira horizontal de imágenes con etiqueta encima de cada una."""
    tiles = []
    for img, lab in zip(images, labels):
        if img is None:
            continue
        h, w = img.shape[:2]
        if h <= 0 or w <= 0:
            continue
        s = height / float(h)
        tile = cv2.resize(img, (max(1, int(w * s)), height), interpolation=cv2.INTER_AREA)
        banner = np.full((28, tile.shape[1], 3), 30, dtype=np.uint8)
        cv2.putText(banner, lab, (6, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1,
                    cv2.LINE_AA)
        tiles.append(np.vstack([banner, tile]))
    if not tiles:
        return None
    hmax = max(t.shape[0] for t in tiles)
    padded = []
    for t in tiles:
        if t.shape[0] < hmax:
            pad = np.full((hmax - t.shape[0], t.shape[1], 3), 30, dtype=np.uint8)
            t = np.vstack([t, pad])
        padded.append(t)
    return np.hstack(padded)


def _render_variants(frames, cfg: Config, model: str, model_photo: str):
    """Genera (A, B, C, D) para una cara. Degradación segura: None si falla."""
    a = b = c = d = None
    ref_img, ref_bbox = frames[0]
    try:
        a = photo_busto(ref_img, ref_bbox, cfg, model=model, restore=True)
    except Exception:  # noqa: BLE001
        a = None
    if len(frames) >= 2:
        try:
            b = photo_busto_fused(frames, cfg, model=model, restore=True)
        except Exception:  # noqa: BLE001
            b = None
        try:
            c = photo_busto_fused(frames, cfg, model=model_photo, restore=True)
        except Exception:  # noqa: BLE001
            c = None
        cfg_d = copy.copy(cfg)
        cfg_d.face_restore_min_side = 0
        try:
            d = photo_busto_fused(frames, cfg_d, model=model_photo, restore=True)
        except Exception:  # noqa: BLE001
            d = None
    return a, b, c, d


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--face-every", type=int, default=1, help="muestreo de frames (1 = todos)")
    ap.add_argument("--k", type=int, default=6, help="máx frames a fusionar (MF-SR)")
    ap.add_argument("--cos", type=float, default=0.45, help="coseno mínimo para el mismo track")
    ap.add_argument("--max-gap", type=int, default=30, help="hueco máx de frames dentro de un track")
    ap.add_argument("--max-faces", type=int, default=20, help="nº máx de caras a comparar")
    ap.add_argument("--limit-videos", type=int, default=0, help="0 = todos los vídeos archivados")
    ap.add_argument("--cam", default="", help="filtrar por cámara")
    ap.add_argument("--out", default="", help="directorio de salida (def: motor/quality_probe/<ts>)")
    args = ap.parse_args()

    from motor.core.threads import limit_threads
    limit_threads()

    cfg = Config.from_env(args.ruta)
    base = os.path.join(args.ruta, "motor/videos_archivo", str(args.local_id))
    if not os.path.isdir(base):
        print(f"sin vídeos archivados en {base}", flush=True)
        return 1

    out_dir = args.out or os.path.join(args.ruta, "motor/quality_probe",
                                       time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(out_dir, exist_ok=True)

    vids = []
    for cam in sorted(os.listdir(base)):
        if args.cam and cam != str(args.cam):
            continue
        cdir = os.path.join(base, cam)
        if not os.path.isdir(cdir):
            continue
        for f in sorted(os.listdir(cdir)):
            if f.lower().endswith(".mp4"):
                vids.append((cam, os.path.join(cdir, f), f))
    if args.limit_videos > 0:
        vids = vids[:args.limit_videos]
    print(f"[probe] {len(vids)} vídeo(s) | face_every={args.face_every} k={args.k} "
          f"max_faces={args.max_faces}", flush=True)

    rows = []
    sizes = []
    n_faces = 0
    for cam, vpath, vfile in vids:
        if n_faces >= args.max_faces:
            break
        try:
            tracks = _collect_tracks(vpath, cfg, args.face_every, args.k,
                                     args.cos, args.max_gap)
        except Exception as e:  # noqa: BLE001
            print(f"  [skip] {vfile}: {e}", flush=True)
            continue
        # ordenar tracks por nitidez×área desc para quedarnos con las mejores caras
        tracks.sort(key=lambda t: -(t.sharp * (t.bbox_side ** 0.5)))
        for ti, tr in enumerate(tracks):
            if n_faces >= args.max_faces:
                break
            frames = _pick_frames(tr, args.k)
            if not frames:
                continue
            a, b, c, d = _render_variants(frames, cfg, cfg.sr_model, cfg.sr_model_photo)
            side = tr.bbox_side
            sizes.append(side)
            ref_img, ref_bbox = frames[0]
            orig = ref_img[ref_bbox[1]:ref_bbox[3], ref_bbox[0]:ref_bbox[2]]
            orig_big = cv2.resize(orig, (orig.shape[1] * 4, orig.shape[0] * 4),
                                  interpolation=cv2.INTER_NEAREST) if orig.size else None
            strip = _strip([orig_big, a, b, c, d],
                           ["ORIG x4 (real)", "A: actual", f"B: MF-SR({len(frames)})",
                            "C: MF-SR x4plus", "D: MF-SR x4plus+GFPGAN"])
            if strip is None:
                continue
            name = f"{n_faces:03d}_{cam}_{os.path.splitext(vfile)[0][:28]}.jpg"
            cv2.imwrite(os.path.join(out_dir, name), strip, [cv2.IMWRITE_JPEG_QUALITY, 92])
            rows.append({
                "idx": n_faces, "cam": cam, "video": vfile, "track": ti,
                "face_side": side, "quality": quality_label(side),
                "n_frames": len(frames),
                "a_w": (a.shape[1] if a is not None else 0),
                "b_w": (b.shape[1] if b is not None else 0),
                "c_w": (c.shape[1] if c is not None else 0),
                "d_w": (d.shape[1] if d is not None else 0),
                "file": name,
            })
            n_faces += 1
            print(f"  [{n_faces}] cam {cam} {vfile[:26]} cara {side}px "
                  f"({len(frames)} frames) -> {name}", flush=True)

    csv_path = os.path.join(out_dir, "informe.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()) if rows else
                           ["idx", "cam", "video", "track", "face_side", "quality",
                            "n_frames", "a_w", "b_w", "c_w", "d_w", "file"])
        w.writeheader()
        w.writerows(rows)

    a_sizes = np.array(sizes) if sizes else np.array([0])
    resumen = {
        "n_caras": len(rows),
        "face_side_min": int(a_sizes.min()) if sizes else None,
        "face_side_p50": float(np.median(a_sizes)) if sizes else None,
        "face_side_max": int(a_sizes.max()) if sizes else None,
        "quality": {q: int(sum(1 for r in rows if r["quality"] == q))
                    for q in ("insufficient", "limited", "usable")},
        "video_sizes": {int(s): int((a_sizes == s).sum()) for s in sorted(set(int(x) for x in sizes))}
        if sizes else {},
        "out_dir": out_dir,
    }
    with open(os.path.join(out_dir, "resumen.json"), "w", encoding="utf-8") as fh:
        json.dump(resumen, fh, ensure_ascii=False, indent=2)

    print(f"\n[probe] caras comparadas: {len(rows)} | calidad: {resumen['quality']}")
    print(f"[probe] salida: {out_dir}")
    print(f"[probe] CSV: {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
