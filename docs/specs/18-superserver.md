# 18 — Integración con SuperServer (M3)

Estado: **implementado y en modo `local`** (comportamiento idéntico al actual).
Documento del lado del proyecto; la plataforma se describe en el repo `superserver`
(`spec/17` metodología, `spec/19` requisitos).

## Interruptor

- Fichero: `/var/lib/taildeck/projects/reconocimientoFacial.mode` (`local` | `superserver`).
  Lo escribe el panel (pantalla **Proyectos**); si no existe → `local`.
- `libs/superserver.php::ss_mode()` lo lee.
- **`local` (por defecto):** `detector.php` ejecuta `motor/procesa_video.py` como siempre.
- **`superserver`:** `detector.php` ejecuta `motor/pool_bridge.py` con la misma vida que el
  proceso clásico (su `--tag` mantiene el `pgrep` del detector y el control de marcadores).

## Proceso externalizado (fase 1): `video_faces`

```
detector.php ──(modo superserver)──▶ pool_bridge.py
      │                                  │ 1. líneas de la cámara (ws.php, casa)
      │                                  │ 2. petición al spool de SuperServer
      │                                  │ 3. espera returns/reconocimientoFacial/<job>/
      │                                  │ 4. aplica efectos y borra vídeo+marker
      ▼                                  ▼
  marker aux/<video>.txt      worker: procesa_video_pool.py (sin efectos)
```

### Sin efectos en el worker
`procesa_video_pool.py` llama a `process_video(..., efectos=False)`:
- no borra el vídeo, no toca markers, no llama a `ws.php`, no escribe el embudo;
- escribe caras en `motor/caras/sinclasificar/...` y fotos de cruce en
  `motor/fotos_lineas/<linea>/...` dentro del sandbox;
- devuelve `efectos.json` con cruces (línea, fecha, dirección, x, y, uid) y métricas.

### Efectos en la casa (idénticos)
`pool_bridge.py` al recibir el resultado:
1. mueve las caras (`<cam>`, `<cam>_busto`, `<cam>_cuerpo`) a su ruta real;
2. mueve las fotos de cruce y ejecuta `php ws.php guarda_cruce` con los mismos datos;
3. escribe el embudo (`motor/core/embudo.py::log_evento`);
4. borra el vídeo origen y el marker `aux/<fichero>.txt`;
5. marca el resultado como aplicado (`.aplicado`).

## Reversibilidad

- Apagar el proyecto en el panel (modo `local`) devuelve el flujo clásico al instante.
- Si el puente muere, el detector conserva su lógica de marcador huérfano y reintentos.

## Pruebas

- `motor/tests/test_pool_bridge.py` — forma de la petición y rutas del contrato.
- Gate del deploy: `php -l` + `py_compile` sobre lo cambiado (ver `deploy/deploy_prod.sh`).
- Mini-prueba de equivalencia (M5): copia real fuera de la cola, ejecución local vs pool
  en cada nodo, comparación de caras/cruces y teardown.
