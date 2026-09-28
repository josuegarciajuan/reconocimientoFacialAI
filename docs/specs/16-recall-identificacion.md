# Spec 16 — Recall de identificación (captura → extracción → clasificación)

> Estado: en implementación. Cambios por fases, cada uno desplegable y reversible.

## 1. Problema

No se captura al 100% de las personas que pasan ante las cámaras: hay gente que
nunca queda registrada. El pipeline tiene varias etapas donde una persona puede
"escaparse" antes de llegar a `face_enc_v2`:

1. **Captura** (`capturador.php` → `guarda_movimientosV3.py` + `motor/core/motion.py`):
   el disparador exige movimiento en ≥60% de 28 frames (`segundos_analizar=2 × fps=14`)
   y solo mira el **contorno mayor** ≥ `dontCare=220` px² sobre un frame reescalado al
   60% con `GaussianBlur(21)`. Personas rápidas, lejanas o breves no disparan grabación.
2. **Extracción** (`motor/procesa_video.py`): analiza 1 de cada `face_every=2` frames y
   **descarta** toda cara con `face_sharpness < min_sharpness (70)` sin plan B.
3. **Clasificación** (`motor/clasificador.py`): vuelve a filtrar por nitidez y por
   `face_min_side=52` y manda a `motor/removidas/nopasafiltros` (pozo sin fondo).
4. **F7** (de espaldas): nunca crea persona; si torso+VLM no concluyen → revisión.
5. **Operación**: sin medición del embudo; `RF_LIMITE_VIDEOS=1`; el `detector.php`
   bloquea con `sleep(6)` por cámara; tras 3 fallos un vídeo se borra sin extraer caras.

## 2. Objetivo

Máximo recall primero (que nadie quede sin registrar), reconciliando identidades
después. **No se relaja la postura anti-mezcla**: `admission_cosine`,
`cluster_confirm` y la decisión por autoridad/veto se mantienen. Lo que cambia es
el destino de lo descartado (revisión/provisional en vez de borrado) y la
sensibilidad de captura/extracción.

Decisiones del usuario que acotan el diseño:

- Prioridad: **máximo recall primero**, luego continuidad de identidad.
- **Sin grabación continua**: se mantiene el modelo "clip por movimiento", afinando
  el disparador.

## 3. Fases

### Fase 0 — Instrumentación del embudo (medir)

Sin cambiar comportamiento. Contadores por vídeo y por decisión a
`motor/logs/embudo_<local>.jsonl`, más un CLI/`ws.php` que agrega:

- cobertura = `estancias / cruces_lineas`;
- desgloses: caras detectadas/guardadas, descartes por nitidez/dedup, cuerpos,
  verdicts y descartes de clasificación.

Aceptación: obtener en prod el % por etapa y el motivo dominante de fuga.

### Fase 1 — Sensibilidad del disparador

- `motion.py`: disparar también por nº/suma de contornos, no solo el mayor.
- Pre/post-roll 2 s → 4 s.
- Parámetros por cámara: `threshold`, `blur`, `dilate`, `seg_antes`, `seg_despues`
  (NULL = valor global de `.env`).
- UI de cámara + CLI opt-in para aplicar recomendados a cámaras existentes.
- Cierre del hueco de reinicio del capturador y aviso de fallo RTSP.

Defaults propuestos: `porcentaje_mov` 60→35, `dontCare` 220→100, `threshold` 21→15,
`blur` 21→15, pre/post 4 s.

### Fase 2 — Separar "capturar" de "admitir"

- `face_every` 2→1 (configurable) y/o dos niveles de `det_size`.
- Bajar `min_det_score` de captura (0.4→0.3).
- **Eliminar el descarte duro por `min_sharpness`**: guardar siempre y registrar
  la nitidez para que el clasificador ordene.
- El clasificador no manda a `nopasafiltros` si hay cara: procesa la mejor y la
  encamina a revisión/provisional sin contaminar la galería.
- Recuperación con SR (MF-SR / `enhance_embedding`) para caras pequeñas/borrosas.

Flags: `RF_FACE_EVERY`, `RF_CAPTURE_KEEP_ALL`, `RF_CAPTURE_MIN_DET`, `RF_SR_MF_ENABLED`.

### Fase 3 — Recuperación y reconciliación

- Timer `rf-reprocesa` diario: `reprocesar.py --videos` sobre la retención (30 d),
  con idempotencia por vídeo (marker/columna `videos.reprocesado`).
- `consolidar_nacidos`: guarda de co-ocurrencia temporal (quien aparece a la vez =
  distinto) + evidencia multi-pose.
- F7: persona provisional por batería en vez de solo revisión.
- Informe de pares casi-duplicados con co-ocurrencia.

Flags: `RF_REPROCESA_ENABLED`, `RF_PROVISIONAL_BACKS`.

## 4. Seguridad y reversibilidad

- Todo detrás de feature-flags en `.env`; rollback sin desplegar código.
- Admisión a galería intacta: la baja calidad va a revisión/provisional, nunca a
  `face_enc_v2` como encoding de decisión hasta confirmar.
- Cada fase es un commit atómico; merge a `main` + `bash deploy/deploy_prod.sh`.
- Migraciones SQL nuevas e idempotentes en `sql/` (aplicadas por `deploy_prod.sh`).

## 5. Validación

- Tests unitarios del motor (`motor/tests`, `motor/venv/bin/python -m pytest`).
- `motor/eval/eval.py` (TAR/FAR) para confirmar que no empeoran los falsos match.
- Métrica de aceptación por fase: sube `estancias` y la cobertura del embudo sin
  aumento de fusiones/`Unir` anómalas.
