# Spec 12 — Refinamiento del autoaprendizaje del clasificador (galerías limpias)

> Estado: implementado (2026-08-19). Objetivo del usuario: clasificar cada nueva
> persona con la máxima precisión — ni duplicar identidades, ni añadir caras
> ajenas a una persona, ni crear perfiles con 2-3 caras diferentes.

## Problema

Síntomas observados en producción:
1. Se añadía a una persona una cara que NO era suya (falso positivo).
2. Se creaban perfiles "raros" con 2-3 caras de personas distintas.

## Causas raíz (verificadas en código)

1. **Clúster mezclado** (`clasificador.py`): el union-find intra-batería a
   `group_threshold=0.30` enlazaba transitivamente caras de personas distintas
   (impostor p95 ~0.36): A~B y B~C unían A~C sin que A~C se parecieran.
2. **Se añadía TODO el clúster a una sola persona** (`_store_add`): todos los
   encodings del clúster entraban en la galería de la persona ganadora sin
   verificar cara a cara, contaminando `face_enc_v2`.
3. **Agregación max**: un impostor dentro de la galería disparaba falsos match
   posteriores (una cara ajena similar bastaba).
4. **Sin control de admisión por cara** ni poda de outliers.
5. **Feedback/calibración inertes**: las etiquetas del panel ("Unir"/"mover
   foto") no se emitían (`feedback_enabled=False`), y `cambiar_foto.py` usaba
   `Config()` sin `.env`, así que el bucle de autoaprendizaje no corría.

## Cambios (F1-F5)

### F1 — Galerías limpias
- **F1.1 Sub-clustering coherente** (`clasificador.py::split_coherent_clusters`):
  cada clúster de batería se divide en sub-clústeres alrededor de la cara más
  nítida; un miembro permanece solo si coseno vs representativo >=
  `cluster_confirm` (0.35). Dos personas juntas en la escena dejan de mezclarse.
- **F1.2 Admisión por cara** (`_store_add`): en match/uncertain, cada encoding
  entra en la galería solo si su mejor similitud individual contra la persona
  asignada >= `admission_cosine` (0.32), pose-consciente si `zones_enabled`.
  Los que no confirmen NO contaminan (la foto sí se archiva en el álbum).
- **F1.3 Identidades nuevas coherentes**: el sub-clúster garantiza coherencia
  interna antes de crear la persona (nada de perfiles con 2-3 caras).
- **F1.4 Poda de outliers** (`store.py::_prune`): con >= 8 encodings se
  descartan los que tengan similitud media al resto < `OUTLIER_COSINE` (0.25) —
  típicos impostores históricos — antes del top-N por nitidez. Nunca vacía.

### F2 — Decisión más precisa
- `min_sharpness` 60 → 80 (menos ruido; flag por cámara si se queda corto).
- `zones_enabled=True` por defecto: matching pose-consciente (comparar solo
  poses comparables) — barato, sin VLM, reduce falsos match y falsos new.

### F3 — Autoaprendizaje real
- `feedback_enabled=True` y `calibration_enabled=True`: el clasificador registra
  cada decisión (features por capa + hash del embedding, sin fotos) y las
  acciones del panel emiten etiquetas genuino/impostor →
  `motor/feedback/<local>/decisions.jsonl` y `labels.jsonl`.
- Fix `cambiar_foto.py` → `Config.from_env` (carga `.env`, emite su etiqueta).
- La calibración diaria (`motor/calibrar.py`, timer `rf-calibra`) ajusta pesos
  con validación TAR/FAR en held-out; desplegable solo si mejora.

### F4 — Detección/limpieza de perfiles mezclados existentes
- `motor/detectar_mezclados.py`:
  - `--check` (por defecto): analiza `face_enc_v2` y marca perfiles con
    satélites "alien": tamaño >= 2, coherencia interna >= 0.30 y similitud MÁXIMA
    al núcleo < `--bridge` 0.42 (impostores p95 ~0.36; variación genuina de
    pose mantiene puentes >= 0.45 — calibrado con la galería real, 46 personas:
    solo marcó `ik8TjR1S…` con un residuo de 2 caras ajenas).
  - `--apply`: re-embebe las fotos reales de la BD, re-clusteriza (umbral alto
    `--thr-apply` 0.45) y separa en personas nuevas, con snapshot + journal
    reversible (F6) y `--rollback`.
- Complementa a `motor/reagrupar.py` (fusiona duplicados; este SEPARA mezclados).

### F5 — Verificación
- `motor/tests/test_autoaprendizaje.py` (16 tests): sub-clustering coherente,
  admisión por cara, poda de outliers, detección de mezclados y no-marca de
  variación genuina. Suite completa: 136 passed, 1 skipped.

## Decisiones de diseño
- **Baja confianza**: se mantiene el comportamiento actual — tras pasar todas
  las capas, si no hay match se crea persona nueva (la UI tiene "Unir" para
  corregir, y esa corrección alimenta la calibración). Los "uncertain" siguen
  yendo a `motor/revision/`.
- **Umbrales operativos intactos** (secure 0.40 / match 0.30 / margin 0.03):
  siguen los calibrados con datos reales 2026-08-18; este refinamiento actúa
  sobre la CONTAMINACIÓN, no sobre los umbrales.

## Pendiente / riesgos
- `min_sharpness=80` puede dejar sin detecciones cámaras de muy baja resolución:
  bajar vía flag si ocurre.
- El set `motor/eval/data` (110 imgs) muestra genuino medio 0.27 (pose cruzada);
  la calibración operativa debe seguir alimentándose con feedback real
  (`calibrar.py`) y el eval `--pose-aware`.
- Revisar manualmente `ik8TjR1S…` (residuo de 2 caras) y decidir `--apply`.

## Reenfoque A+B — motor de decisión situacional (2026-08-20)

La fusión ponderada (media de capas) tenía un fallo estructural: una cara con
coseno alto podía degradarse a "new" por capas débiles con confianza no
calibrada (p. ej. LLM con `c≈0.9` y acierto real ~40%). Se sustituye por un
motor de EVIDENCIA con enrutado (`motor/core/router.py` + `fusion.py`):

- **Autoridad**: la capa de cara/perfil decide la identidad. Sin cara (F7),
  torso+LLM mandan y NUNCA crean persona.
- **Gate de identidad**: "new" <=> `s1 < match_threshold`. Las capas
  superiores jamás crean personas.
- **Suelo por cara**: `s1 >= secure_threshold` nunca es "new" (mínimo
  "uncertain"), independiente de `c_cara` (fix del bug).
- **Acuerdo**: en perfil/ángulos raros la silueta geométrica es co-autoridad
  (`silueta_min_score`); si está y NO confirma → uncertain, no new.
- **Veto**: ≥2 capas independientes (torso/vlm/openai) con `c >= veto_conf` y
  `s < gray_low` degradan match a uncertain (nunca a new).
- **Early-exit**: frontal nítida decide solo con la cara (sin capas caras).

Pesos-prior realistas (solo desempate/reporte, la decisión usa autoridad/veto):
`w_cara=0.70`, `w_torso=0.10`, `w_llm=0.10`, `perfil_w=0.60`, `silueta_w=0.30`.

Autoaprendizaje reconectado:
- El clasificador registra features L1a + candidatos aunque la cascada esté
  apagada (fix: `decisions.jsonl` quedaba con `layers={}` y la calibración no
  tenía matriz).
- `RF_CALIB_APPLY=1` carga `calib_model.pkl` (pesos) al arranque y lo re-lee
  por mtime cada 60 s (timer `rf-calibra` a las 05:10).
- La calibración informa fiabilidad por capa CONDICIONADA a la situación
  (`layer_stats_by_situation`): perfil/angulos/frontal/otro.

Activación gradual: `RF_CASCADE_ENABLED=1` (y opcionales `RF_TORSO_ENABLED`,
`RF_VLM_ENABLED`, `RF_OPENAI_ENABLED`) — ver `.env.example`.

### Alcance 3 diferido (auditar umbrales)
NO se recalibran `secure/match/margin` sobre `motor/eval/data`: el set está
construido desde las capturas actuales (deficientes), calibrar ahí fijaría
umbrales malos (circular). Queda pendiente hasta tener un set etiquetado
limpio capturado con la detección mejorada. `motor/eval` se usa SOLO como
diagnóstico relativo antes/después de activar capas.

### Disparador por VOLUMEN (2026-08-20)
La calibración ya no corre por horario fijo (diario 05:10): el timer
`rf-calibra` SOLO SONDEA cada 60 min y `calibrar.py` decide con un gate de
volumen de 2 etapas (auto-refinamiento):

1. Pre-filtro barato: suma de líneas de `labels.jsonl` (no parsea decisions).
2. Matriz precisa (`export_matrix_with_situations`) + `volume_gate`:
   calibrar solo si hay `>= min_new_labels` (20) etiquetas NUEVAS desde la
   última calibración efectiva, `>= min_samples` (20) totales y respetando el
   cooldown `min_interval_min` (60 min).

El progreso se persiste en `motor/calib/last_labels.json` (gitignored) tras
cada entrenamiento real; la rotación de `labels.jsonl` resetea el progreso.
Valores configurables: `RF_*` no aplica (son args del script o defaults de
`Config`: `min_new_labels`, `min_samples`, `min_interval_min`).
