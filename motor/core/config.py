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

from .env import get, get_bool, get_float, get_int


@dataclass
class Config:
    # --- detección ---
    # det_size 640 -> 1280: la cámara graba 1080p y las caras lejanas miden
    # ~30-90 px; a 640 el detector las pierde. A 1280 se detectan caras mucho
    # más pequeñas (coste ~4x en CPU, amortizado por el muestreo face-every).
    min_det_score: float = 0.4
    det_size: int = 1280
    # det_size para CROPS de cara ya recortados (clasificador + re-embedding):
    # la imagen es pequeña (~85-130 px), subirla a 1280 solo desperdicia CPU.
    crop_det_size: int = 640

    # --- calidad de imagen ---
    # 80 -> 55: las caras lejanas (pocos px) tienen varianza de Laplaciano baja
    # y con 80 se descartaban antes de poder aplicar SR. 55 sigue filtrando
    # desenfoque real pero admite caras pequeñas aprovechables.
    # 55 -> 70 (2026-08-26): la clasificación fallaba porque se decidía sobre
    # caras borrosas/pequeñas con embeddings ruidosos. 70 filtra el desenfoque
    # real que produce falsos match/new (ver NFR-ACC).
    min_sharpness: float = 70.0      # varianza Laplaciano mínima (vigilancia)
    # Tamaño mínimo (lado mayor, px) de la cara para ser admitida en matching/
    # galería. Por debajo, la cara tiene tan poca información que el embedding
    # ArcFace es poco fiable -> se descarta (nopasafiltros) en vez de decidir.
    face_min_side: int = 52
    frontal_yaw_tol: float = 35.0
    frontal_pitch_tol: float = 25.0

    # --- matching (similitud coseno, embeddings L2-normalizados) ---
    # ENDURECIDO 2026-09-01 (anti-mezcla): dos personas "que se parecen" en
    # videovigilancia alcanzan hasta coseno ~0.43 (falso merge real: visitante 75
    # mezcló 2 personas con puente cruzado 0.43). Todos los umbrales se suben por
    # encima de esa banda del impostor: ante la duda se prefiere crear una persona
    # duplicada a mezclar caras (precisión sobre recall).
    secure_threshold: float = 0.55   # >= esto: match seguro (impostor máx observado 0.43)
    match_threshold: float = 0.48    # >= esto: match si la diferencia con el 2º >= margin
    margin: float = 0.07             # separación frente al 2º para evitar confusión
    group_threshold: float = 0.50    # intra-batería: >= esto = misma persona en la escena

    # --- refinamiento autoaprendizaje (F1): galerías limpias ---
    # Sub-clustering coherente: dentro de un clúster de batería, un miembro
    # permanece con el representativo solo si coseno >= cluster_confirm. Evita
    # que dos personas juntas en la escena se mezclen en una galería (union-find
    # transitivo enlazaba caras ajenas: impostor p95 ~0.36, máx real 0.43).
    # ENDURECIDO 2026-09-01: 0.55 separa el par real mezclado (cruzado 0.43).
    cluster_confirm: float = 0.55
    # Admisión individual: un encoding solo entra en la galería de la persona
    # asignada si su mejor similitud contra esa persona >= admission_cosine
    # (y, con zones_enabled, contra una pose comparable). Evita que una cara
    # ajena agrupada por transitividad contamine la galería y provoque falsos
    # match posteriores (agregación max).
    admission_cosine: float = 0.48
    admission_pose_aware: bool = True

    # --- agrupación temporal ---
    batch_seconds: float = 6.0       # ventana para agrupar fotos de un mismo evento

    # --- procesa_video.py ---
    dedup_cosine: float = 0.97       # salta caras casi idénticas a las ya guardadas
    face_every: int = 2              # muestreo: analiza 1 de cada N frames (más muestras MF-SR/HQ)

    # --- RAM-gate (clasificador.py) ---
    # Si la memoria disponible (MemAvailable) baja de este umbral, el clasificador
    # duerme y no procesa: evita que 12 instancias de insightface pidan RAM a la vez
    # (p. ej. mientras autotube renderiza en la misma máquina) y dispare el OOM killer.
    ram_min_free_gb: float = 2.0

    # --- CPU-gate (clasificador.py) ---
    # Si la carga media de 1 min (loadavg) supera nproc * max_load_ratio, el
    # clasificador duerme: el procesado se difiere hasta que haya CPU libre.
    # Protege a los capturadores (guarda_movimientosV3, tiempo real) de la
    # saturación causada por la clasificación + autotube en la misma máquina.
    max_load_ratio: float = 1.0

    # --- store (face_enc_v2) ---
    max_encodings_per_person: int = 500

    # --- super-resolución (nitidez de caras pequeñas, motor/core/superres.py) ---
    sr_enabled: bool = True
    sr_model: str = "compact"      # "compact" (realesr-general-x4v3, ~2-5 s/cara, recomendado prod)
                                   # "x4plus" (RealESRGAN_x4plus, mejor calidad, ~30 s/cara en CPU)
    sr_target_side: int = 512      # TOPE máximo de salida (ya no se reescala hasta aquí:
                                   # el top-up LANCZOS4 a 512 pixelaba las caras pequeñas ~11x)
    sr_min_side: int = 320         # solo SR si el lado mayor del crop es < esto (caras pequeñas)
    min_display_side: int = 384    # A5 top-up de DISPLAY: solo se reescala (LANCZOS4) la foto
                                   # final hasta este lado si quedó menor (antes 512: pixelaba
                                   # caras diminutas ~11x; 384 es un upscale más suave).
    # SR-before-embedding: caras con lado mayor < esto se super-resuelven ANTES de
    # recalcular el embedding ArcFace (mejora real del matching, no solo visual).
    sr_embed_min_face: int = 96

    # --- super-resolución multi-frame (MF-SR) ---
    # OFF por defecto: se prefiere un ÚNICO frame nítido y cercano (selección por
    # nitidez x área) sobre la fusión de varios, que con alineación imperfecta
    # puede dar ligero desenfoque. Se mantiene como opt-in (RF_SR_MF_ENABLED=1).
    sr_mf_enabled: bool = False
    sr_mf_k: int = 8                # nº de crops a alinear/fusionar por cara
    sr_mf_min_face: int = 128       # solo fusionar si el lado mayor de la cara < esto

    # --- restauración facial GFPGAN (motor/core/gfpgan.py) ---
    sr_face_enabled: bool = True   # prior facial: caras naturales de 512 px sin pixelado
    sr_face_weight: float = 0.30   # mezcla salida GFPGAN / entrada SR (identidad; None no aplica)
                                   # 0.70 -> 0.30 (2026-08-26): 0.70 sobre-restauraba y producía
                                   # el efecto "fantasma"/ceroso en gafas y caras pequeñas.
    # A3 gate: SOLO se restaura la cara con GFPGAN si su lado mayor ORIGINAL (en
    # el crop de entrada, antes del SR) es >= este umbral. Las caras diminutas
    # (< umbral) se dejan con el SR genérico (píxel real) en vez de dejar que
    # GFPGAN alucine rasgos: menos "fantasma", identidad más honesta.
    face_restore_min_side: int = 96

    # --- foto final de busto (display) ---
    # La foto que se muestra en el panel se genera desde un crop de busto (torso
    # real nítido) y solo la región de la cara se restaura con GFPGAN. La cara
    # ocupa ~busto_face_fill del encuadre (vs 0.70 del auto-zoom anterior).
    busto_enabled: bool = True
    busto_face_fill: float = 0.40    # fracción del encuadre que ocupa la cara
    busto_min_pad: int = 16          # pad mínimo (px) alrededor de la cara
    busto_w_face: float = 3.0        # ancho del crop de busto en veces el ancho de la cara
    busto_h_face: float = 4.5        # alto del crop de busto en veces el alto de la cara
    busto_head_pad: float = 0.6      # margen sobre la cabeza (pelo) en veces el alto de la cara
    # B (2 caras en el mismo busto): el crop de busto puede contener a OTRA
    # persona. Para la foto final se elige la cara con mayor coseno contra la
    # persona del sub-clúster (no la de mayor det_score); si ninguna supera este
    # umbral se cae al crop tight (cara correcta garantizada).
    display_face_min_cosine: float = 0.6

    # --- foto final HQ (progresiva): fast (compact) -> HQ (sr_model_photo) ---
    # La foto rápida (compact) aparece al instante; si hq_enabled, un hilo de
    # fondo genera la versión HQ (sr_model_photo) y el panel la "autonitida"
    # sin recargar. Los embeddings/matching SIEMPRE usan `sr_model` (compact).
    sr_model_photo: str = "compact"  # modelo SR de la foto final (HQ)
                                   # x4plus -> compact (2026-08-26): con la máquina a
                                   # loadavg ~50, x4plus (~30-45 s/cara) no terminaba y las
                                   # fotos se quedaban en la versión "rápida" pixelada para
                                   # siempre. compact (realesr-general-x4v3, ~2-5 s/cara)
                                   # termina siempre y es el MISMO modelo del embedding.
    hq_enabled: bool = True          # generar la versión HQ progresiva
    hq_max_workers: int = 1          # nº máx de trabajos HQ concurrentes (CPU)

    # --- SR-before-embedding (superres.enhance_embedding) ---
    # Flag para poder desactivar el re-embedding sobre crop SR (que el propio
    # código documenta como "plastificante"). Default True (comportamiento
    # actual); la validación (motor/eval) decide si conviene dejarlo o no.
    sr_embed_enabled: bool = True

    # --- encuadre de la cara (auto-zoom hacia la cara en la foto guardada) ---
    face_fill: float = 0.70        # fracción del encuadre que debe ocupar la cara
    face_min_pad: int = 8          # pad mínimo (px) para no cortar frente/barbilla

    # --- enrolamiento ---
    # Nitidez mínima de las caras admitidas en el registro. 80 -> 95 (2026-09-01):
    # las caras "algo borrosas" ensuciaban la galería y bajaban la tasa de acierto.
    # Se deja un valor intermedio para probar en producción.
    enrollment_min_sharpness: float = 95.0
    # Poses admitidas en el enrolamiento. Se conservan frontal + giros moderados
    # (45°) + arriba/abajo; se DESCARTAN los perfiles 90° (pi/pd, "casi de espaldas")
    # y `other` (pose degenerada), que producían embeddings ruidosos y baja acierto.
    min_poses: list[str] = field(default_factory=lambda: ["f", "m45i", "m45d", "arr", "aba"])

    # --- pose label (yaw/pitch en grados) ---
    yaw_frontal: float = 15.0
    yaw_45: float = 22.5
    yaw_90: float = 67.5
    pitch_frontal: float = 20.0

    # ------------------------------------------------------------------
    # MOTOR DE DECISIÓN SITUACIONAL (reenfoque A+B) — fusion.py + router.py
    # La decisión ya NO es una media ponderada: cada situación elige qué
    # capa es AUTORIDAD (cara/perfil), cuáles CONFIRMAN por ACUERDO (silueta
    # en perfil/ángulos) y cuáles corroboran/vetan en la zona gris.
    # ------------------------------------------------------------------

    # --- feature-flags (activación gradual vía .env) ---
    cascade_enabled: bool = False       # motor situacional (reemplaza la decisión binaria)
    torso_enabled: bool = False         # capa L1b torso/ropa (apoyo)
    silueta_enabled: bool = True        # capa geométrica L1c (acuerdo en perfil/ángulos)
    perfil_layer_enabled: bool = True   # matching pose-consciente (perfil) — ya en L1a
    zones_enabled: bool = True          # matching pose-consciente en L1a (activado por defecto)
    vlm_enabled: bool = False
    openai_enabled: bool = False

    # --- umbrales operativos (ENDURECIDOS 2026-09-01 anti-mezcla; override .env) ---
    secure_threshold: float = 0.55      # s1 >= esto: match seguro (NUNCA new)
    match_threshold: float = 0.48       # s1 >= esto: match si margen/confirmación
    margin: float = 0.07                # separación top1-top2 (decisión binaria L1a)
    gray_low: float = 0.38              # s < esto con confianza alta => evidencia en contra
    gray_high: float = 0.55             # confirmación: capa de apoyo >= esto corrobora
    escalate_band: float = 0.03         # candidatos a >= top1 - banda ("podría-ser-la-misma")

    # --- banda baja (anti-fragmentación de perfiles/espaldas, 2026-08-21) ---
    # ENDURECIDO 2026-09-01: suelo 0.15 -> 0.30 y corroboración solo si las capas
    # coinciden con gray_high (0.55) y confianza mínima alta. La banda [0.30, 0.48)
    # exige un acuerdo MUY fuerte de capas independientes antes de asociar a top1.
    new_low_floor: float = 0.30         # s1 < esto => "new" directo sin corroboración
    low_band_min_agreements: int = 2    # capas independientes que deben coincidir

    # --- early-exit frontal: margen mínimo top1-top2 ---
    # ENDURECIDO 2026-09-01: 0.06 -> 0.09 (la cara sola solo decide con margen limpio).
    early_exit_min_margin: float = 0.09

    # --- confianza mínima para VOTAR por capa ---
    # Una capa solo aporta evidencia si su confianza de instancia supera su
    # umbral; por debajo se ignora (su señal se considera no fiable, no en contra).
    # ENDURECIDO 2026-09-01: min_layer_conf 0.70 -> 0.75, llm_min_conf 0.85 -> 0.90.
    min_layer_conf: float = 0.75        # apoyo general (silueta/torso)
    llm_min_conf: float = 0.90          # LLM: más estricto (sobreconfianza sin calibrar)
    # ENDURECIDO 2026-09-01: 0.85 -> 0.80 (más fácil que 2 capas independientes
    # vetten un match seguro -> uncertain -> persona duplicada, no mezcla).
    veto_conf: float = 0.80             # contradicción FUERTE (s < gray_low y c >= esto)

    # --- acuerdo por silueta (perfil / ángulos raros) ---
    silueta_min_score: float = 0.60     # silueta >= esto confirma el acuerdo; < bloquea

    # --- pesos-prior (SOLO desempate/reporte; la decisión usa autoridad/veto) ---
    w_cara: float = 0.70                # peso-prior capa cara (L1a)
    w_torso: float = 0.10               # peso-prior capa torso/ropa (L1b, apoyo)
    w_llm: float = 0.10                 # peso-prior capas LLM (L2 vlm_local + L3 openai)
    perfil_w: float = 0.60              # peso de la cara pose-consciente (perfil)
    silueta_w: float = 0.30             # peso de la silueta geométrica (acuerdo perfil)
    face_conf_secure_floor: float = 0.60  # (legacy) suelo de confianza para c_cara
    early_exit_conf: float = 0.97       # (legacy) early-exit antiguo (mantenido)

    # --- L1a cara: sub-pesos de la confianza de instancia ---
    c_w_sharp: float = 0.25             # nitidez normalizada
    c_w_margin: float = 0.35            # separación top1-top2 normalizada
    c_w_level: float = 0.40             # nivel absoluto del coseno

    # --- torso/ropa (F1, L1b) ---
    torso_ttl_days: float = 30.0        # frescura: 1.0 hoy -> 0.0 tras N días
    torso_w_face: float = 2.5           # ancho del crop de torso en veces el ancho de la cara
    torso_h_face: float = 2.0           # alto del crop de torso (desde la barbilla) en veces la cara

    # --- F7: identificar de espaldas (crops de cuerpo sin cara) ---
    body_match_conf: float = 0.9        # OBSOLETO: sin uso lógico (la decisión F7
                                        # usa fuse() + gray_high + conf>=0.35 en
                                        # fusion._decide_body). Se conserva por
                                        # compat; pendiente de eliminar.

    # --- VLM local (F4, L2) — Ollama, UN solo worker compartido ---
    # Nota: el registro de Ollama ya no ofrece qwen2-vl:4b; se usa qwen2.5vl:3b
    # (3.2 GB, orientado a edge AI, ver docs) con el mismo prompt de identidad.
    vlm_enabled: bool = False
    vlm_base_url: str = "http://localhost:11434"
    vlm_model: str = "qwen2.5vl:3b"
    vlm_num_ctx: int = 4096             # mínimo útil: 2 imgs (384px) + prompt ≈ 900 tokens
    vlm_num_gpu: int = 0
    vlm_timeout_s: float = 90.0         # CPU compartida y bajo carga: margen amplio
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
    # ACTIVADOS por defecto (plan refinamiento-autoaprendizaje, F3): el
    # clasificador registra cada decisión y las acciones del panel ("Unir",
    # "mover foto") emiten etiquetas genuino/impostor que alimentan la
    # calibración diaria de pesos/umbrales con validación held-out.
    feedback_enabled: bool = True
    calibration_enabled: bool = True
    calib_lr: float = 0.15              # cap al delta diario de pesos (anti-drift)
    calib_ewma_alpha: float = 0.30      # factor de olvido del EWMA de accuracy
    calib_apply: bool = False           # aplicar calib_model.pkl al arranque/reload
                                        # (off hasta validar; activar RF_CALIB_APPLY=1)

    # --- disparador por VOLUMEN (auto-refinamiento, no horario) ---
    # El timer rf-calibra solo SONDEA; calibrar.py decide con estos valores.
    min_new_labels: int = 20            # etiquetas NUEVAS desde la última calibración
    min_samples: int = 20               # mínimo TOTAL absoluto (primera vez)
    min_interval_min: int = 60          # cooldown mínimo entre calibraciones

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

        # Resolución/calidad del pipeline (opcional; por defecto los valores de
        # esta clase). Permite afinar sin tocar código: p. ej. RF_SR_TARGET_SIDE
        # para el tamaño de las fotos finales o RF_SR_EMBED_MIN_FACE para
        # super-resolver más caras pequeñas antes del embedding (mejor matching).
        cfg.sr_target_side = get_int(ruta, "RF_SR_TARGET_SIDE", cfg.sr_target_side)
        cfg.sr_min_side = get_int(ruta, "RF_SR_MIN_SIDE", cfg.sr_min_side)
        cfg.sr_embed_min_face = get_int(ruta, "RF_SR_EMBED_MIN_FACE", cfg.sr_embed_min_face)
        cfg.sr_model = get(ruta, "RF_SR_MODEL", cfg.sr_model)
        cfg.sr_mf_enabled = get_bool(ruta, "RF_SR_MF_ENABLED", cfg.sr_mf_enabled)
        cfg.sr_mf_k = get_int(ruta, "RF_SR_MF_K", cfg.sr_mf_k)
        cfg.sr_mf_min_face = get_int(ruta, "RF_SR_MF_MIN_FACE", cfg.sr_mf_min_face)
        cfg.sr_face_enabled = get_bool(ruta, "RF_SR_FACE_ENABLED", cfg.sr_face_enabled)
        cfg.sr_face_weight = get_float(ruta, "RF_SR_FACE_WEIGHT", cfg.sr_face_weight)
        cfg.sr_model_photo = get(ruta, "RF_SR_MODEL_PHOTO", cfg.sr_model_photo)
        cfg.hq_enabled = get_bool(ruta, "RF_HQ_ENABLED", cfg.hq_enabled)
        cfg.hq_max_workers = get_int(ruta, "RF_HQ_MAX_WORKERS", cfg.hq_max_workers)
        cfg.busto_enabled = get_bool(ruta, "RF_BUSTO_ENABLED", cfg.busto_enabled)
        cfg.busto_face_fill = get_float(ruta, "RF_BUSTO_FACE_FILL", cfg.busto_face_fill)
        cfg.display_face_min_cosine = get_float(ruta, "RF_DISPLAY_FACE_MIN_COS", cfg.display_face_min_cosine)
        cfg.face_every = get_int(ruta, "RF_FACE_EVERY", cfg.face_every)
        cfg.min_sharpness = get_float(ruta, "RF_MIN_SHARPNESS", cfg.min_sharpness)
        cfg.face_min_side = get_int(ruta, "RF_FACE_MIN_SIDE", cfg.face_min_side)
        cfg.face_restore_min_side = get_int(ruta, "RF_FACE_RESTORE_MIN_SIDE", cfg.face_restore_min_side)
        cfg.sr_embed_enabled = get_bool(ruta, "RF_SR_EMBED_ENABLED", cfg.sr_embed_enabled)
        cfg.min_display_side = get_int(ruta, "RF_MIN_DISPLAY_SIDE", cfg.min_display_side)
        cfg.det_size = get_int(ruta, "RF_DET_SIZE", cfg.det_size)
        cfg.crop_det_size = get_int(ruta, "RF_CROP_DET_SIZE", cfg.crop_det_size)
        cfg.face_fill = get_float(ruta, "RF_FACE_FILL", cfg.face_fill)
        cfg.face_min_pad = get_int(ruta, "RF_FACE_MIN_PAD", cfg.face_min_pad)
        cfg.ram_min_free_gb = get_float(ruta, "RF_RAM_MIN_FREE_GB", cfg.ram_min_free_gb)

        # Umbrales de matching configurables (calibrados offline con motor/eval/eval.py
        # o por el ritual E del calibrador guiado; ver docs y libs/calibracion.php).
        cfg.match_threshold = get_float(ruta, "RF_MATCH_THRESHOLD", cfg.match_threshold)
        cfg.margin = get_float(ruta, "RF_MARGIN", cfg.margin)
        cfg.secure_threshold = get_float(ruta, "RF_SECURE_THRESHOLD", cfg.secure_threshold)
        cfg.group_threshold = get_float(ruta, "RF_GROUP_THRESHOLD", cfg.group_threshold)
        cfg.cluster_confirm = get_float(ruta, "RF_CLUSTER_CONFIRM", cfg.cluster_confirm)
        cfg.admission_cosine = get_float(ruta, "RF_ADMISSION_COSINE", cfg.admission_cosine)

        # Motor de decisión situacional: flags de activación gradual y umbrales
        # de confianza por capa (sin tocar código).
        cfg.cascade_enabled = get_bool(ruta, "RF_CASCADE_ENABLED", cfg.cascade_enabled)
        cfg.torso_enabled = get_bool(ruta, "RF_TORSO_ENABLED", cfg.torso_enabled)
        cfg.silueta_enabled = get_bool(ruta, "RF_SILUETA_ENABLED", cfg.silueta_enabled)
        cfg.perfil_layer_enabled = get_bool(ruta, "RF_PERFIL_LAYER_ENABLED", cfg.perfil_layer_enabled)
        cfg.vlm_enabled = get_bool(ruta, "RF_VLM_ENABLED", cfg.vlm_enabled)
        cfg.openai_enabled = get_bool(ruta, "RF_OPENAI_ENABLED", cfg.openai_enabled)
        cfg.min_layer_conf = get_float(ruta, "RF_MIN_LAYER_CONF", cfg.min_layer_conf)
        cfg.llm_min_conf = get_float(ruta, "RF_LLM_MIN_CONF", cfg.llm_min_conf)
        cfg.veto_conf = get_float(ruta, "RF_VETO_CONF", cfg.veto_conf)
        cfg.gray_low = get_float(ruta, "RF_GRAY_LOW", cfg.gray_low)
        cfg.gray_high = get_float(ruta, "RF_GRAY_HIGH", cfg.gray_high)
        cfg.escalate_band = get_float(ruta, "RF_ESCALATE_BAND", cfg.escalate_band)
        cfg.silueta_min_score = get_float(ruta, "RF_SILUETA_MIN_SCORE", cfg.silueta_min_score)
        cfg.new_low_floor = get_float(ruta, "RF_NEW_LOW_FLOOR", cfg.new_low_floor)
        cfg.low_band_min_agreements = get_int(ruta, "RF_LOW_BAND_AGREEMENTS", cfg.low_band_min_agreements)
        cfg.early_exit_min_margin = get_float(ruta, "RF_EARLY_EXIT_MIN_MARGIN", cfg.early_exit_min_margin)
        cfg.calib_apply = get_bool(ruta, "RF_CALIB_APPLY", cfg.calib_apply)
        # Enrolamiento: umbral de nitidez de las caras del registro (ajustable sin código).
        cfg.enrollment_min_sharpness = get_float(ruta, "RF_ENROLL_MIN_SHARPNESS", cfg.enrollment_min_sharpness)
        return cfg
