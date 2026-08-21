"""Capa de zonas/ángulos (L1c): matching pose-consciente + silueta geométrica.

La cara global (ArcFace) pierde discriminación entre ángulos muy distintos
(perfil↔frontal). L1c aporta dos señales baratas (sin re-embedding masivo):

  1. MATCHING POSE-CONSCIENTE: la similitud de cara se calcula solo contra los
     encodings de la galería cuya CLASE DE POSE es comparable con la del query.
     (f <-> f, m45, arr, aba ; pi <-> pi, m45i ; pd <-> pd, m45d).

  2. SILUETA GEOMÉTRICA: descriptor de distancias entre landmarks (106 pts)
     normalizadas por el ancho de la cara -> invariable a escala. Se compara
     entre el query y la foto representativa del candidato. s_zona combina
     ambos; c_zona = compatibilidad de pose x acuerdo de silueta.

Las zonas de landmarks (ojos, nariz, boca, frente, mentón, oreja) se recortan
aquí para contexto de las capas VLM (L2/L3), no para re-embedding por defecto
(CPU limitada). Si `zones_reembed` está activo (off por defecto), se re-embeben
solo en escalada y se comparan por pares de zonas comparables.
"""
from __future__ import annotations

import cv2
import numpy as np

# --- clases de pose (etiquetas de quality.pose_label) ---
FRONTAL_CLASSES = {"f", "m45i", "m45d", "arr", "aba"}
PROFILE_LEFT = {"pi", "m45i"}
PROFILE_RIGHT = {"pd", "m45d"}


def pose_compatible(q_pose: str | None, g_pose: str | None) -> bool:
    """¿Pueden ser la misma persona q_pose y g_pose? (comparabilidad de zonas)."""
    if q_pose is None or g_pose is None:
        return True                      # sin etiqueta: no descartamos
    if q_pose == g_pose:
        return True
    if q_pose in FRONTAL_CLASSES and g_pose in FRONTAL_CLASSES:
        return True
    if q_pose in PROFILE_LEFT and g_pose in PROFILE_LEFT:
        return True
    if q_pose in PROFILE_RIGHT and g_pose in PROFILE_RIGHT:
        return True
    return False


def silhouette_descriptor(face) -> np.ndarray:
    """Descriptor geométrico de la silueta facial.

    Prioridad: landmarks completos (106 pts) -> pares de distancias estables
    normalizadas por la distancia inter-pupilar. Si no hay landmarks suficientes
    (p. ej. poses arr/aba extremas donde el modelo 106 falla), FALLBACK a los 5
    keypoints de detección (kps: ojos/nariz/boca) con el mismo esquema de
    normalización: así la capa de silueta sigue disponible en las poses donde
    más se necesita (antes devolvía vector vacío y la co-autoridad se saltaba).
    Si no hay ni landmarks ni kps, devuelve un vector vacío (capa sin señal).
    """
    lm = getattr(face, "landmarks", None)
    if lm is not None and len(lm) >= 20:
        lm = np.asarray(lm, dtype=np.float32)
        # pares de índices del modelo 106 (aproximaciones estables):
        # ojo izq ~ 33/34, ojo der ~ 87/88 (buffalo_l 106pts: ojo izq ~33, ojo der ~87)
        pairs = [
            (33, 87),   # inter-pupilar (referencia de escala)
            (8, 98),    # mentón -> frente alta
            (52, 88),   # nariz -> ojo der
            (52, 33),   # nariz -> ojo izq
            (61, 72),   # boca ancho
            (33, 52),   # ojo izq -> nariz
            (87, 52),   # ojo der -> nariz
            (33, 8),    # ojo izq -> mentón
            (87, 8),    # ojo der -> mentón
            (33, 98),   # ojo izq -> frente
            (87, 98),   # ojo der -> frente
            (4, 103),   # ancho frontal (sienes)
        ]
        out = []
        for (i, j) in pairs:
            d = float(np.linalg.norm(lm[i] - lm[j]))
            out.append(d)
        v = np.asarray(out, dtype=np.float32)
        scale = v[0] if v[0] > 1e-6 else 1.0
        v = v / scale
        n = np.linalg.norm(v)
        if n > 0:
            v = v / n
        return v

    kps = getattr(face, "kps", None)
    if kps is not None and len(kps) >= 5:
        kps = np.asarray(kps, dtype=np.float32)
        eye_l, eye_r, nose, mouth_l, mouth_r = kps[0], kps[1], kps[2], kps[3], kps[4]
        scale = float(np.linalg.norm(eye_r - eye_l))
        if scale < 1e-6:
            return np.zeros(0, dtype=np.float32)
        mouth_c = 0.5 * (mouth_l + mouth_r)
        v = np.asarray([
            float(np.linalg.norm(nose - eye_l)),
            float(np.linalg.norm(nose - eye_r)),
            float(np.linalg.norm(nose - mouth_c)),
            float(np.linalg.norm(mouth_r - mouth_l)),
            float(np.linalg.norm(mouth_l - eye_l)),
            float(np.linalg.norm(mouth_r - eye_r)),
        ], dtype=np.float32) / scale
        n = np.linalg.norm(v)
        if n > 1e-9:
            v = v / n
        return v
    return np.zeros(0, dtype=np.float32)


def silhouette_sim(a_desc: np.ndarray, b_desc: np.ndarray) -> float:
    """Acuerdo 0..1 entre dos siluetas (1 - L1 normalizado; 0 si falta señal)."""
    if a_desc.size == 0 or b_desc.size == 0 or a_desc.shape != b_desc.shape:
        return 0.0
    return float(np.clip(1.0 - float(np.abs(a_desc - b_desc).sum()) / 2.0, 0.0, 1.0))


def zone_crops(img: np.ndarray, face) -> dict[str, np.ndarray]:
    """Recortes de zonas faciales por landmarks (106 pts), con fallback a bbox.

    Devuelve dict[str, crop]. Las zonas se usan como CONTEXTO para el VLM
    (L2/L3) y para re-embedding opcional (zones_reembed, off por defecto).
    """
    lm = getattr(face, "landmarks", None)
    h, w = img.shape[:2]
    zones: dict[str, tuple[int, int, int, int]] = {}
    if lm is not None and len(lm) >= 20:
        lm = np.asarray(lm, dtype=np.float32)
        # índices aproximados del modelo 106 de buffalo_l (verificar con datos reales)
        def box(idx):
            pts = lm[idx]
            x0, y0 = int(pts[:, 0].min()), int(pts[:, 1].min())
            x1, y1 = int(pts[:, 0].max()), int(pts[:, 1].max())
            return (x0, y0, x1, y1)
        zones["ojo_izq"] = box([33, 36])
        zones["ojo_der"] = box([87, 90])
        zones["nariz"] = box([51, 56])
        zones["boca"] = box([61, 72])
        zones["frente"] = box([96, 103])
        zones["menton"] = box([4, 8])
    x1, y1, x2, y2 = face.bbox
    zones.setdefault("cara", (x1, y1, x2, y2))
    out: dict[str, np.ndarray] = {}
    for name, (zx1, zy1, zx2, zy2) in zones.items():
        zx1, zy1 = max(0, zx1), max(0, zy1)
        zx2, zy2 = min(w, zx2), min(h, zy2)
        if zx2 - zx1 >= 8 and zy2 - zy1 >= 8:
            out[name] = img[zy1:zy2, zx1:zx2]
    return out


def pose_confidence(q_pose: str | None, g_pose: str | None) -> float:
    """Peso de comparabilidad de pose: 1.0 misma clase, 0.6 adyacente, 0.0 opuesta."""
    if q_pose is None or g_pose is None:
        return 0.6
    if q_pose == g_pose:
        return 1.0
    if pose_compatible(q_pose, g_pose):
        return 0.6
    return 0.0
