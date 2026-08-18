"""Configuración central del motor (sustituye a los ~36 argv mágicos del código legacy).

Los umbrales de matching son valores iniciales razonables para ArcFace (coseno);
se calibran en la Fase 1 con `motor/eval` (T1.4). Ver NFR-ACC en docs/specs/01.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Config:
    # --- detección ---
    min_det_score: float = 0.5
    det_size: int = 640

    # --- calidad de imagen ---
    min_sharpness: float = 60.0      # varianza Laplaciano mínima (vigilancia)
    frontal_yaw_tol: float = 35.0
    frontal_pitch_tol: float = 25.0

    # --- matching (similitud coseno, embeddings L2-normalizados) ---
    secure_threshold: float = 0.45   # >= esto: match seguro
    match_threshold: float = 0.35    # >= esto: match si la diferencia con el 2º >= margin
    margin: float = 0.05             # separación frente al 2º para evitar confusión
    group_threshold: float = 0.40    # intra-batería: >= esto = misma persona en la escena

    # --- agrupación temporal ---
    batch_seconds: float = 6.0       # ventana para agrupar fotos de un mismo evento

    # --- procesa_video.py ---
    dedup_cosine: float = 0.97       # salta caras casi idénticas a las ya guardadas

    # --- store (face_enc_v2) ---
    max_encodings_per_person: int = 500

    # --- super-resolución (nitidez de caras pequeñas, motor/core/superres.py) ---
    sr_enabled: bool = True
    sr_model: str = "compact"      # "compact" (realesr-general-x4v3, ~2-5 s/cara, recomendado prod)
                                   # "x4plus" (RealESRGAN_x4plus, mejor calidad, ~30 s/cara en CPU)
    sr_target_side: int = 512      # lado mínimo de salida en fallback LANCZOS4+unsharp
    sr_min_side: int = 320         # solo SR si el lado mayor del crop es < esto (caras pequeñas)

    # --- enrolamiento ---
    enrollment_min_sharpness: float = 80.0
    min_poses: list[str] = field(default_factory=lambda: ["f", "pi", "pd"])

    # --- pose label (yaw/pitch en grados) ---
    yaw_frontal: float = 15.0
    yaw_45: float = 22.5
    yaw_90: float = 67.5
    pitch_frontal: float = 20.0
