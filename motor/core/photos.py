"""Localiza fotos representativas de una persona en disco (para las capas L1c/L2/L3).

La galería `face_enc_v2` guarda embeddings, no imágenes. Las capas de zonas (L1c)
y VLM/OpenAI (L2/L3) necesitan la FOTO real de la persona candidata para comparar.
Las fotos viven en:
  - `motor/caras/<local>/<cam>/<persona>/*.jpg` (contrato del clasificador), y
  - `admin/caras_procesadas/<foto_id>.jpg` con el mapeo identidad en BD
    (fotos -> estancias -> personas) — usado por re-matching/backfill cuando
    las carpetas de `motor/caras` están vacías.
"""
from __future__ import annotations

import os
import subprocess

from .env import load_env


def _mysql(ruta: str, sql: str) -> list[str]:
    env = load_env(ruta)
    cmd = ["mysql", "-u", env.get("RF_DB_USER", "root"), "-p" + env.get("RF_DB_PASS", ""),
           "-h", env.get("RF_DB_HOST", "localhost"), env.get("RF_DB_NAME", "reconocimientofacial"),
           "-N", "-e", sql]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"mysql error: {out.stderr.strip()}")
    return [l for l in out.stdout.strip().splitlines() if l.strip()]


def find_person_photos(ruta: str, local_id: str, person_cod: str,
                       max_n: int = 3) -> list[str]:
    """Devuelve las N fotos más recientes de la persona (por mtime, descendente).

    Primero busca en `motor/caras/<local>/<cam>/<persona>/` (contrato del
    clasificador); si no hay nada (p.ej. galería histórica con carpetas vacías),
    resuelve las fotos desde la BD: fotos -> estancias -> personas, con las
    imágenes en `admin/caras_procesadas/<foto_id>.jpg`.
    """
    base = os.path.join(ruta, "motor/caras", str(local_id))
    found: list[tuple[float, str]] = []
    if os.path.isdir(base):
        try:
            cams = sorted(os.listdir(base))
        except OSError:
            cams = []
        for cam in cams:
            pdir = os.path.join(base, cam, person_cod)
            if not os.path.isdir(pdir):
                continue
            try:
                for f in os.listdir(pdir):
                    if f.lower().endswith((".jpg", ".jpeg", ".png")):
                        p = os.path.join(pdir, f)
                        try:
                            found.append((os.path.getmtime(p), p))
                        except OSError:
                            continue
            except OSError:
                continue
    found.sort(reverse=True)
    if found:
        return [p for _, p in found[:max_n]]

    # fallback BD: admin/caras_procesadas/<foto_id>.jpg (más recientes primero)
    return find_person_photos_db(ruta, local_id, person_cod, max_n=max_n)


def find_person_photos_db(ruta: str, local_id: str, person_cod: str,
                          max_n: int = 3) -> list[str]:
    """Fotos de la persona vía BD (fotos -> estancias -> personas).

    Devuelve rutas a `admin/caras_procesadas/<foto_id>.jpg` que existen en disco,
    ordenadas por id descendente (las más recientes).
    """
    fotos_dir = os.path.join(ruta, "admin/caras_procesadas")
    try:
        rows = _mysql(ruta,
            "SELECT f.id FROM fotos f JOIN estancias e ON e.id=f.estancia_id "
            "JOIN personas p ON p.id=e.persona_id "
            f"WHERE p.local_id={int(local_id)} AND p.cod_interno='{person_cod}' "
            "ORDER BY f.id DESC")
    except RuntimeError:
        return []
    out = []
    for r in rows:
        p = os.path.join(fotos_dir, r.strip() + ".jpg")
        if os.path.exists(p):
            out.append(p)
        if len(out) >= max_n:
            break
    return out

