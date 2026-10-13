# Spec 19 — Latencia end-to-end y tiempo real

Estado: **P0 (medición) implementado**. Objetivo: p95 fin-a-fin
(cierre de clip → foto clasificada en el panel) **< 60 s** en condiciones
normales, sin crecimiento ilimitado de cola.

Contexto: el sistema llegó a acumular un retraso de ~2 días con pocas cámaras.
El cuello documentado (`docs/specs/16`) es CPU de inferencia (`RetinaFace@1280`
≈ 2,4 s/frame) + arranque de modelos por proceso, más la **aplicación de
`classify`** (escritor único en la casa). Con la flota SuperServer activa, la
palanca principal es **trocear el vídeo** (una unidad lógica → N unidades en
paralelo) y **sacar la cola larga** del camino visible.

## 1. Contrato de medición (P0/WS1)

Eventos `latencia` en `motor/logs/embudo_<local>.jsonl` (append bajo flock,
best-effort, nunca rompe el pipeline):

| Etapa | Emisor | Campos |
|---|---|---|
| `extract` | `motor/procesa_video.py` (local) y `motor/pool_bridge.py` (superserver) | `cam`, `fichero`, `frames`, `t_clip`, `t_cierre`, `t_ini`, `t_fin`, `dur_s`, `espera_s` |
| `classify` | `motor/clasificador.py` (`--serve` y bucle principal) | `cam`, `n_baterias`, `t_ini`, `t_fin`, `dur_s` |
| `bd` | `clasificadorV2.php` (foto publicada) | `cam`, `foto_id`, `frame_ts`, `e2e_s` |

- `dur_s = t_fin - t_ini` (latencia de la etapa).
- `espera_s = t_ini - t_cierre` (tiempo en cola desde el cierre del clip).
- `e2e_s = t_bd - frame_ts` (fin-a-fin, el KPI).

Agregado por percentiles: `motor/core/embudo.py::resumir_latencia` y
`libs/embudo.php::embudo_resumen_latencia` (mismo contrato).
Consumo:
- CLI: `motor/venv/bin/python motor/embudo.py <local> [--desde YYYY-MM-DD]`.
- Panel/HTTP: `ws.php embudo_latencia <local> [desde]` (solo lectura).

## 2. Plan por fases

- **P0 — Medición** (esta fase): contrato de eventos + CLI + `ws.php`. Sin
  cambio de comportamiento.
- **P1 — Troceado intra-vídeo**: definición `rf-video-segments` en SuperServer
  (split del clip por ventanas de ~10 s) + canal remoto casa→control plane
  (`ss-dist-submit`, pull desde casa) + `motor/video_orchestrator.py` en la casa
  que envía y aplica los mismos efectos. `RF_VIDEO_MODE=pool|distributed` con
  fallback. Esperado: ÷3-4.
- **P2 — Cola larga asíncrona + aplicación de `classify`**: VLM/OpenAI/SR/body en
  worker de fondo (identidad provisional inmediata); acelerar el escritor único.
- **P3 — Dos niveles de detección** (`RF_TWO_STAGE_DET`, gate `motor/eval`): pasada
  barata + `RetinaFace@1280` solo donde hay cara. Esperado: ÷2-3 en coste/frame.
- **P4 — (opcional) Streaming durante la grabación.**

## 3. Reversibilidad

Todo cambio de P2–P4 detrás de flags en `.env`; P1 conserva el modo `pool` como
fallback automático. Rollback por `git log`/`git diff` + flags, nunca
`reset --hard`.
