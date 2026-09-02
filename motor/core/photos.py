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
import shutil
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

    Fase 2: la prioridad es el REGISTRO DE RETRATOS (`motor/portraits/<local>/<cod>/`),
    una copia inmune a la ingesta/limpieza que el clasificador actualiza en cada
    decisión. Las capas VLM/OpenAI/silueta leen SIEMPRE de aquí para tener foto
    del candidato en el instante de decidir (antes dependían de `motor/caras`,
    que el ingestor vacía, y de `admin/caras_procesadas`, que no siempre existe).
    Después: `motor/caras/<local>/<cam>/<persona>/` y, en último lugar, BD.
    """
    # 1) registro de retratos persistente
    portraits = _portraits_dir(ruta, local_id, person_cod)
    if os.path.isdir(portraits):
        try:
            files = sorted(os.listdir(portraits), key=lambda f: os.path.getmtime(os.path.join(portraits, f)),
                           reverse=True)
        except OSError:
            files = []
        out = [os.path.join(portraits, f) for f in files
               if f.lower().endswith((".jpg", ".jpeg", ".png"))][:max_n]
        if out:
            return out
    # 2) motor/caras (contrato del clasificador)
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

    # 3) fallback BD: admin/caras_procesadas/<foto_id>.jpg (más recientes primero)
    return find_person_photos_db(ruta, local_id, person_cod, max_n=max_n)


def _portraits_dir(ruta: str, local_id: str, person_cod: str) -> str:
    return os.path.join(ruta, "motor/portraits", str(local_id), str(person_cod))


def save_portrait(ruta: str, local_id: str, person_cod: str, pose: str,
                  foto_id: str, tight_path: str | None,
                  busto_path: str | None) -> None:
    """Copia la mejor cara y busto de una decisión al registro de retratos.

    El registro es inmune a la ingesta/limpieza: garantiza que las capas
    VLM/OpenAI/silueta tengan foto del candidato en el instante de decidir.
    Se guarda una entrada por (pose, foto_id) para no duplicar.
    """
    if not person_cod:
        return
    d = _portraits_dir(ruta, local_id, person_cod)
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        return
    pose_s = pose or "other"
    for label, src in (("cara", tight_path), ("busto", busto_path)):
        if not src or not os.path.exists(src):
            continue
        ext = os.path.splitext(src)[1].lower() or ".jpg"
        dst = os.path.join(d, f"{pose_s}_{label}_{foto_id}{ext}")
        try:
            if os.path.exists(dst):
                continue
            shutil.copy2(src, dst)
        except OSError:
            continue


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

