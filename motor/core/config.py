"""Configuración central del motor (sustituye a los ~36 argv mágicos del código legacy).

Los umbrales de matching se calibraron con datos reales de videovigilancia (2026-08-18):
el coseno genuino (misma persona) en recortes de cámara es ~0.32-0.38, por lo que los
valores iniciales (0.45/0.35) fragmentaban identidades. Ver NFR-ACC en docs/specs/01.

La cascada de fusión (F0-F7) añade capas por fases; cada una con su feature-flag para
poder activarla/desactivarla en producción sin tocar código. Los pesos-prior iniciales
son los acordados: cara=0.60, torso=0.15, llm=0.25 (la capa LLM agrupa vlm_local+openai).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .env import get, get_float, get_int


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
    # Calibrado 2026-08-18 con datos reales: genuino ~0.32-0.38, impostor p95 ~0.36.
    secure_threshold: float = 0.40   # >= esto: match seguro
    match_threshold: float = 0.30    # >= esto: match si la diferencia con el 2º >= margin
    margin: float = 0.03             # separación frente al 2º para evitar confusión
    group_threshold: float = 0.30    # intra-batería: >= esto = misma persona en la escena

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

    # --- encuadre de la cara (auto-zoom hacia la cara en la foto guardada) ---
    face_fill: float = 0.70        # fracción del encuadre que debe ocupar la cara
    face_min_pad: int = 8          # pad mínimo (px) para no cortar frente/barbilla

    # --- enrolamiento ---
    enrollment_min_sharpness: float = 80.0
    min_poses: list[str] = field(default_factory=lambda: ["f", "pi", "pd"])

    # --- pose label (yaw/pitch en grados) ---
    yaw_frontal: float = 15.0
    yaw_45: float = 22.5
    yaw_90: float = 67.5
    pitch_frontal: float = 20.0

    # ------------------------------------------------------------------
    # CASCADA DE FUSIÓN (F0-F7) — feature-flags por fase, OFF por defecto
    # ------------------------------------------------------------------

    # --- fusión ponderada (F3) ---
    cascade_enabled: bool = False       # feature-flag global de la cascada
    gray_low: float = 0.28              # fusión < esto con confianza alta => new
    gray_high: float = 0.42             # fusión >= esto con confianza decente => match
    new_confidence_min: float = 0.45    # confianza mínima de fusión para auto-crear "new"
    early_exit_conf: float = 0.97       # capa con c_i >= esto finaliza inmediatamente
    escalate_band: float = 0.05         # candidatos a >= top1 - banda ("podría-ser-la-misma")
    w_cara: float = 0.60                # peso-prior capa cara (L1a)
    w_torso: float = 0.15               # peso-prior capa torso/ropa (L1b)
    w_llm: float = 0.25                 # peso-prior capas LLM (L2 vlm_local + L3 openai)
    face_conf_secure_floor: float = 0.60  # si L1a da match seguro con c >= esto => match final
                                           # (invariante de seguridad: nunca degradar a new)

    # --- L1a cara: sub-pesos de la confianza de instancia ---
    c_w_sharp: float = 0.25             # nitidez normalizada
    c_w_margin: float = 0.35            # separación top1-top2 normalizada
    c_w_level: float = 0.40             # nivel absoluto del coseno

    # --- torso/ropa (F1, L1b) ---
    torso_enabled: bool = False
    torso_ttl_days: float = 30.0        # frescura: 1.0 hoy -> 0.0 tras N días
    torso_w_face: float = 2.5           # ancho del crop de torso en veces el ancho de la cara
    torso_h_face: float = 2.0           # alto del crop de torso (desde la barbilla) en veces la cara

    # --- zonas/ángulos (F2, L1c) ---
    zones_enabled: bool = False

    # --- VLM local (F4, L2) — Ollama, UN solo worker compartido ---
    # Nota: el registro de Ollama ya no ofrece qwen2-vl:4b; se usa qwen2.5vl:3b
    # (3.2 GB, orientado a edge AI, ver docs) con el mismo prompt de identidad.
    vlm_enabled: bool = False
    vlm_base_url: str = "http://localhost:11434"
    vlm_model: str = "qwen2.5vl:3b"
    vlm_num_ctx: int = 1024             # KV limitado para no desbordar RAM en CPU
    vlm_num_gpu: int = 0
    vlm_timeout_s: float = 30.0
    vlm_keep_alive_s: float = 300.0     # descarga el modelo tras N s sin peticiones
    vlm_max_pending: int = 20           # cola acotada; si se llena, se degrada (no bloquea)
    vlm_ram_defer_gb: float = 2.0       # RAM libre < esto => diferir (encolar)
    vlm_ram_skip_gb: float = 1.0        # RAM libre < esto => omitir (c_vlm=0)

    # --- OpenAI (F5, L3) — solo último recurso, con presupuesto diario ---
    openai_enabled: bool = False
    openai_model: str = "gpt-4o-mini"
    openai_daily_budget: int = 100
    openai_timeout_s: float = 45.0
    openai_retries: int = 2

    # --- feedback / calibración (F3) ---
    feedback_enabled: bool = False
    calibration_enabled: bool = False
    calib_lr: float = 0.15              # cap al delta diario de pesos (anti-drift)
    calib_ewma_alpha: float = 0.30      # factor de olvido del EWMA de accuracy

    # --- rutas runtime (gitignored: git = código, no datos) ---
    feedback_dir: str = "motor/feedback"
    revision_dir: str = "motor/revision"
    backups_dir: str = "motor/backups"
    calib_dir: str = "motor/calib"
    llm_cache_dir: str = "motor/llm_cache"

    # --- secretos / modelo externo (se cargan desde .env, nunca en código) ---
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_daily_budget: int = 100

    # --- VLM override desde .env ---
    vlm_base_url_env: str = ""
    vlm_model_env: str = ""

    @classmethod
    def from_env(cls, ruta: str) -> "Config":
        """Config con los valores del `.env` del proyecto (secretos y VLM)."""
        cfg = cls()
        cfg.llm_api_key = get(ruta, "RF_LLM_API_KEY", cfg.llm_api_key)
        cfg.llm_model = get(ruta, "RF_LLM_MODEL", cfg.llm_model)
        cfg.llm_daily_budget = get_int(ruta, "RF_LLM_DAILY_BUDGET", cfg.llm_daily_budget)
        cfg.vlm_base_url = get(ruta, "RF_VLM_BASE_URL", cfg.vlm_base_url).rstrip("/")
        cfg.vlm_model = get(ruta, "RF_VLM_MODEL", cfg.vlm_model)
        cfg.vlm_num_ctx = get_int(ruta, "RF_VLM_NUM_CTX", cfg.vlm_num_ctx)
        cfg.vlm_num_gpu = get_int(ruta, "RF_VLM_NUM_GPU", cfg.vlm_num_gpu)
        cfg.vlm_timeout_s = get_float(ruta, "RF_VLM_TIMEOUT_S", cfg.vlm_timeout_s)
        cfg.vlm_keep_alive_s = get_float(ruta, "RF_VLM_KEEP_ALIVE_S", cfg.vlm_keep_alive_s)
        cfg.vlm_max_pending = get_int(ruta, "RF_VLM_MAX_PENDING", cfg.vlm_max_pending)
        cfg.vlm_ram_defer_gb = get_float(ruta, "RF_VLM_RAM_DEFER_GB", cfg.vlm_ram_defer_gb)
        cfg.vlm_ram_skip_gb = get_float(ruta, "RF_VLM_RAM_SKIP_GB", cfg.vlm_ram_skip_gb)
        return cfg
