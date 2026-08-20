"""Proveniencia de encodings — mover una foto (o varias) entre personas de forma EXACTA.

P4 del plan unir/separar: el panel mueve fotos (`fotos.id`) entre personas. Cada
foto tiene su `identificador_unico` (el foto_id que el clasificador puso en el
nombre `{nombre}_{foto_id}.jpg` y que clasificadorV2.php guarda en la BD), y
cada encoding de la galería guarda esa misma proveniencia en `sources` (P1/P2).

Con eso, "mover foto" quita de la persona equivocada EXACTAMENTE lo que aportó
esa foto (move_by_source) y lo lleva a la correcta — sin residuos ni guess por
coseno. Jerarquía:

  1. source: proveniencia exacta presente en la galería de origen (rápido, sin
     cargar el modelo).
  2. cosine: encodings legacy sin `sources` → se re-embebe la foto y se mueven
     los encodings de origen cuya mejor similitud >= min_cosine.
  3. reembed: la cara ya no está en la galería de origen → se añade re-embebida
     al destino (etiquetada con la proveniencia si se conoce).
"""
from __future__ import annotations

import os

from .backup import _mysql
from .config import Config
from .store import FaceStore

DEFAULT_MIN_COSINE = 0.45   # calibrado: la misma cara coincide ~0.5-0.9; 0.45 no arrastra a otros


def lookup_foto_source(ruta: str, foto_id: int | str) -> str | None:
    """Devuelve el `identificador_unico` (foto_id del clasificador) de la foto, o None.

    None = foto sin traza en BD (borrada, legado) → se cae al fallback coseno.
    """
    try:
        rows = _mysql(ruta, f"SELECT identificador_unico FROM fotos WHERE id = {int(foto_id)} LIMIT 1")
    except RuntimeError:
        return None
    if not rows or not rows[0].strip():
        return None
    return rows[0].strip()


def move_foto(store: FaceStore, ruta: str, cfg: Config, foto_id: int | str,
              cod_origen: str, cod_destino: str,
              min_cosine: float = DEFAULT_MIN_COSINE) -> dict:
    """Mueve los encodings que aportó `foto_id` de `cod_origen` a `cod_destino`.

    Devuelve {"moved": int, "via": "source"|"cosine"|"reembed"|..., "label_emb": ndarray|None}.
    `label_emb` es un embedding representativo de lo movido (para la etiqueta de
    feedback impostor) o None si no se movió nada.
    """
    if cod_origen == cod_destino:
        return {"moved": 0, "via": "noop", "label_emb": None}

    # 1) proveniencia exacta
    source_id = lookup_foto_source(ruta, foto_id)
    if source_id:
        srcs = store.person_sources(cod_origen) or []
        idx = next((i for i, s in enumerate(srcs) if s == source_id), None)
        if idx is not None:
            encs = store.person_encodings(cod_origen)
            emb = encs[idx] if encs is not None else None
            moved = store.move_by_source(cod_origen, cod_destino, source_id)
            if moved:
                return {"moved": moved, "via": "source", "label_emb": emb}

    # 2/3) fallback legacy: re-embebe la foto y mueve/añade por coseno
    from motor.core.model import analyze
    from motor.core.quality import face_sharpness, pose_label
    import cv2

    foto_path = os.path.join(ruta, "admin/caras_procesadas", str(foto_id) + ".jpg")
    if not os.path.exists(foto_path):
        return {"moved": 0, "via": "missing", "label_emb": None}
    img = cv2.imread(foto_path)
    if img is None:
        return {"moved": 0, "via": "unreadable", "label_emb": None}
    faces = analyze(img, det_size=(cfg.det_size, cfg.det_size), min_score=cfg.min_det_score)
    if not faces:
        return {"moved": 0, "via": "noface", "label_emb": None}
    face = max(faces, key=lambda f: f.det_score)
    emb = face.embedding
    q = face_sharpness(img, face)
    po = pose_label(face, cfg.yaw_frontal, cfg.yaw_45, cfg.yaw_90, cfg.pitch_frontal)

    moved = store.move_matching(cod_origen, cod_destino, [emb], min_cosine=min_cosine)
    if moved:
        return {"moved": moved, "via": "cosine", "label_emb": emb}
    store.add(cod_destino, [emb], [q], [po], sources=[source_id])
    return {"moved": 1, "via": "reembed", "label_emb": emb}
