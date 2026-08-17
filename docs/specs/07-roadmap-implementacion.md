# Spec 07 — Roadmap de implementación

> Estado: aprobado (Fase 0). Cada fase se cierra con verificación y commit. Orden por dependencias y prioridad (Precisión → Seguridad → Limpieza).

## Fases

### Fase 0 — Fundación (setup + documentación) ← ACTUAL
| # | Tarea | Criterio de aceptación | Verificación |
|---|---|---|---|
| T0.1 | Specs en `docs/specs/` + `README.md` limpio | Docs completos, sin secretos | Revisión + commit |
| T0.2 | venv aislado + deps + modelos | `motor/venv/bin/python` importa insightface/onnxruntime y encoda una imagen | Smoke test |
| T0.3 | `rutas.php` (hostname + RUTA_PYTHON venv) + reemplazar `python3.7` hardcodeados + `.gitignore` | `php -l` OK; config carga constantes | php -l + php -r |
| T0.4 | Harness `motor/eval/` + set semilla | `python -m motor.eval.eval` imprime métricas | Ejecución |
| T0.5 | Verificación final y commit | Fase verificada | git log |

### Fase 1 — Motor de clasificación (precisión)
- T1.1 `motor/core/` (detector, embedder, matching, store, quality) + tests.
- T1.2 `clasificador.py` (reescritura de `procesa_fotos_def_borrosaparteV2.py`).
- T1.3 `enrolamiento.py` multi-pose + `pose.py` (corrige B1, B2, B5, B8).
- T1.4 Calibración de umbrales con `motor/eval` → cumplir NFR-ACC.
- T1.5 `fifo.py` fix (B3).
- Verificación: pytest + eval TAR/FAR + smoke de flujo de carpetas.

### Fase 2 — Cruces de línea ✅ (parcial)
- ✅ T2.1 `motor/cruces.py` extraído y corregido (P1–P4): MOG2 + tracking IoU + histéresis + dedup.
- ✅ T2.2 Calibración con vídeos grabados (`motor/eval_cruces.py`).
- ✅ T2.3 Reemplazo de `ftp-upload` por paramiko SFTP (M12).
- ⏳ Integración con `procesa_videosV6.py` (el orquestador aún usa el cruce legacy) — se cablea en Fase 4.
- Verificación: 6 tests unitarios; 1 cruce/paso en vídeo sintético; sin FP por flash de luz.

### Fase 3 — Rutas ✅
- ✅ T3.1 Cadena de estancias en PHP (`libs/rutas.php`) + JSON limpio (R1, R2).
- ✅ T3.2 Nodos precalculados + dibujado (R3, R4); fix B15.
- ✅ `libs/fechas.php` (B13 en rutas); B22 (constructor PHP4 en `mysql.class.php`).
- Verificación: test funcional 12/12 (cadena 1→2→4, nodos, sin error sin puerta).

### Fase 4 — Seguridad + refactor panel ✅
- ✅ T4.1 `libs/db.php` (PDO, prepared statements) — B9 migrado en toda la app.
- ✅ T4.2 Auth: `libs/auth.php` (password_hash/verify, rate-limit, CSRF, session) → B10.
- ✅ T4.3 `ws.php` seguro + `accionesAjax` (esquema actual) → B11; barrido B9 completo (index, notificaciones, seleccionCuenta, camaras, locales, visitantes, config) → B12/B13/B14/B16/B17/B19.
- ✅ T4.4 Integración del motor: `motor/procesa_video.py` (cruces.py + RetinaFace, sustituye a procesa_videosV6), `detector.php` cableado (clasificador.py + procesa_video.py), `capturador.php` B20, `enrolamiento.py` al panel (B18), `cambiar_foto.py` (B4).
- ⏳ Pendiente post-fase: calibración NFR-ACC con datos reales (enrolamiento/7 poses), CSRF en mutaciones restantes, re-hashear passwords existentes.

### Fase 5 — Limpieza y operativa
- T5.1 Eliminar legacy (~40 scripts) tras verificar referencias → B6, B7.
- T5.2 `systemd` services (5 procesos) → M7.
- T5.3 Secretos a `.env` + rotación → M10.
- T5.4 README final + docs al día.
- Verificación: arranque limpio sin legacy; `systemctl` gestiona procesos.

## Dependencias
- Fase 1 depende de 0 (venv, eval).
- Fase 4 depende de 0 (hostname/config) y puede solaparse con 1–3 (streams distintos).
- Fase 5 depende de 1–4 (solo se elimina legacy ya sustituido).

## Paralelizable
- Stream A (Fases 1–3, motor) y Stream B (Fase 4, panel) son independientes tras la Fase 0.
