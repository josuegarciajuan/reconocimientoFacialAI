# Puesta en marcha y aceptación

Este documento describe el arranque controlado tras el reset total y los
criterios de aceptación del pipeline en tiempo real.

## Estado de partida

- Ambas instancias reseteadas: sin personas, vídeos, fotos, cruces ni colas.
- Configuración y cámaras intactas.
- Servicios del motor apagados.
- `rf-pipeline` instalado pero no habilitado.

## Orden de arranque

1. **Persistencia y cola**: `rf-pipeline` crea la generación y abre `motor/jobs/`.
2. **Despacho/recolección**: los ciclos arrancan en vacío.
3. **Panel en vivo**: `rf-live`.
4. **Captura**: solo cuando el sink/apply esté conectado y validado.

## Comando

```bash
# Arranque del servicio y del panel (sin captura)
bash deploy/start_pipeline.sh --instance ojos

# Estado
motor/venv/bin/python motor/pipeline_service.py --status --ruta /root/reconocimientoFacial

# Una pasada manual (sin dejar el servicio corriendo)
motor/venv/bin/python motor/pipeline_service.py --once
```

En `mail`:

```bash
bash deploy/start_pipeline.sh --instance mail
# o ambas
bash deploy/start_pipeline.sh --instance all
```

## Guarda de captura

La captura **no** se arranca por defecto. Para habilitarla:

```bash
# 1) En .env: RF_PIPELINE_CAPTURE_READY=1
# 2) bash deploy/start_pipeline.sh --instance ojos --enable-capture
```

La guarda existe porque el pipeline nuevo aún necesita tres piezas de
integración antes de procesar cámara real:

1. **Adaptador `video_units` en SuperServer** (worker `inference_pool.py`).
2. **Sink real de galería/BD/panel** (hoy el sink por defecto es JSONL).
3. **Aplicador de artefactos** (mover crops/bustos/frames y registrar fotos y
   cruces en la casa).

Sin esas piezas, la captura generaría trabajos que no producen identidades
visibles. Por eso la guarda es fail-closed.

## Validación local end-to-end

`motor/tests/test_fase10_puesta_en_marcha.py` valida:

- Petición `JobRequest` → worker → `result.json` (`JobResult`).
- Colector → `JobStore` en estado `resultado_recibido`.
- Procesador real con inferencia simulada → `UnitResult` con contexto de evento.

Ejecución:

```bash
motor/venv/bin/python -m pytest motor/tests/test_fase10_puesta_en_marcha.py -v
```

## Medición de latencia

```bash
motor/venv/bin/python motor/pipeline_report.py --local 1 --since-hours 24
motor/venv/bin/python motor/pipeline_report.py --local 1 --json
```

Devuelve por etapa p50/p95/p99, número de unidades, resúmenes tempranos/finales
y último estado de cola.

Criterios de aceptación:

- Todos los eventos nuevos quedan contabilizados.
- Ningún trabajo se elimina por saturación.
- La cola no crece de forma sostenida bajo carga representativa.
- p95 de `inferencia` y p95 de extremo a extremo se estabilizan.
- Un reinicio no duplica resultados ni publicaciones.
- Las identificaciones tempranas aparecen antes de cerrar el clip.

## Parada

```bash
# Parada segura y project-scoped (mantiene rf-live):
sudo deploy/rf_power.sh off

# Equivalente directo, con opciones de limpieza:
sudo deploy/rf_stop.sh --project <id> [--dry-run] [--purge-queues] [--purge-media]
```

`rf_power.sh off` pone el proyecto en modo `local`, para servicios/timers,
mata bridges/ffmpeg huérfanos y cancela en SuperServer los jobs activos de esa
instancia. `rf_stop.sh` no toca `taildeck.service` ni otros proyectos.
Cada UI (`/rf` en mail, `/ojos` en liveyourdre2) ejecuta el script de su propio
checkout y usa su propio `RF_SUPERSERVER_PROJECT`.

## Limitaciones conocidas

- El sink real de galería/BD y el aplicador de artefactos se conectarán sobre la
  interfaz `PublicationSink` y el colector, sin cambiar los contratos.
- La definición del proceso `video_units` debe añadirse al manifiesto de cada
  proyecto en el control plane de SuperServer.
- Las sesiones viven en memoria; tras un reinicio se reconstruyen a partir de los
  resultados pendientes en la cola duradera.
