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

## Acceso a producción

- **Panel web**: `http://194.233.67.64:8090/reconocimientoFacial/admin`
- **SSH**:
  ```bash
  sshpass -p '<password>' ssh root@194.233.67.64
  # o si no hay sshpass instalado:
  ssh root@194.233.67.64
  ```
  La contraseña actual está en el `.env` de **dev** como `RF_PROD_PASS`
  (`/root/reconocimientoFacial/.env`) y en el secret manager del equipo.
  **No versionar nunca contraseñas** (bloqueado por el hook pre-commit).

> ⚠️ **IMPORTANTE (lección 2026-09-01)**: los datos reales del sistema viven en
> **producción (`194.233.67.64`), NO en dev**. Hacer operaciones sobre datos
> (reset, purgas, borrados) en la máquina de desarrollo **no afecta a
> producción** y puede confundir (los procesos que se ven en `ps` en dev no son
> los de producción). **Antes de tocar datos, confirmar siempre en qué host
> se está** (`hostname`): dev = `liveyourdre2`, prod = `mail`.

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

## Reset del sistema (empezar a capturar caras desde cero)

> ⚠️ **EJECUTAR SIEMPRE EN PRODUCCIÓN (`194.233.67.64`), nunca en dev.**

El script `deploy/reset_datos.sh` (versionado en el repo) vuelve a cero los
datos de identidad y movimiento y rearranca los servicios, conservando la
configuración (cámaras, líneas, plano, local, auto-login):

```bash
# 1. Desplegar el script (si no está) y ejecutarlo en PRODUCCIÓN:
cd /root/reconocimientoFacial
git pull origin main
bash deploy/reset_datos.sh          # detiene servicios → mata procesos → vacía BD → borra motor → rearranca
bash deploy/reset_datos.sh --dry-run  # modo ensayo: solo muestra el plan
```

Qué borra:
- BD: `personas`, `estancias`, `fotos`, `videos`, `cruces_lineas`, `fichajes`,
  `alarmas`, `calibraciones` (+ `foto_audits`/`foto_audit_events` si existen).
- Galería y media del motor: `face_enc_v2`, `caras/`, `videos/`,
  `videos_archivo/`, `feedback/`, `revision/`, etc.

Qué conserva: `camaras`, `locales`, `lineas`, `lineas_plano`, `nodos`,
`senderos`, `dispositivos_autologin`, `alarmas_telefonos`.

Verificación tras el reset:
```bash
mysql -u<user> -p<pass> reconocimientofacial -e \
  "SELECT COUNT(*) FROM personas; SELECT COUNT(*) FROM videos;"
systemctl is-active rf-capturador rf-detector rf-clasificador
ps -eo pid,args | grep '[c]lasificador.py'   # debe salir SOLO el daemon fresco
```
