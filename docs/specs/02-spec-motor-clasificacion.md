# Spec 02 — Motor de clasificación y enrolamiento

> Fuente de verdad del rediseño del núcleo. Estado: aprobado (Fase 0). Se implementa en Fase 1.

## 1. Objetivo

Sustituir el pipeline `face_recognition` (dlib, 128-d, Euclidiano) por un pipeline ArcFace
(512-d, coseno) con enrolamiento multi-pose en el alta, para cumplir NFR-ACC desde el día 1.

## 2. Decisiones técnicas

| Decisión | Valor | Motivo |
|---|---|---|
| Detector | **RetinaFace** (insightface `buffalo_l`) | Detección frontal + perfil robusta, landmarks. |
| Embedding | **ArcFace** (insightface, ONNX, CPU) | Robusto a pose/iluminación; 512-d. |
| Similitud | **Coseno** (equivalente a Euclidiana sobre L2-normalizados) | Mejor calibración de umbrales. |
| Diccionario | `face_enc_v2` (pickle versionado + schema) | Formato explícito, migración futura viable. |
| Escritura | write-temp-then-rename + FileLock | Sin corrupción ante cierre abrupto. |
| Enrolamiento | multi-pose (default: 3 poses; completo: 7) | Cubre frontal↔perfil desde el alta. |

## 3. Estructura (motor nuevo)

```
motor/
  core/
    __init__.py
    detector.py     # RetinaFace wrapper (carga única, detección + landmarks)
    embedder.py     # ArcFace ONNX wrapper (carga única, encoding en batch)
    matching.py     # coseno, agregación de plantilla, decisión ganador/segundo
    store.py        # face_enc_v2: schema, read/write atómico, FileLock, merge
    quality.py      # blur (varianza Laplaciano), oclusión, pose válida
  clasificador.py   # sustituye a procesa_fotos_def_borrosaparteV2.py
  enrolamiento.py   # sustituye a procesa_video_registro_1.py + _2.py
  pose.py           # sustituye a devuelve_posicion_cara.py (corregido)
  eval/
    eval.py         # métricas TAR/FAR sobre set etiquetado
    data/           # set etiquetado (gitignored)
  tests/            # pytest
  requirements.txt
  venv/             # gitignored
```

## 4. Lógica de matching (punto crítico)

Entrada: embeddings del evento (1..N caras). Salida: persona asignada o NUEVO.

1. **Agrupación intra-batería**: caras del mismo evento (<6 s) agrupadas por similitud
   (maneja 2+ personas juntas). Se conserva la idea de `procesa_fotos_def_borrosaparteV2.py`.
2. **Comparación multi-plantilla**: para cada persona del diccionario, distancia coseno del
   encoding contra **todas sus poses/encodings**; se toma la **mejor** (no la media), que es
   la que da robustez frontal↔perfil.
3. **Puntuación por persona**: media de las mejores distancias de las caras del grupo.
4. **Decisión**:
   - `mejor < umbral_seguro` → persona.
   - `mejor < umbral` y `diferencia con 2º > margen` → persona.
   - `mejor < umbral` pero diferencia con 2º pequeña → **no clasificar** (evita falsos; se
     queda en cola para revisión o auto-refinamiento sin etiquetar).
   - resto → **NUEVO** (se crea persona, sin auto-asignar a nadie).
5. **Auto-refinamiento**: al confirmar persona (umbral seguro o validación humana), se añaden
   los encodings nuevos a su plantilla (máx. N por persona, política FIFO por antigüedad y
   calidad de enfoque).

> Nota: los ~36 umbrales argv actuales se sustituyen por una única config (dataclass) con
> valores por defecto calibrados en evaluación, sobreescribible por local/cámara.

## 5. Enrolamiento multi-pose

- Reutiliza el wizard de poses (frente, 45°, 90°, arriba, abajo) ya existente en el panel.
- `pose.py` valida que la persona esté en la pose pedida (corrigiendo B1/B2 del inventario).
- `enrolamiento.py` guarda **todas las poses** como encodings de la persona en `face_enc_v2`.
- Modo rápido: frente + 90° izq + 90° der. Modo completo: + 45° izq/der + arriba + abajo.

## 6. Testing

- `pytest` en `motor/tests/`: matching (casos: 1 persona, 2 personas juntas, pose nueva,
  umbral no seguro), store (concurrencia, atomicidad, corrupción).
- Evaluación: `motor/eval/eval.py` mide TAR/FAR sobre `data/` etiquetado.
- Fixtures: encodings sintéticos + imágenes reales de prueba.

## 7. Criterios de éxito

- [ ] NFR-ACC: TAR ≥95% frontal, ≥90% perfil; FAR <1% en `eval.py`.
- [ ] `face_enc_v2` sobrevive a cierres abruptos (test de concurrencia).
- [ ] Config en un solo fichero; cero argv mágicos.
- [ ] `clasificador.py` procesa el flujo `sinclasificar/` con el mismo contrato de carpetas.
