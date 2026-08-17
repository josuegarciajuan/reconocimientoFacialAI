# Spec 01 — Requisitos y Restricciones

> Documento vivo. Fuente de verdad de requisitos. Actualizar antes que el código cuando cambie el alcance.
> Estado: **aprobado para Fase 0** · Fecha: 2026-08-17

## 1. Objetivo del proyecto

Sistema de reconocimiento facial en tiempo real para interiores con varias cámaras RTSP:
detectar caras, clasificarlas automáticamente por persona, trazar rutas entre cámaras y
detectar cruces de línea virtuales. Reconstruir el motor sobre embeddings modernos
(ArcFace) con **alta precisión desde el primer día para personas enroladas**, manteniendo
el auto-refinamiento como mejora incremental.

## 2. Contexto histórico (por qué se rehace)

- El sistema original funcionó 3 meses en producción con ~80% de acierto inicial, subiendo
  con el auto-refinamiento (más ángulos por persona → mejor matching).
- Se retiró por exigencia de ~100% desde el día 1, incluyendo correspondencia frontal↔perfil
  entre cámaras distintas.
- Análisis: el 100% es inalcanzable en condiciones reales (ni los mejores modelos llegan).
  El objetivo realista es ≥95% frontal / ≥90% perfil con **enrolamiento multi-pose**.

## 3. Supuestos validados (2026-08-17)

1. **Precisión objetivo**: ≥95% TAR frontal↔frontal, ≥90% TAR frontal↔perfil (personas
   enroladas con todas las poses), FAR <1% a umbral operativo. El 100% queda descartado.
2. **CPU-only** (servidor actual, sin GPU). Condiciona modelo y batch.
3. **Python**: el servidor actual (Ubuntu 22.04) ya tiene **Python 3.10** de sistema; NO
   hay python3.7. No se migra versión: se usa **venv aislado** para no interferir con otros
   proyectos activos (uvicorn, autotube, supervisord) que corren sobre `python3.10` del sistema.
4. **Re-enrolado desde cero**: la BD está prácticamente vacía y `face_enc` histórico no existe
   en este entorno → no hay migración de datos de identidad.
5. **Panel**: refactor completo en **PHP puro + PDO** (no framework). PHP real del servidor: **8.4**.
6. **Live-view** (ipcamlive.com) fuera de alcance salvo petición explícita.

## 4. Requisitos funcionales (FR)

### Motor de clasificación (núcleo)
| ID | Requisito |
|---|---|
| FR-C1 | Detectar caras frontal y perfil en vídeo RTSP con detector robusto (RetinaFace). |
| FR-C2 | Embeddings de identidad robustos a pose/iluminación (ArcFace 512-d, ONNX, CPU). |
| FR-C3 | Enrolar en el alta con encodings de **múltiples poses** (default: frente + 90° izq + 90° der; completo: + 45° + arriba/abajo). |
| FR-C4 | Clasificar por **mejor coincidencia** (similitud coseno) contra todas las poses de cada persona. |
| FR-C5 | Mantener **auto-refinamiento** (acumular ángulos con el tiempo) como mejora, no prerrequisito. |
| FR-C6 | Manejar **2+ personas juntas** en el mismo evento (agrupación intra-batería). |
| FR-C7 | Control de calidad: descartar blur/oclusión/pose inválida en vigilancia y enrolamiento. |
| FR-C8 | Diccionario persistente seguro y concurrente (formato versionado + lock atómico). |

### Cruces de línea
| ID | Requisito |
|---|---|
| FR-L1 | Detectar cruce de línea + dirección (existe; mantener). |
| FR-L2 | Reducir falsos positivos (luz, contornos pequeños) y duplicados (cruces cercanos = 1). |
| FR-L3 | Guardar foto del cruce asociada a `cruces_lineas`. |

### Rutas
| ID | Requisito |
|---|---|
| FR-R1 | Trazar ruta persona entre cámaras (estancias encadenadas entrada→salida). |
| FR-R2 | Dibujar ruta sobre plano con nodos intermedios (no líneas rectas entre cámaras). |
| FR-R3 | Calcular tiempo total y cámaras visitadas. |

### Panel / Gestión (refactor)
| ID | Requisito |
|---|---|
| FR-P1 | CRUD locales, cámaras, líneas, personas. |
| FR-P2 | Unir personas y mover fotos entre personas. |
| FR-P3 | Control de aforo por cámaras entrada/salida. |
| FR-P4 | Fichajes de trabajadores y notificaciones de acceso. |

## 5. Requisitos no funcionales (NFR)

| ID | Requisito |
|---|---|
| NFR-ACC | TAR ≥95% frontal↔frontal; ≥90% frontal↔perfil (enrolados); FAR <1%. Medible con set etiquetado (motor/eval). |
| NFR-PERF | Procesado en CPU sin desbordar RAM; batch pequeño (2–8 caras); encodear en lote. |
| NFR-SEG | Sin SQLi (PDO prepared), sin credenciales en claro (.env), sin `chmod 777` en la app, password_hash + rate-limit, CSRF en mutaciones. |
| NFR-MANT | Eliminar ~40 scripts legacy; 1 script por responsabilidad; logging rotativo; typing en Python. |
| NFR-DISP | Reinicio automático de procesos (systemd Restart=always en Fase 5); face_enc_v2 no se corrompe ante cierre abrupto. |

## 6. Restricciones

| ID | Restricción |
|---|---|
| R1 | CPU-only (sin GPU). |
| R2 | Panel PHP **8.4** (real) + PDO. MySQL/MariaDB existente. |
| R3 | Formato `face_enc` cambia (128-d dlib → 512-d ArcFace): requiere re-enrolado, sin compatibilidad hacia atrás. |
| R4 | Esquema MySQL actual sin FKs; cambios de esquema mínimos. |
| R5 | Procesos en `screen` actualmente; migrar a `systemd` en Fase 5. |
| R6 | **Aislamiento Python**: NUNCA tocar `python3.10` del sistema ni `update-alternatives`; todo el motor en venv dedicado (`motor/venv`). |

## 7. Comandos de referencia (se fijan en Fase 0)

```
Entorno:  python3 -m venv motor/venv && motor/venv/bin/pip install -r motor/requirements.txt
Test:     motor/venv/bin/python -m pytest motor/tests -q
Eval:     motor/venv/bin/python -m motor.eval.eval
Lint PHP: php -l <archivo>
```

## 8. Criterios de éxito globales

1. NFR-ACC medible y cumplido sobre el set de evaluación.
2. Sin SQLi verificable; login funcional (admin + locales).
3. Zero scripts legacy en ejecución; procesos bajo systemd.
4. Enrolamiento multi-pose operativo desde el panel.
5. Documentación al día (specs + README sin secretos).
