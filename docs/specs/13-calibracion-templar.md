# 13 · Calibración guiada: La Forja · Templar

> **Qué resuelve**: los parámetros configurables del sistema (por cámara y globales)
> dejaron de ajustarse "a ojo". Templar los calibra con **rituales guiados en vivo**
> que miden con el **mismo código de producción** (nunca una copia) y proponen valores
> con su motivo; un humano revisa el diff y aplica o descarta. Además, una vigilancia
> diaria detecta si una cámara se ha movido.

## Acceso

`La Forja` (⚒️) → pestaña **Cámaras** → sub-pasos:

- **Forjar** — crear cámara (sin cambios).
- **Editar** — datos + "Parámetros de análisis" agrupados por dominio
  (🎯 Movimiento / ⚡ Rendimiento / 💾 Almacenamiento), botón **↺** por campo
  (restaurar a fábrica) y badges **recomendado: N** que llegan del calibrador.
- **Templar** — el calibrador guiado (este documento).

## Valores de fábrica y journal (todo reversible)

- Fuente de verdad de los "valores de fábrica": `config/config.php` (`CONFIG_*`) para
  los 7 parámetros por cámara, y los defaults de `motor/core/config.py` +
  `.env.example` para los globales.
- **Niveles de restauración**: `↺` por campo, "Restaurar valores de fábrica" por
  cámara (2/60/220/14/60/60/1), "Restaurar todos los globales" (borra las líneas
  `RF_*` del `.env` para que aplique el default del código; con copia `.env.bak.<ts>`).
- **Journal**: tabla `calibraciones` (runtime) guarda `antes → despues` de cada cambio
  aplicado, por cámara o global, para auditoría y deshacer.

## Rituales (cada uno se ejecuta por separado)

Elige cámara, ritual y duración (5–60 s) y pulsa **▶ Iniciar ritual**. El probe
(`motor/calibrador.py`) abre el RTSP, mide en vivo y pinta el **frame anotado**
(verde = cara aprovechable, ámbar = pequeña/borrosa) + métricas. Al terminar,
propone la recomendación con motivo; **nada se aplica solo**.

| Ritual | Qué haces delante de la cámara | Verde cuando… | Calibra |
|---|---|---|---|
| **A · Alcance** | te pones a distintas distancias (cerca/media/lejos) | la cara se detecta con px y nitidez suficientes | `RF_SR_EMBED_MIN_FACE`, `RF_MIN_SHARPNESS`, avisa si hace falta `RF_DET_SIZE=1280` |
| **B · Paso veloz** | pasas rápido delante de la cámara | el paso rápido no se pierde (frames con cara + disparo) | `fps`, `sensibilidad` |
| **C · Disparo** | fase **C1** camina despacio (debe disparar) y fase **C2** agita la mano lejos (no debe) | C1 dispara y C2 no | `dontCare`, `porcentaje_mov`, `RF_MOV_THRESHOLD` (combina las 2 fases) |
| **D · Cruce de línea** | cruzas la línea N veces (espera 2-3 s entre cruces) | detecta los cruces y su dirección | `RF_CRUCE_AREA_MIN` (baja si no detecta, sube si hay ruido) |
| **E · Identidad** (offline) | sin cámara: corre TAR/FAR sobre `motor/eval/data` | dataset con 3+ personas × 3 poses | `RF_MATCH_THRESHOLD`, `RF_MARGIN`, `RF_SECURE_THRESHOLD` |
| **F · Enfoque** | sostienes la cara a la distancia MÁXIMA de reconocimiento | la cara pasa el umbral de nitidez a esa distancia | `RF_MIN_SHARPNESS` |

**Aplicar**: la recomendación aparece como "actual → propuesto" con motivo. Pulsa
*Aplicar recomendación* (escribe en la cámara, con journal) o descártala. Los badges
de "Editar" reflejan la última recomendación.

## Modo "Configuración general"

En Templar, modo **Configuración general**: tabla de los globales `RF_*` con su valor
actual, fábrica y `↺` individual, botones "Restaurar todos los globales" y "Aplicar
recomendaciones globales" (escribe en `.env` con backup + journal). Aquí también viven
los umbrales de matching (`RF_MATCH_THRESHOLD`/`RF_MARGIN`/`RF_SECURE_THRESHOLD`),
de cruce (`RF_CRUCE_*`) y de SR/detección.

## Vigilancia de deriva (cámara movida) — 1×/día

Timer systemd `rf-vigilar-deriva` (03:10) ejecuta `motor/vigilar_deriva.py`:

1. **Firma estructural** por cámara: fondo **mediana** de ~1 frame/s (30 s) → CLAHE
   (tolera luz) → bordes Sobel en rejilla 8×6 (48 valores).
2. Comparación con una **referencia de largo plazo (EMA)** que **solo se actualiza en
   días estables** (una caja que aparece un día no se hornea).
3. **Regla anti-falsa-alarma**: aviso solo tras **2 días consecutivos** de similitud
   < 0.75, con la **zona localizada** (top celdas cambiadas).

- Aviso en el dashboard (KPI "anomalías") y en Templar · General (tabla de estado).
- **«Comprobar»**: pasada puntual (~20 s en segundo plano; refresca la página).
- **«↺ Ref.»**: restablece la referencia — úsalo **después de mover la cámara a
  propósito** (o al corregir su orientación) para no arrastrar la alerta.

## Herramientas CLI (barridos offline)

```bash
# Barrido de movimiento: vídeos positivos (movimiento confirmado) y negativos
# (escena vacía). Barre redimesionframe + dontCare juntos (unidades acopladas)
# y escribe la recomendación por cámara para los badges del panel.
motor/venv/bin/python motor/calibrar_movimiento.py \
    --positivos motor/calib_mov/positivos --negativos motor/calib_mov/negativos \
    --thresholds 18,21,24 --dontcares 180,220,260 --porcentajes 50,60,70 \
    --resizes 50,60,70 --camara 13 --ruta /root/reconocimientoFacial

# TAR/FAR del matcher con salida JSON + sugerencia de umbrales (lo usa el ritual E)
motor/venv/bin/python -m motor.eval.eval --data-dir motor/eval/data --pose-aware \
    --json-out /tmp/eval.json
```

## Datos runtime (git = código, no datos)

Todo lo que generan el calibrador y la deriva es runtime y **no se versiona**:
`motor/calibrador/{jobs,resultados,frames,recomendaciones,deriva}` (gitignored).

## Solución de problemas

- **"No se pudo abrir el stream RTSP" / "sin señal"**: la cámara no responde desde el
  servidor (RTSP sobre TCP). Revisa `url_conexion` y la red; el ritual E no necesita
  cámara.
- **Ritual E: "No existe el set etiquetado"**: puebla `motor/eval/data` con
  3+ personas × 3 poses (frente + perfiles) — ver `motor/eval/README.md`.
- **Ritual D: "la cámara no tiene líneas"**: traza las líneas en la pestaña **Líneas**
  antes de calibrar el cruce.
- **Probe lento / mucha RAM**: cada probe carga InsightFace (~1-1,5 GB). Es un proceso
  puntual de 5-60 s; no lanzar varios rituales a la vez.
- **Falsa alerta de deriva**: comprueba que la cámara no se movió; si se movió a
  propósito, pulsa **«↺ Ref.»** en Templar · General.
