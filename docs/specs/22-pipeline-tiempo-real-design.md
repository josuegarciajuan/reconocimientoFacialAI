# Especificación de diseño — Pipeline de reconocimiento facial en tiempo real

## 1. Objetivo

Reducir al mínimo la latencia del reconocimiento facial sin perder calidad, sin
descartar vídeos nuevos y sin reservar capacidad de la flota SuperServer. Este
documento recoge el diseño aprobado y sirve de referencia para las fases de
implementación.

## 2. Alcance

Afecta a todo el camino crítico:

```
captura → movimiento → grabación → despacho → pool → clasificación → BD/panel
```

Se mantienen dos instancias independientes:

- `/rf`   — laboral (proyecto `reconocimientoFacial`, BD `reconocimientofacial`).
- `/ojos` — personal (proyecto `ojos`, BD `reconocimientofacial_ojos`).

## 3. Principios de diseño

1. **Nunca perder un vídeo nuevo**: si falta capacidad, se conserva y espera.
2. **Calidad antes que velocidad**: ninguna optimización se activa si degrada
   detección o identificación sin validación.
3. **Desacoplamiento**: captura, análisis y aplicación no se bloquean mutuamente.
4. **Recuperabilidad**: reinicios, caídas y resultados tardíos no duplican efectos.
5. **Identificación estable**: cada ejecución desde cero tiene una generación que
   invalida resultados anteriores.
6. **Competencia justa en la flota**: sin reservas; se adapta a la carga real.
7. **Métricas end-to-end**: se mide desde el fotograma hasta el resultado.

## 4. Estados de un trabajo

```text
pendiente → enviado → ejecutando → resultado_recibido → aplicando → aplicado
                ↑                       ↓
                └────── reintento ←──── requiere_intervención
```

## 5. Componentes previstos

| Componente | Responsabilidad |
|---|---|
| `pipeline_contracts` | Datos, identificadores y versiones compartidos. |
| `job_store` | Registro duradero local de trabajos y resultados. |
| `pipeline_metrics` | Medición correlacionada end-to-end. |
| `pipeline_dispatcher` | Envío asíncrono de trabajos a SuperServer. |
| `pipeline_collector` | Recepción y validación de resultados. |
| `pipeline_reconcile` | Recuperación y cobertura de trabajos. |
| `inference_worker` | Ejecutor reutilizable de inferencia en la pool. |
| `capture_units` | Publicación progresiva de unidades durante captura. |
| `recognition_session` | Agrupación incremental y resultados temprano/final. |
| `artifact_lifecycle` | Conservación y limpieza por dependencias. |

## 6. Resultados temprano y final

- **Temprano**: decisión con la evidencia recibida hasta el momento. Se muestra
  como provisional.
- **Final**: decisión cerrada tras las reglas temporales y de calidad.

Un resultado temprano nunca se presenta como identidad confirmada; se actualiza
o reemplaza al cerrar.

## 7. Generaciones

Cada reset/arranque desde cero crea una `run_generation`. Todos los trabajos,
resultados y artefactos llevan `instancia + generación + id_estable`. Un
resultado de otra generación se rechaza antes de tocar BD, galería o archivos
públicos.

## 8. Métricas obligatorias

- Tiempo entre captura del fotograma y publicación de unidad.
- Tiempo de espera local.
- Tiempo de espera en SuperServer.
- Tiempo de transferencia.
- Tiempo de carga de modelos.
- Tiempo de inferencia.
- Tiempo de aplicación de identidad.
- Tiempo hasta resultado temprano y final.
- Tasa de entrada vs tasa de finalización.
- Coste por tipo de tarea y nodo.

## 9. Plan de implementación

1. Fase 0 — Contratos, métricas y referencia de calidad.
2. Fase 1 — Cola duradera, generaciones e idempotencia.
3. Fase 2 — Despacho asíncrono sobre motor actual.
4. Fase 3 — Inferencia con modelos reutilizables en la pool.
5. Fase 4 — Cálculo consolidado y artefactos consistentes.
6. Fase 5 — Análisis durante la grabación.
7. Fase 6 — Reconocimiento incremental y publicación temprana.
8. Fase 7 — Optimización validada del camino crítico.
9. Fase 8 — Operación y pruebas de carga/recuperación.
10. Fase 9 — Reset completo de `/rf` y `/ojos`.
11. Fase 10 — Puesta en marcha y aceptación final.

## 10. Reset de datos

Se ejecutará en la fase 9. Se conservan:

- Cámaras, locales, líneas, planos, nodos, senderos.
- Usuarios, auto-login, alarmas_telefonos.
- Calibraciones y perfiles de cámara.
- Configuración de despliegue e instancia.

Se eliminan personas, galerías, fotos, vídeos, cruces, fichajes, estancias,
alarmas históricas, colas, cachés y estados derivados.

## 11. Notas

- git = código, no datos. Nunca se versionan `.env`, modelos, galerías ni logs.
- Cada cambio se trabaja en worktree y se integra en `main` antes de desplegar.
- Cada fase debe poder desactivarse o revertirse sin perder los datos nuevos.
