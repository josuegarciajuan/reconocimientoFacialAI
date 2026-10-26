# Operación del pipeline en tiempo real

Este documento describe el servicio `rf-pipeline`, su configuración, operación,
retención y recuperación. El servicio es el pegamento entre la captura, la cola
duradera, la pool y la publicación de resultados.

## Componentes

`motor/pipeline_service.py` ejecuta en un solo proceso:

| Ciclo | Función | Intervalo por defecto |
|---|---|---|
| `dispatch` | Envía trabajos pendientes a SuperServer | 2 s |
| `collect` | Recoge y valida resultados | 2 s |
| `reconcile` | Recupera trabajos huérfanos | 30 s |
| `sessions` | Cierra sesiones inactivas y publica finales | 10 s |
| `retention` | Limpia `.units/` antiguos no referenciados | 1 h |
| `metrics` | Emite estado de cola a `pipeline_metrics_<local>.jsonl` | 30 s |

Al arrancar, ejecuta una reconciliación completa antes de escuchar.

## Interruptor de seguridad

La unit `rf-pipeline.service` se instala **apagada** y con:

```ini
Environment=RF_PIPELINE_ENABLED=0
```

El servicio, aunque se lance, no arranca si `RF_PIPELINE_ENABLED=0`. La puesta en
marcha controlada (Fase 10) debe cambiar el valor a `1` y habilitar la unit.

## Configuración

| Variable | Default | Descripción |
|---|---|---|
| `RF_PIPELINE_ENABLED` | `0` (unit) / `1` (CLI) | Interruptor de arranque |
| `RF_PIPELINE_DISPATCH_S` | `2` | Intervalo de despacho |
| `RF_PIPELINE_COLLECT_S` | `2` | Intervalo de recolección |
| `RF_PIPELINE_RECONCILE_S` | `30` | Intervalo de reconciliación |
| `RF_PIPELINE_SESSIONS_S` | `10` | Cierre de sesiones inactivas |
| `RF_PIPELINE_RETENTION_S` | `3600` | Limpieza de `.units/` |
| `RF_PIPELINE_METRICS_S` | `30` | Emisión de métricas de cola |
| `RF_PIPELINE_MAX_SENT` | `20` | Ventana máxima de trabajos enviados |
| `RF_PIPELINE_CLOSE_AFTER_S` | `30` | Inactividad para cerrar sesión |
| `RF_PIPELINE_UNITS_MAX_AGE_H` | `6` | Antigüedad máxima de `.units/` |
| `RF_PIPELINE_PUBLICATIONS` | `motor/logs/pipeline_publications.jsonl` | Sink JSONL operativo |
| `RF_PIPELINE_GALLERY` | vacío | JSON de galería `[{person_id,label,embedding}]` |
| `RF_CLUSTER_COSINE` | `0.50` | Umbral de agrupación |
| `RF_MATCH_MIN_SCORE` | `0.45` | Score mínimo para confirmar |
| `RF_MATCH_MIN_MARGIN` | `0.08` | Margen mínimo sobre el segundo |
| `RF_MIN_FACES_CONFIRM` | `1` | Caras mínimas para confirmar |
| `RF_MIN_QUALITY_CONFIRM` | `0.0` | Calidad mínima para confirmar |

## Comandos

```bash
# Estado del servicio (JSON)
motor/venv/bin/python motor/pipeline_service.py --status

# Una sola pasada (operación manual o pruebas)
motor/venv/bin/python motor/pipeline_service.py --once

# Arranque como servicio (cuando se habilite)
systemctl enable --now rf-pipeline
systemctl status rf-pipeline
journalctl -u rf-pipeline -f
```

## Estado y observabilidad

`--status` devuelve, entre otros:

- `generation` activa,
- `queues` por estado (`pendiente`, `enviado`, `ejecutando`, `resultado_recibido`, `aplicando`, `aplicado`, `reintento`, `requiere_intervencion`),
- `sessions` activas y confirmadas,
- `cycles` y `errors` por ciclo,
- porcentaje de disco usado.

Métricas por etapa: `motor/logs/pipeline_metrics_<local>.jsonl`.
Publicaciones operativas: `motor/logs/pipeline_publications.jsonl` (una línea por
upsert, con `publication_key`, `person_id`, `confirmed`).

## Retención de `.units/`

Los segmentos se conservan mientras algún trabajo activo los referencie. La
limpieza:

1. Recorre `motor/videos/<local>/<cámara>/.units/<evento>/`.
2. Calcula la antigüedad del fichero más reciente.
3. Borra el evento solo si todos sus ficheros superan `RF_PIPELINE_UNITS_MAX_AGE_H`
   y ninguna ruta está referenciada por un trabajo activo.

El vídeo completo concatenado (`motor/videos/<local>/<cámara>/<evento>.mp4`) no
se toca por esta limpieza.

## Recuperación

- **Reinicio del servicio**: al arrancar reconcilia trabajos enviados sin
  intento reciente y detecta resultados ya presentes en el directorio de retornos.
- **Resultado duplicado**: `save_result` reutiliza la fila existente; el colector
  marca `.pipeline_collected` para no releer.
- **Resultado de generación antigua**: rechazado antes de tocar BD/galería.
- **Worker caído**: el trabajo vuelve a `pendiente` (reintento) hasta
  `RF_PIPELINE_MAX_SENT`/límite de intentos; después pasa a
  `requiere_intervencion`.
- **Red caída**: el despacho falla de forma tolerante; el trabajo permanece en la
  cola y se reintenta en el siguiente ciclo.

## Pruebas de carga

`motor/tests/test_fase8_operacion_carga.py` incluye:

- 100 trabajos drenados en ventanas de 20, sin duplicados.
- Recolección duplicada idempotente.
- Retención con referencias activas.
- Arranque/parada de hilos y `--once`.

## Limitaciones conocidas

- El sink por defecto es JSONL. La escritura en la galería/BD real (y la
  actualización del panel) se conectará en la puesta en marcha.
- La galería se carga desde `RF_PIPELINE_GALLERY` si se indica; sin ella, el
  pipeline agrupa pero no identifica.
- La definición `video_segment` en el control plane de SuperServer debe existir
  antes de habilitar el despacho real (Fase 10).
