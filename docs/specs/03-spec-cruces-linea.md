# Spec 03 — Cruces de línea

> Estado: aprobado (Fase 0). Se implementa en Fase 2. Sustituye la lógica embebida en `procesa_videosV6.py` (y el legacy `cruza_lineas*.py`, a eliminar).

## 1. Objetivo

Detectar cuándo un objeto cruza una línea virtual dibujada sobre la imagen de una cámara,
registrando dirección y foto del cruce, **sin falsos positivos por luz ni duplicados** por
pasos cercanos.

## 2. Comportamiento actual (a mantener)

- Las líneas se definen en `lineas` (camara_id, x1,y1,x2,y2) desde el panel.
- El análisis corre dentro del procesamiento de vídeo (`procesa_videosV6.py`): sustracción
  de fondo (MOG), contornos sobre el área de la línea, dos "gatillos" (X1_1/X2_1) para
  detectar dirección, debounce temporal, y guardado de foto + `guarda_cruce` en BD.

## 3. Problemas a resolver (Fase 2)

| # | Problema | Solución |
|---|---|---|
| P1 | Falsos positivos por cambios de luz (contornos grandes sin objeto) | Filtrar por área mínima + ratio de aspecto + persistencia temporal mínima del contorno. |
| P2 | Cruces duplicados (un mismo paso genera varios registros) | Debounce robusto por objeto: seguimiento del contorno (tracking simple IoU) en vez de solo tiempo global. |
| P3 | Fotos del cruce guardadas con retardo (se captura segundos después) | Capturar el frame en el instante del gatillo (frame congelado del buffer). |
| P4 | Parámetros mágicos dispersos | Config centralizada (dataclass) por cámara, calibrada con vídeos reales grabados. |

## 4. Diseño propuesto

1. **Módulo propio** `motor/cruces.py` (extraído de `procesa_videosV6.py`), testeable.
2. Pipeline por frame sobre el área de la línea:
   - MOG → umbral → morfología (open/close/dilate).
   - Contornos; filtro área mínima (`MinimoContorno`) + ratio de aspecto.
   - **Tracking ligero**: centroide + IoU para asociar el contorno entre frames.
   - Al cruzar la línea: gatillo único por objeto; dirección por orden de cruce de los
     extremos (A→B / B→A).
3. Salida: `cruces_lineas` (BD) + foto en `motor/fotos_lineas/<linea_id>/<uid>.jpg` con el
   frame exacto del cruce.
4. Harness de calibración: `motor/eval_cruces.py` corre sobre vídeos grabados y reporta
   cruces detectados para ajustar umbrales.

## 5. Criterios de éxito

- [ ] 1 cruce por paso real (sin duplicados).
- [ ] Cambios de luz no generan cruces.
- [ ] Dirección correcta en entrada/salida.
- [ ] Foto del cruce coincide con el instante del paso.
- [ ] Calibración reproducible sobre vídeos de test (comando documentado).
