# Spec 16 — Optimización de rendimiento del motor (CPU/RAM)

Estado: **F0 + F1 en curso** (2026-09-28).
Restricción del proyecto: **solo infraestructura, SIN tocar precisión**. Ningún
cambio de este plan modifica modelos, umbrales, `det_size`, `face_every`,
`min_sharpness`, capas de decisión ni el resultado de matching (TAR/FAR). Todo
cambio se verifica con `motor/eval/eval.py` como gate de regresión.

## 1. Problema

El servidor de producción (host `mail`, 10 vCPU, 58 GB RAM, exclusivo de RF)
mantiene la CPU al 100 % y el panel web va lento, con solo 14-20 GB de RAM en
uso y 40 GB libres. La sensación es "falta CPU", pero el diagnóstico es lo
contrario: **sobresuscripción de hilos**.

## 2. Baseline medido (2026-09-28, solo lectura)

| Métrica | Valor | Lectura |
|---|---|---|
| Cores / RAM | 10 vCPU / 58 GB (41 GB libres, 0 swap) | RAM de sobra |
| loadavg | 50.7 / 54.9 / 51.8 | 5× sobre 10 cores |
| runqueue (`vmstat r`) | 49-50 | 49 tareas listas para 10 cores |
| context switches | 79.000/s → 56.000/s | *thrashing* |
| CPU | us 85-93 %, id 0-2 % | saturada |
| Cámaras | 11 (ids 14-24) | 11 `guarda_movimientosV3` |
| Hilos/proceso | `procesa_video` 65, `clasificador` 55 | 5-6 sesiones ONNX × 10 hilos |
| Inferencia concurrente | 3 `procesa_video` + 2 `clasificador` | ~275 hilos ONNX |
| Datos | 51 personas, 253 fotos, 1.500 vídeos; `face_enc_v2` 3,3 MB | — |
| Config prod | `RF_LIMITE_VIDEOS=3`, `RF_CLASIF_CAMS_POR_PROC=8`, `RF_SR_EMBED_MIN_FACE=160` | — |
| VLM | `RF_VLM_ENABLED=0` | Ollama idle (no es el problema hoy) |

## 3. Causa raíz

`motor/core/model.py::_build_app` creaba `FaceAnalysis(...)` **sin
`SessionOptions`**. ONNX Runtime usa por defecto un pool *intra-op* del tamaño
de cores **físicos** (10) **por sesión**, y `buffalo_l` crea 5 sesiones
(`det_10g`, `2d106det`, `1k3d68`, `genderage`, `w600k_r50`) → ~50 hilos por
proceso. `OMP_NUM_THREADS=1` de los units **no** limita ese pool: verificado en
`insightface/model_zoo/model_zoo.py:96`, que solo reenvía
`providers`/`provider_options` a `InferenceSession` (nunca `sess_options`).

Con 5 procesos de inferencia a la vez: ~275 hilos ONNX sobre 10 cores → runqueue
~50 y 79k cambios de contexto/s. La CPU se consume en cambiar de hilo, no en
trabajo útil; el panel (Apache/php-fpm/MySQL) se queda sin turno.

## 4. Plan por fases

### F0 — Instrumentación y baseline  *(hecho en este cambio)*
- `deploy/perf_snapshot.sh`: foto read-only (loadavg, `vmstat`, hilos/proceso,
  counts, cgroups, backlog, disco). Sin `--out` no escribe nada.
- Baseline `motor/eval/eval.py` congelado como referencia de precisión.
- Este documento.

### F1 — Control de hilos (mayor impacto)  *(hecho en este cambio)*
- `motor/core/threads.py`: `ort_threads()` / `limit_threads()`, todo por env:
  - `RF_ORT_THREADS` (default **2**): hilos intra-op por sesión ONNX.
  - `RF_CV_THREADS` (default **1**): `cv2.setNumThreads`.
  - `RF_TORCH_THREADS` (default **1**; `rf-photo` lo sube a 4).
- `motor/core/model.py`: `_patch_ort_sessions()` inyecta `SessionOptions`
  (`intra_op=RF_ORT_THREADS`, `inter_op=1`, `ORT_ENABLE_ALL`, secuencial) en
  todas las sesiones de insightface vía parche contenido de
  `ModelRouter.get_model`. Idempotente y tolerante a fallos.
- `limit_threads()` llamado al inicio de `clasificador.py`, `procesa_video.py`,
  `guarda_movimientosV3.py`, `photo_worker.py` y `pose.py`.
- Units: `RF_ORT_THREADS=2`, `RF_CV_THREADS=1`,
  `OMP/OPENBLAS/MKL_NUM_THREADS=1` en `rf-detector`; `RF_CV_THREADS=1` en
  `rf-capturador`/`rf-photo`; mismos topes en `rf-panel-control`.
- **Criterio de aceptación:** runqueue < 15, ctx-switch < 20k/s, loadavg < 15,
  panel responsivo, `motor/eval` idéntico, backlog de vídeos estable.

### F1 — Resultado medido (2026-09-28, prod)

| Métrica | Antes | Después |
|---|---:|---:|
| Context switches/s | 79.040 | ~2.900 (~27× menos) |
| Hilos/proceso `procesa_video` | 65 | 12-16 |
| Hilos/proceso `clasificador` | 55 | 6 |
| Hilos/proceso `guarda_movimientos` | 20 | 11 |
| Hilos totales del sistema | 1.130 | 928 |
| Detección (dev, misma imagen) | — | idéntica (1 cara) |

### F2 — Topología y afinidad  *(hecho en este cambio)*
Reparto de los 10 cores con `CPUAffinity` (vía `sched_setaffinity`; el cgroup es
v1, por eso se usa `CPUAffinity` y no `CPUWeight`). Los hijos heredan la afinidad:

| Cores | Servicios | Motivo |
|---|---|---|
| 0-2 | `rf-live`, `rf-panel-control`, `rf-clasificador`, `rf-conciliador`, `rf-vinculador`, `rf-alarmador` + Apache/php-fpm/MySQL/OS (sin pinchar) | reserva de latencia para el panel |
| 3-5 | `rf-capturador` (11 `guarda_movimientos` + ffmpeg) | captura en tiempo real (Nice=-10) |
| 6-9 | `rf-detector` (clasificador + procesa_video) | inferencia diferible (Nice=10) |
| 3-9 | `rf-photo` | foto HQ diferible |

Al estar RF pinneado fuera de 0-2, la web conserva esos cores aunque el motor
esté saturado. Pendiente: afinar `RF_CLASIF_CAMS_POR_PROC` si la medición lo pide.

### F3 — SR/GFPGAN fuera del camino crítico (misma salida)
- Mover `enhance_embedding` a un worker por cola con hilos fijos; `photo_worker`
  ya está separado. **Descartado**: cuantizar/OpenVINO (riesgo numérico) y GPU
  (no hay).

### F4 — Caché en RAM del `FaceStore`  *(hecho en este cambio)*
`motor/core/store.py`: la galería se deserializaba con `pickle.load` COMPLETO en
cada acceso (`persons`/`person`/`person_encodings`); el matching recorre todas
las personas y hacía *P* lecturas completas por cada embedding query. Ahora hay
una caché en memoria invalidada por `(mtime_ns, tamaño)`: si otro proceso
escribe, se recarga. Los `_transaction` (read-modify-write) parten SIEMPRE de
disco para no mutar una caché desfasada. Resultado idéntico; libera CPU y disco
y aprovecha la RAM (58 GB).

### F5 — Servicios y web  *(PHP hecho; resto diferido)*
- **PHP (hecho)**: `admin/pages/dashboard/widgets.php` lanzaba un
  `systemctl is-active` por servicio (6 forks) en cada poll de `a=5` (cada 10 s)
  y `a=7` (cada 15 s, en todas las páginas) -> php-fpm al ~45 % de CPU. Ahora
  `dash_daemons_estados()` hace UN solo `systemctl is-active svc1 svc2 ...` y
  cachea el resultado 5 s en `/tmp` (compartido entre peticiones).
- **Diferido**: fan-out de `rf-live` (1 `ffmpeg` por cámara para N
  espectadores); quitar `ps aux`/`pgrep` de los bucles de `Jos_thread`/
  `detector.php`; cola/`inotify` en `clasificadorV2.php`; índices y *buffer
  pool* de MariaDB (el `innodb_buffer_pool_size` de 128 MB ya cubre una BD de
  ~1500 vídeos/253 fotos, por lo que no es rentable reiniciar MariaDB).

### F6 — Verificación y rollout
- Cada fase: worktree → commit → merge a `main` → `bash deploy/deploy_prod.sh`.
- `perf_snapshot` antes/después + gate `motor/eval`.
- Rollback por `git log`/`git diff` (nunca `reset --hard`).

## 5. Descartado (por la restricción "sin tocar precisión")

Cuantización / OpenVINO, cambiar `det_size`/`face_every`/`min_sharpness`,
desactivar SR-before-embedding o VLM/capas, tocar umbrales de matching, GPU
(no hay). Reescribir el framework: no rentable. Subir `RF_LIMITE_VIDEOS` sin
controlar hilos: empeora la contención.

## 6. Variables nuevas

| Variable | Default | Efecto |
|---|---|---|
| `RF_ORT_THREADS` | 2 | Hilos intra-op por sesión ONNX (no cambia resultados) |
| `RF_CV_THREADS` | 1 | Hilos internos de OpenCV |
| `RF_TORCH_THREADS` | 1 | Hilos de torch (rf-photo=4) |
