# Reconocimiento Facial — Control de Accesos

Sistema de reconocimiento facial en tiempo real para interiores con múltiples cámaras RTSP:
detección y clasificación automática de personas, trazado de rutas entre cámaras, detección
de cruces de línea virtuales, control de aforo y fichajes.

## Arquitectura

- **Panel web**: PHP 8.4 + **PDO** (`libs/db.php`) — refactor completo (sin SQLi, login con
  `password_hash` + rate-limit + CSRF).
- **Motor de visión**: Python 3.10 en **venv aislado** (`motor/venv`) — **ArcFace/RetinaFace**
  (insightface `buffalo_l`) para embeddings, matching por similitud coseno multi-pose,
  diccionario `face_enc_v2` atómico (`motor/core/`).
- **BD**: MySQL/MariaDB (esquema `reconocimientofacial-20260817.sql`).
- **Daemons**: 6 servicios `systemd` (`deploy/systemd/`) — capturador, detector, clasificador,
  panel-control, conciliador de fichajes y vinculador de vídeos/personas/cruces.
  Logs vía `journalctl` (rotación del sistema).

## Procesos (daemons)

| Servicio | Script | Rol |
|---|---|---|
| rf-capturador (p4) | `capturador.php` → `motor/guarda_movimientosV3.py` | Detecta movimiento, graba MP4 H.264 directo (con 2 s de pre-roll y post-roll) en `motor/videos/<local>/<cam>/` |
| rf-detector (p5) | `detector.php` → `motor/procesa_video.py` + `motor/archiva_video.py` | Cruces de línea (MOG2+tracking) + extracción de caras + archivado a `motor/videos_archivo/` (miniatura incluida) + purga por retención |
| rf-clasificador (p3) | `clasificadorV2.php` | Ingesta a BD (personas/estancias/fotos) desde `motor/caras/`; enlaza cada estancia con su vídeo de movimiento |
| rf-panel-control (p1) | `procesos_panel_control.php` → `motor/pose.py` | Validador de pose para el registro webcam multi-pose |
| rf-conciliador (p6) | `conciliador.php` → `libs/conciliador.php` | Concilia fichajes según el horario del local: provisional en vivo, conciliado (salida definitiva) al cerrar el día |
| rf-vinculador (p7) | `vinculador.php` → `libs/vinculos.php` | Enlaza vídeos ↔ estancias (personas) ↔ cruces por cámara + solape temporal (backfill + incremental) |

Scripts actuales del motor: `core/` (model, matching, store, quality, config, superres), `clasificador.py`,
`procesa_video.py`, `enrolamiento.py`, `pose.py`, `cambiar_foto.py`, `cruces.py`,
`guarda_movimientosV3.py`, `juntar_personas.py`, `dofoto.py`, `eval_cruces.py`, `eval/`,
`reprocesar.py` (backfill de resolución: fotos existentes + re-escaneo de vídeos archivados + re-embedding de galería).

## Instalación

```bash
# 1. Entorno Python aislado (nunca tocar el python del sistema)
python3 -m venv motor/venv
motor/venv/bin/pip install -r motor/requirements.txt

# 2. Credenciales
cp .env.example .env   # y ajusta RF_DB_* / RF_URL / RF_RUTA

# 3. BD (esquema vacío)
mysql -uroot -e "CREATE DATABASE IF NOT EXISTS reconocimientofacial CHARACTER SET latin1"
mysql -uroot reconocimientofacial < reconocimientofacial-20260817.sql

# 4. Servicios systemd
sudo bash deploy/install_services.sh start
```

## Pruebas

```bash
motor/venv/bin/python -m pytest motor/tests -q        # tests del motor (29)
motor/venv/bin/python -m motor.eval.eval              # métricas TAR/FAR (set en motor/eval/data/)
php tests/fichajes_conciliador_test.php               # lógica de conciliación de fichajes (13)
php tests/vinculos_test.php                           # lógica de vínculos vídeos↔estancias↔cruces (18)
```

## Documentación

| Documento | Contenido |
|---|---|
| `docs/specs/01-requisitos.md` | Requisitos funcionales/no funcionales y restricciones |
| `docs/specs/02-spec-motor-clasificacion.md` | Motor ArcFace + enrolamiento multi-pose |
| `docs/specs/03-spec-cruces-linea.md` | Cruces de línea |
| `docs/specs/04-spec-rutas.md` | Rutas entre cámaras |
| `docs/specs/05-spec-panel.md` | Refactor del panel (PDO/seguridad) |
| `docs/specs/06-plan-bugs-mejoras.md` | Backlog de bugs y mejoras |
| `docs/specs/07-roadmap-implementacion.md` | Plan por fases |
| `docs/specs/08-fichajes-horarios.md` | Fichajes con horario habitual y conciliador |
| `docs/specs/09-vinculos.md` | Vínculos automáticos vídeos ↔ personas ↔ cruces de línea |
| `docs/specs/10-lore-tooltips.md` | Bocadillos de lore: explicación de la terminología temática (glosario + motor) |
| `docs/specs/11-anillo-hub.md` | El Ojo del Anillo: hub maestro flotante (búsqueda + accesos rápidos + centinelas + semáforo) |
| `docs/specs/12-refinar-autoaprendizaje.md` | Refinamiento del autoaprendizaje: galerías limpias, admisión por cara, feedback activo y limpieza de perfiles mezclados |
| `docs/specs/13-calibracion-templar.md` | Calibrador guiado (Templar): rituales A-F, valores de fábrica/journal, vigilancia diaria de deriva y herramientas CLI |
| `docs/specs/14-flujo-despliegue-dev-prod.md` | Flujo de despliegue: dev (worktrees) → GitHub `main` → producción (`git pull`) |

## Seguridad

- Credenciales en `.env` (fuera de git). El histórico `readme.txt` (con credenciales de
  servidores antiguos) fue **eliminado** — rotar cualquier credencial que hubiera compartido.
- SQLi eliminado (PDO en toda la app); login con `password_hash`/`password_verify` + rate-limit.
