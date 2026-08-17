# Spec 06 — Plan de bugs y mejoras (backlog consolidado)

> Estado: aprobado (Fase 0). Los bugs se corrigen en las fases indicadas.

## 1. Bugs — Motor Python

| # | Bug | Archivo | Sev | Fase | Estado |
|---|---|---|---|---|---|
| B1 | `distancias_similares`/`distacia_superior` usan `abs(y3-y3)=0` → pruebas de pose no-op | `motor/devuelve_posicion_cara.py` | Alta | 1 | ✅ `motor/pose.py` (usa face.pose) |
| B2 | `LandmarksType._2D` deprecado (crash con libs nuevas) | `motor/devuelve_posicion_cara.py` | Alta | 1 | ✅ `motor/pose.py` |
| B3 | `desapilar()` captura `AttributeError` en vez de `IndexError`; `vaciar()` rompe deque | `motor/fifo.py` | Media | 1 | ✅ reescrito + tests |
| B4 | Falta `import FileLock` + escribe `knownNames` en campo `points` (corrompe diccionario) | `motor/cambiar_foto_de_persona.py` | Alta | 4 | ✅ `motor/cambiar_foto.py` (re-encodea + face_enc_v2) |
| B5 | Guarda frame completo (crop deshabilitado) + `blobFromImage` sin resize/mean | `motor/procesa_video_registro_1.py` | Media | 1 | ✅ `motor/enrolamiento.py` |
| B6 | Indentación mixta → `TabError` (legacy) | `motor/cruza_lineas.py` | Baja | 5 (eliminar) | ✅ eliminado |
| B7 | Lógica enfocado/desenfocado invertida (legacy) | `motor/desenfocadas.py` | Baja | 5 (eliminar) | ✅ eliminado |
| B8 | `fotos_identificadorunico` → `NameError` si no hay matches | `motor/procesa_video_registro_2.py` | Media | 1 | ✅ `motor/enrolamiento.py` |

## 2. Bugs — Panel / PHP

| # | Bug | Archivo | Sev | Fase |
|---|---|---|---|---|
| B9 | SQL injection global (sin escape ni prepared statements) | `libs/mysql.class.php` + todos | Crítica | 4 | ✅ migrado a PDO (libs/db.php) en toda la app; quedan como código legacy `mysql.class.php` y `reconocimientoFacial.class.php` (Fase 5) |
| B10 | Login no-admin fatal (`$sql` sin instanciar); password claro + `md5` roto | `admin/login.php`, `locales/acciones.php` | Crítica | 4 | ✅ password_hash/verify + rate-limit (queda re-hashear passwords existentes) |
| B11 | Marcar-notificaciones usa `local_id` en vez de `id` | `admin/accionesAjax.php` | Alta | 4 | ✅ + esquema actual (estancias/personas) |
| B12 | Dashboard división por cero + `lafecha` indefinido | `dashboard/list.php` | Media | 4 | ✅ queries PDO + fix |
| B13 | Fecha 12h→24h rota (`$rango = $v_fecha[0]`) en todos los listados | lineas/rutas/visitantes/fichajes/accesos | Alta | 4 | ✅ todos migrados a `libs/fechas.php` |
| B14 | Filtro cámara usa alias `c.id` inexistente | `visitantes/list.php` | Alta | 4 | ✅ `a.camara_id` + PDO |
| B15 | `camara_id in()` vacío sin cámaras puerta/salida | `rutas/list.php` | Alta | 3 | ✅ SQL defensivo |
| B16 | Índices de líneas desalineados al guardar | `config/javascript.php` | Media | 4 | ✅ `editar_linea1` localiza por `id_lineas.indexOf` |
| B17 | Asignaciones a `$aux` en vez de `$data[$i]`; "Descargar" sin handler | `fichajes/*` | Media | 4 | ✅ agregación reescrita en PDO |
| B18 | `subir_video2` no dispara el procesamiento | `visitantes/acciones.php` | Media | 4 | ✅ dispara `enrolamiento.py` + inserta persona |
| B19 | `?descargar=` roto (`$tmp` sin instanciar) | `admin/index.php` | Baja | 4 | ✅ descarga segura de foto por estancia |
| B20 | `exit;` hardcodeado (depuración) | `capturador.php` | Alta | 4 | ✅ eliminado |
| B21 | Hostname no mapeado → constantes sin definir | `config/rutas.php` | Alta | 0 | ✅ Fase 0 |
| B22 | PHP 8.4 eliminó constructores estilo PHP4 → `new Conectar()` no conectaba | `libs/mysql.class.php` | Crítica | 3 | ✅ `__construct` delegando |

## 3. Mejoras (backlog priorizado)

| # | Mejora | Fase | Estado |
|---|---|---|---|
| M1 | Embedding ArcFace + re-enrolado (face_enc_v2) | 1 | ✅ core + clasificador.py |
| M2 | Similitud coseno + normalización L2 + plantilla multi-pose | 1 | ✅ core/matching.py |
| M3 | Enrolamiento multi-pose (default 3, completo 7) | 1 | ✅ enrolamiento.py + pose.py |
| M4 | Seguridad PHP (PDO, CSRF, password_hash, rate-limit) | 4 | ✅ PDO global + login (CSRF/rate-limit); CSRF en el resto de mutaciones pendiente |
| M5 | Refactor completo panel (routing, templates, bugs UI) | 4 | ✅ módulos a PDO + bugs B9-B20 cerrados |
| M6 | Limpiar ~40 scripts legacy + `__pycache__`, `*.out`, backups | 5 | ✅ 101 ficheros eliminados (scripts legacy, modelos, R&D, mysql.class.php, readme.txt) |
| M7 | Migrar `screen` → `systemd` (Restart=always) | 5 | ✅ `deploy/systemd/` + `deploy/install_services.sh` |
| M8 | Logs rotativos (RotatingFileHandler) | 1 | ✅ vía journald (systemd) — los .py imprimen a stdout |
| M9 | Harness de evaluación TAR/FAR (motor/eval) | 0–1 | ✅ harness; pendiente datos |
| M10 | Secretos a `.env` (fuera de git) + rotar credenciales expuestas | 0–5 | ✅ `.env` + `.env.example`; `readme.txt` (credenciales) eliminado |
| M11 | Aislamiento Python: venv dedicado, RUTA_PYTHON al venv | 0 | ✅ Fase 0 |
| M12 | `ftp-upload` no está instalado en este servidor → reemplazar por pysftp/paramiko | 2 | ✅ `guarda_movimientosV3.py` usa paramiko SFTP |

## 4. Seguimiento

Cada bug/mejora se marca `[x]` en su fichero de fase al completarse, con la verificación
que la cerró. Los nuevos hallazgos se añaden aquí con ID correlativo.
