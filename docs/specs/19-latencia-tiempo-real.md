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

## 2. Plan por fases (estado)

- **P0 — Medición** ✅ implementado y desplegado. Contrato de eventos `latencia` +
  CLI + `ws.php embudo_latencia`.
- **P1 — Troceado intra-vídeo** ✅ implementado (ambos repos), **inactivo**:
  - Proyecto: `process_video(--from/--to)`, `motor/video_orchestrator.py`,
    selector `RF_VIDEO_MODE=pool|distributed` (default `pool`).
  - SuperServer: definición `rf-video-segments` (split por segmentos + `pull`
    desde la casa), canal remoto `ss-dist-submit` + `server/distspool.js`.
  - Sin activar: motor apagado, modo `local`, `taildeck` sin reiniciar.
- **P2 — Cola larga / camino síncrono** ✅ implementado (inactivo). El escritor
  único de galería ya agrupa escrituras por sub-clúster (`begin_defer`/
  `flush_defer`). Se añade `RF_SYNC_TAIL_BUDGET_MS` (default 0): corta VLM/OpenAI
  por tiempo por cara (equivalente a "proveedor sin respuesta"). La separación
  completa en un worker de fondo queda pendiente de validar con datos reales.
- **P3 — Dos niveles de detección** ✅ implementado, **flag OFF**
  (`RF_TWO_STAGE_DET=0`): pasada barata + `RetinaFace@1280` solo donde hay cara.
  Activar solo tras gate `motor/eval` (TAR/FAR) + cobertura del embudo.
- **P4 — (opcional) Streaming durante la grabación** ⏸️ **diferido**: solo si
  P1-P3 no bastan; requiere tocar la captura (`guarda_movimientosV3`) y validar
  con el motor activo.

## 3. Reversibilidad

Todo cambio de P2–P4 detrás de flags en `.env`; P1 conserva el modo `pool` como
fallback automático. Rollback por `git log`/`git diff` + flags, nunca
`reset --hard`.
