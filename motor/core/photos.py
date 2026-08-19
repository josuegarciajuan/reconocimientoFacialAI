"""Localiza fotos representativas de una persona en disco (para las capas L1c/L2/L3).

La galería `face_enc_v2` guarda embeddings, no imágenes. Las capas de zonas (L1c)
y VLM/OpenAI (L2/L3) necesitan la FOTO real de la persona candidata para comparar.
Las fotos viven en `motor/caras/<local>/<cam>/<persona>/*.jpg` (contrato de nombres
del clasificador).
"""
from __future__ import annotations

import os


def find_person_photos(ruta: str, local_id: str, person_cod: str,
                       max_n: int = 3) -> list[str]:
    """Devuelve las N fotos más recientes de la persona (por mtime, descendente)."""
    base = os.path.join(ruta, "motor/caras", str(local_id))
    found: list[tuple[float, str]] = []
    if not os.path.isdir(base):
        return []
    try:
        cams = sorted(os.listdir(base))
    except OSError:
        return []
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
    return [p for _, p in found[:max_n]]
