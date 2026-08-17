# Reconocimiento Facial — Control de Accesos

Sistema de reconocimiento facial en tiempo real para interiores con múltiples cámaras RTSP:
detección y clasificación automática de personas, trazado de rutas entre cámaras, detección
de cruces de línea virtuales, control de aforo y fichajes.

> ⚠️ **Documentación en reconstrucción.** Este README sustituye al `readme.txt` histórico
> (que contiene credenciales y NO debe usarse como referencia de seguridad).

## Arquitectura

- **Panel web**: PHP 8.4 + PDO (refactor en curso, ver `docs/specs/05-spec-panel.md`).
- **Motor de visión**: Python 3.10 en **venv aislado** (`motor/venv`, ver `R6` en
  `docs/specs/01-requisitos.md`) — ArcFace/RetinaFace (Fase 1).
- **BD**: MySQL/MariaDB (esquema `reconocimientofacial-20260817.sql`).
- **Procesos**: 5 daemons (`capturador`, `detector`, `clasificador`, `procesa_video_registro`,
  `procesos_panel_control`) gestionados por `screen` hoy, migrando a `systemd` (Fase 5).

## Documentación

| Documento | Contenido |
|---|---|
| `docs/specs/01-requisitos.md` | Requisitos funcionales/no funcionales y restricciones |
| `docs/specs/02-spec-motor-clasificacion.md` | Diseño del motor ArcFace + enrolamiento multi-pose |
| `docs/specs/03-spec-cruces-linea.md` | Cruces de línea |
| `docs/specs/04-spec-rutas.md` | Rutas entre cámaras |
| `docs/specs/05-spec-panel.md` | Refactor del panel (PDO/seguridad) |
| `docs/specs/06-plan-bugs-mejoras.md` | Backlog de bugs y mejoras |
| `docs/specs/07-roadmap-implementacion.md` | Plan por fases |

## Puesta en marcha del motor (venv aislado)

```bash
python3 -m venv motor/venv
motor/venv/bin/pip install -r motor/requirements.txt   # se crea en Fase 0
```

> Regla crítica: **nunca** tocar `python3.10` del sistema ni `update-alternatives`;
> otros proyectos activos del servidor dependen de él.

## Estado del proyecto

- **Fase 0** (fundación) en curso.
- Roadmap completo: `docs/specs/07-roadmap-implementacion.md`.

## Seguridad

- Las credenciales deben ir en `.env` (fuera de git). El `readme.txt` histórico contiene
  secretos y está pendiente de purga (Fase 5).
