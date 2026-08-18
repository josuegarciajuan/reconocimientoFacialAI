# Spec 09 — Vínculos automáticos vídeos ↔ personas ↔ cruces de línea

> Estado: implementado (2026-08-19). Fase: panel + daemon (p7).

## 1. Problema

Las secciones **Pueblos** (`personas`), **Movimientos** (vídeos de movimiento y
estancias) y **Líneas** (`cruces_lineas`) vivían aisladas en BD:

- Un vídeo de movimiento no sabía de qué persona(s) era, ni viceversa (solo un
  enlace temporal calculado en vivo en `admin/pages/accesos/list.php`).
- Un cruce de línea no sabía a qué vídeo ni a qué persona pertenecía.
- No había navegación bidireccional entre las tres secciones.

Además se pedía **no re-estudiar los vídeos** (extraer caras / comparar embeddings)
para vincular: el trabajo de clasificación ya lo hace el pipeline una única vez.

## 2. Solución

### 2.1 Esquema (migración `sql/2026-08-19-vinculos-videos-cruces.sql`)

FKs **nullable** (no siempre es posible el vínculo mutuo):

| Tabla | Columna | Descripción |
|---|---|---|
| `estancias` | `video_id` | vídeo de movimiento del que derivan sus fotos |
| `cruces_lineas` | `video_id` | vídeo donde se detectó el cruce |
| `cruces_lineas` | `persona_id` | persona atribuida al cruce (vía estancia del mismo vídeo) |

### 2.2 Por qué no hace falta re-extraer caras

Los tres artefactos comparten **cámara + timestamp base** porque derivan del mismo
fichero de movimiento:

- `videos.fecha_ini/fecha_fin` ← nombre `{cam}_{fecha}_{hora}.{micro}.mp4` (`archiva_video.py`).
- `estancias.fecha_ini/fecha_fin` ← fotos `<fichero>_<segs>.jpg` (`clasificadorV2.php`).
- `cruces_lineas.fecha` ← `procesa_video.py` (mismo vídeo).

El vínculo es, por tanto, **solape de intervalos por cámara** con margen
(`CONFIG_VINCULO_MARGEN_SEGS`, def. 30 s) — barato y sin tocar el MP4.

### 2.3 Lógica (`libs/vinculos.php`)

- `vinculos_solapa()` / `vinculos_mas_cercano()`: funciones puras (testeables sin BD).
- `vinculos_vincular_estancia($estancia, $margen)`: busca vídeo por cámara + solape → `estancias.video_id`.
- `vinculos_vincular_video($video, $margen)`: enlaza sus estancias, sus cruces y la
  persona de cada cruce (estancia del mismo vídeo que cubre la fecha del cruce).
- `vinculos_vincular_cruce($cruce, $margen)`: para cruces huérfanos (vídeo y persona).
- `vinculos_videos_sin_estancia()`: candidatos a re-estudio (movimiento sin cara
  reconocible) — solo informativo; el re-análisis del MP4 es opcional.

### 2.4 Daemon `vinculador.php` (p7, `rf-vinculador`)

Cada `CONFIG_VINCULADOR_LOOP` (def. 60 s):

- **Backfill** (1ª vez por local): todos los vídeos, estancias y cruces históricos.
- **Incremental**: estancias/cruces huérfanos de los últimos 30 días + vídeos de las
  últimas 24 h (idempotente, solo rellena NULL).
- **Log** de candidatos a re-estudio.

El hook en `clasificadorV2.php` enlaza la estancia al instante al crearla; el daemon
es la red de seguridad y el backfill.

## 3. UI (navegación bidireccional)

- **Persona** (`admin/pages/visitantes/edit.php`): pestañas **Ver Vídeos (n)** (grid de
  miniaturas con reproducción en modal) y **Ver Cruces (n)** (listado filtrado); enlaces
  en `list.php` (Vídeos / Cruces).
- **Movimientos** (`admin/pages/accesos/list.php`): el modal de vídeo muestra
  "👤 Ver persona" enlazado.
- **Líneas** (`admin/pages/lineas/list.php`): columnas **PERSONA** (enlace a la ficha)
  y **VÍDEO** (miniatura + modal) por cruce, con filtro de persona.
- Modal `rfVideoModal(id, url, poster, titulo, personaId, personaNombre)` en
  `admin/files/ui-common.js`.

## 4. Configuración

| Constante | Env | Def. |
|---|---|---|
| `CONFIG_VINCULADOR_LOOP` | `RF_VINCULADOR_LOOP` | 60 s |
| `CONFIG_VINCULADOR_BACKFILL_DIAS` | `RF_VINCULADOR_BACKFILL_DIAS` | 30 |
| `CONFIG_VINCULO_MARGEN_SEGS` | `RF_VINCULO_MARGEN_SEGS` | 30 |

## 5. Pruebas

`php tests/vinculos_test.php` (18 comprobaciones de lógica pura: solape, margen,
sin solape, atribución persona). Despliegue: añadir `rf-vinculador` a
`deploy/install_services.sh`.

## 6. Pendiente (opcional)

Re-estudio automático de vídeos sin estancia (hoy solo se loguean): re-lanzar
`motor/procesa_video.py` sobre el MP4 archivado cuando no haya ninguna cara/estancia.
