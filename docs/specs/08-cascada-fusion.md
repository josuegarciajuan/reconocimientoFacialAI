# Spec 08 — Cascada de fusión para eliminar personas duplicadas (F0-F7)

> Estado: implementado (F0-F7). Cada capa/fase con feature-flag en `Config`,
> OFF por defecto → producción no cambia hasta activar las fases explícitamente.

## Problema
Una persona vista en un ángulo distinto al de su galería (p.ej. primera vez de
PERFIL y luego FRONTAL) no se asocia por cara sola → PERSONA DUPLICADA.
Causas raíz: galería sin cobertura de pose, veredicto "uncertain" que asigna pero
NO enriquece la galería, un único umbral global para todo par de poses, y nula
explotación de torso/ropa/contexto.

## Arquitectura (decisión cerrada)
Sustituir la decisión binaria por una CASCADA DE CAPAS con FUSIÓN PONDERADA:

| Capa | Señal | (s, c) |
|---|---|---|
| L1a cara | ArcFace (existente) | s=coseno, c=nitidez+margen+nivel |
| L1b torso/ropa | histograma HSV+grilla | s=similitud, c=visibilidad×TTL |
| L1c zonas/ángulos | pose-consciente + silueta | s=score pose-aware, c=compatibilidad×silueta |
| L2 VLM local | Ollama qwen2.5vl:3b | s=probability_same, c=\|p−0.5\|·2 |
| L3 OpenAI | gpt-4o-mini | ídem (solo tras L2, en gris) |

Fusión: `w_i = c_i·p_i` ; `S = Σ(w_i·s_i)/Σ(w_i)` (pesos-prior cara 0.60,
torso 0.15, llm 0.25; capa sin señal se redistribuye sola). Escalada con
early-exit; invariante de seguridad: cara con confianza alta NUNCA degrada a
"new" (solo a "uncertain" con evidencia contraria fortísima); gris tras L3 →
UNCERTAIN → revisión manual (`motor/revision/`), nunca duplicado silencioso.

## Desviaciones documentadas frente al plan original
1. **Modelo VLM**: el registro de Ollama ya no ofrece `qwen2-vl:4b`; se usa
   `qwen2.5vl:3b` (Q4_K_M, ~2.9 GB, edge AI) con el MISMO prompt validado (§7).
2. **num_ctx 4096**: el encoder de visión genera ≥1024 tokens/imagen
   (`--image-min-tokens 1024`); 2 imágenes superan 2048 → num_ctx 4096 mínimo.
3. **Latencia real**: host compartido y saturado (load 50-67 por autotube + 20
   procesos RF + ffmpeg). Prompt de visión a ~4 tok/s: ~5 min/par con 2 imágenes.
   Mitigación: redimensionado a 384px, timeout 90s, mutex global, memory guard
   (<2 GiB diferir, <1 GiB omitir) → la capa DEGRADA en vez de bloquear. Con el
   host en calma, funciona (probado: HTTP 200 + JSON válido).
4. **L1c sin re-embedding por defecto**: se implementó como matching
   pose-consciente + silueta geométrica (barato); el re-embedding de zonas queda
   disponible vía `zone_crops` para las capas VLM (contexto).

## Fases y feature-flags
| Fase | Contenido | Flag |
|---|---|---|
| F0 | Ollama + .env (RF_LLM_*, RF_VLM_*) + smoke_llm.py | — |
| F1 | Crop de torso + `appearance.py` + store.apariencia | `torso_enabled` |
| F2 | `zones.py` + matching pose-consciente + **fix uncertain enriquece** | `zones_enabled` |
| F3 | `fusion.py` + `calibration.py` + `feedback.py` + cascada en clasificador | `cascade_enabled`, `feedback_enabled`, `calibration_enabled` |
| F4 | `vlm_local.py` (worker único Ollama, memory guard, mutex, cache) | `vlm_enabled` |
| F5 | `llm_openai.py` (presupuesto diario, cache, retry) | `openai_enabled` |
| F6 | snapshot+journal+`--rollback` en backfill_merge/limpiar_catchall | — |
| F7 | PersonDetector (MOG2) + crops de cuerpo `*_nocara` + torso+VLM | `body_match_conf` |

## Seguridad / privacidad
- Key OpenAI SOLO en `.env` (gitignored); rotar la usada en validación.
- VLM local no sale del servidor. OpenAI solo en extremos, con cache por hash
  (no se persisten fotos, solo hash+resultado). GDPR/consentimiento pendiente
  de dejar constancia en el panel.

## Verificación
- `motor/venv/bin/python -m pytest motor/tests -q` (120+ tests, sin red ni modelos).
- `motor/venv/bin/python -m motor.eval.eval --pose-aware` (TAR/FAR).
- Smoke VLM/OpenAI: `motor/venv/bin/python motor/scripts/smoke_llm.py --img-a ... --img-b ...`.
- Calibración diaria: `motor/venv/bin/python motor/calibrar.py` (timer rf-calibra).
