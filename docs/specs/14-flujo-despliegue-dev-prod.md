# 14 · Flujo de despliegue: dev (worktrees) → GitHub `main` → producción

## Contexto

El sistema de reconocimiento facial se despliega en **dos servidores**:

| Rol | Servidor | Ruta | Rol del repo |
|---|---|---|---|
| **Desarrollo** | `92.113.151.136` (`liveyourdre2`) | `/root/reconocimientoFacial` | Worktrees de GitHub + opencode |
| **Producción** | `194.233.67.64` | `/root/reconocimientoFacial` | `git clone` de GitHub `main` (se actualiza con `git pull`) |

- **Datos de producción** (vídeos, caras, modelos, `face_enc_v2`, BD, `.env`, `.insightface`)
  **solo viven en el servidor de producción** y NO están en git (`.gitignore`).
- En dev solo existe una copia para desarrollo/pruebas; el motor **no** corre en dev.

## Regla de oro

> **git = código, no datos.** Cada CAMBIO se trabaja en una copia aislada
> (`git worktree`), se integra en `main` y se publica con `push`; luego se
> aplica en producción con `git pull`.

## Flujo por cambio (dev → producción)

1. **En dev** (esta máquina), crear el worktree del cambio:
   ```bash
   git -C /root/reconocimientoFacial worktree add \
     /root/.opencode-worktrees/reconocimientoFacial/<fecha>-<slug> \
     -b work/<fecha>-<slug>
   ```
   (opencode lo hace por defecto a nivel de configuración de plataforma).
2. **Editar solo en el worktree.** Commits atómicos `tipo: descripción`
   (`feat|fix|refactor|docs|chore|test|style|sync`).
3. **Integrar y publicar**: merge de `work/<...>` en `main` y `push` a GitHub:
   ```bash
   git checkout main && git merge work/<slug>
   git push origin main
   ```
4. **En producción** (`194.233.67.64`), aplicar:
   ```bash
   cd /root/reconocimientoFacial
   git pull origin main
   # si el cambio toca servicios, reiniciar los afectados:
   # systemctl restart rf-capturador rf-detector ...   (según el caso)
   ```
   Los datos runtime y `.env` NO cambian con el pull (no están versionados);
   si un cambio necesita nueva variable de entorno, actualizarla manualmente
   en el `.env` de producción.

## Notas

- **`.env` por entorno**: dev y prod tienen su propio `.env` (no versionado).
  No arrastres variables de un entorno a otro con el `pull`.
- **No reinventar el remoto**: el repo usa `origin` =
  `https://github.com/josuegarciajuan/reconocimientoFacialAI.git` (público).
- **Rollback**: si algo falla en producción tras el pull, revisar el cambio
  con `git log`/`git diff`; para datos, restaurar desde el backup previo.
  Nunca `git reset --hard` ni `git clean -fd` (machacan datos/estado).
- **Migración histórica (2026-09-01)**: el servidor antiguo quedó como dev;
  el motor quedó detenido y deshabilitado allí. Ver `docs/adr/` si aplica.
