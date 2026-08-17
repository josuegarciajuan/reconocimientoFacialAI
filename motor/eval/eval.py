#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Harness de evaluación TAR/FAR — motor/eval.

Mide la precisión del embedding (ArcFace, buffalo_l) sobre un set etiquetado:

    motor/eval/data/
        <persona_id>/
            <nombre>_<pose>.jpg|png      (pose opcional)

Sufijos de pose reconocidos (opcional):
    _f    frente          _pi   perfil izq (90°)   _pd  perfil der (90°)
    _m45i 45° izq         _m45d 45° der            _arr arriba   _aba abajo

Reporta:
  - TAR (tasa de acierto) a FAR = 1% (y 0.1%, 5%) — global
  - TAR frontal↔perfil (pares genuinos frente vs _pi/_pd)
  - umbrales operativos sugeridos

Uso:
  motor/venv/bin/python -m motor.eval.eval --data-dir motor/eval/data

Requiere venv (insightface/onnxruntime). Caché de embeddings en motor/eval/.cache
para no re-encodear en cada ejecución.
"""
from __future__ import annotations

import argparse
import os
import pickle
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

POSE_FRONTAL = {"f"}
POSE_PERFIL = {"pi", "pd"}
POSE_SUFIJOS = {"f", "pi", "pd", "m45i", "m45d", "arr", "aba"}


def parse_pose(name: str) -> str | None:
    """Devuelve el sufijo de pose si el fichero lo lleva (último _sufijo)."""
    stem = Path(name).stem
    for suf in sorted(POSE_SUFIJOS, key=len, reverse=True):
        if stem.endswith("_" + suf):
            return suf
    return None


def embed_all(data_dir: Path, cache_file: Path, det_size: int = 640):
    """Embebe todas las imágenes del set etiquetado (con caché)."""
    from insightface.app import FaceAnalysis  # import tardío: requiere venv

    if cache_file.exists():
        with open(cache_file, "rb") as fh:
            cache = pickle.load(fh)
    else:
        cache = {}

    app = FaceAnalysis(name="buffalo_l", providers=["CPUExecutionProvider"])
    app.prepare(ctx_id=0, det_size=(det_size, det_size))

    import cv2

    entries = {}  # (persona, fichero) -> dict(embedding, pose)
    dirty = False
    for person_dir in sorted(data_dir.iterdir()):
        if not person_dir.is_dir():
            continue
        for img_file in sorted(person_dir.iterdir()):
            if img_file.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            key = f"{person_dir.name}/{img_file.name}"
            if key in cache and cache[key] is not None:
                entries[key] = cache[key]
                continue
            img = cv2.imread(str(img_file))
            if img is None:
                print(f"[skip] no se puede leer: {img_file}")
                continue
            faces = app.get(img)
            if not faces:
                print(f"[skip] sin cara: {img_file}")
                continue
            # nos quedamos con la detección de mayor confianza
            best = max(faces, key=lambda f: f.det_score)
            entry = {
                "persona": person_dir.name,
                "file": img_file.name,
                "embedding": np.asarray(best.normed_embedding, dtype=np.float32),
                "pose": parse_pose(img_file.name),
            }
            cache[key] = entry
            entries[key] = entry
            dirty = True

    if dirty:
        with open(cache_file, "wb") as fh:
            pickle.dump(cache, fh)
    return list(entries.values())


def cos_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Similitud coseno (embedding ya L2-normalizado)."""
    return float(np.dot(a, b))


def tar_at_far(genuine: np.ndarray, impostor: np.ndarray, far_target: float) -> tuple[float, float]:
    """Devuelve (TAR, umbral) para un FAR objetivo dado."""
    if impostor.size == 0:
        return float("nan"), float("nan")
    umbral = float(np.percentile(impostor, 100 * (1 - far_target)))
    tar = float(np.mean(genuine >= umbral)) if genuine.size else float("nan")
    return tar, umbral


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluación TAR/FAR del motor")
    parser.add_argument("--data-dir", default=os.path.join(os.path.dirname(__file__), "data"))
    parser.add_argument("--det-size", type=int, default=640)
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        print(f"ERROR: no existe {data_dir}. Crea el set etiquetado (ver motor/eval/README.md).")
        return 1

    cache_file = Path(args.data_dir).parent / ".cache_eval.pkl"
    entries = embed_all(data_dir, cache_file, args.det_size)
    if len(entries) < 2:
        print(f"ERROR: se necesitan >=2 imágenes etiquetadas (hay {len(entries)}).")
        return 1

    personas = defaultdict(list)
    for e in entries:
        personas[e["persona"]].append(e)

    # pares genuinos e impostores (coseno)
    genuine, impostor = [], []
    gen_fp = []  # genuinos frontal↔perfil
    n_personas = len(personas)
    keys = list(personas.keys())
    for i in range(n_personas):
        for j in range(i + 1, n_personas):
            for a in personas[keys[i]]:
                for b in personas[keys[j]]:
                    impostor.append(cos_sim(a["embedding"], b["embedding"]))
    for k in keys:
        for i, a in enumerate(personas[k]):
            for b in personas[k][i + 1:]:
                s = cos_sim(a["embedding"], b["embedding"])
                genuine.append(s)
                if a["pose"] in POSE_FRONTAL and b["pose"] in POSE_PERFIL:
                    gen_fp.append(s)
                if b["pose"] in POSE_FRONTAL and a["pose"] in POSE_PERFIL:
                    gen_fp.append(s)

    genuine = np.array(genuine)
    impostor = np.array(impostor)
    gen_fp = np.array(gen_fp)

    print("=" * 60)
    print("MÉTRICAS DE PRECISIÓN (embedding ArcFace buffalo_l)")
    print("=" * 60)
    print(f"personas: {n_personas}  imágenes: {len(entries)}")
    print(f"pares genuinos: {len(genuine)}  impostores: {len(impostor)}  (frente↔perfil: {len(gen_fp)})")
    if len(genuine) == 0:
        print("[aviso] 0 pares genuinos: necesitas >=2 imágenes por persona para TAR.")
    if len(impostor) == 0:
        print("[aviso] 0 pares impostores: necesitas >=2 personas para FAR.")
    print()
    for far in (0.001, 0.01, 0.05):
        tar, umbral = tar_at_far(genuine, impostor, far)
        print(f"FAR={far*100:.1f}%  ->  TAR={tar*100:.1f}%  (umbral coseno >= {umbral:.4f})")
    print()
    if len(gen_fp):
        tar_fp, umbral_fp = tar_at_far(gen_fp, impostor, 0.01)
        print(f"[frontal↔perfil] TAR={tar_fp*100:.1f}% a FAR=1% (umbral >= {umbral_fp:.4f})")
    print()
    if len(genuine):
        print(f"similitud media genuina : {genuine.mean():.4f}  (p25={np.percentile(genuine,25):.4f})")
    if len(impostor):
        print(f"similitud media impostora: {impostor.mean():.4f}  (p95={np.percentile(impostor,95):.4f})")
    print()
    if len(genuine) and len(impostor):
        print("Interpretación: TAR a FAR=1% es la tasa de acierto operativa (objetivo NFR-ACC: >=95%).")
    else:
        print("Interpretación: faltan pares (ver avisos). Puebla motor/eval/data con 3+ personas x 2+ poses.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
