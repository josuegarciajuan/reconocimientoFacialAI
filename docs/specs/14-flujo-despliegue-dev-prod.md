# 14 · Flujo de despliegue: dev (worktrees) → GitHub `main` → producción (auto-deploy)

## Contexto

El sistema de reconocimiento facial se despliega en **dos servidores**:

| Rol | Servidor | Ruta | Rol del repo |
|---|---|---|---|
| **Desarrollo** | `liveyourdre2` (`92.113.151.136`) | `/root/reconocimientoFacial` | Worktrees de GitHub + opencode. El motor NO corre aquí. |
| **Producción** | `<HOST_PRODUCCION>` (`RF_PROD_HOST`) | `/root/reconocimientoFacial` | `git clone` de GitHub `main` (se actualiza con `git pull`). Motor en marcha. |

- **Datos de producción** (vídeos, caras, modelos, `face_enc_v2`, BD, `.env`, `.insightface`)
  **solo viven en el servidor de producción** y NO están en git (`.gitignore`).
- El host y las credenciales de producción **no se versionan**: se definen en el `.env`
  local (ver «Configuración»). La spec usa siempre `<HOST_PRODUCCION>`.

## Acceso a producción

- **Panel web**: `http://<HOST_PRODUCCION>:8090/reconocimientoFacial/admin`
- **SSH**: gestionado por `deploy/deploy_prod.sh` a partir de `.env`:
  ```bash
  RF_PROD_HOST=<HOST_PRODUCCION>
  RF_PROD_SSH_USER=root
  RF_PROD_SSH_PASS=<secreto>      # nunca se versiona
  RF_PROD_SSH_PORT=22             # opcional
  RF_PROD_PATH=/root/reconocimientoFacial   # opcional
  ```

> ⚠️ **IMPORTANTE (lección 2026-09-01)**: los datos reales del sistema viven en
> **producción (`<HOST_PRODUCCION>`), NO en dev**. Hacer operaciones sobre datos
> (reset, purgas, borrados) en la máquina de desarrollo **no afecta a producción** y
> puede confundir (los procesos que se ven en `ps` en dev no son los de producción).
> **Antes de tocar datos, confirmar siempre en qué host se está** (`hostname`):
> dev = `liveyourdre2`, prod = `mail` (hostname configurado en `<HOST_PRODUCCION>`).

## Regla de oro

> **git = código, no datos.** Cada CAMBIO se trabaja en una copia aislada
> (`git worktree`), se integra en `main` y se publica con `push`; después el cambio
> **se despliega automáticamente a producción** con `deploy/deploy_prod.sh`.

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
4. **Desplegar a producción** (obligatorio, ver `AGENTS.md`):
   ```bash
   bash deploy/deploy_prod.sh
   ```
   El script, por SSH:
   - `git fetch` + `git pull --ff-only origin main` en `/root/reconocimientoFacial`;
   - gate de sintaxis (`php -l` / `py_compile`) sobre los ficheros cambiados;
   - reinstala units systemd (`deploy/systemd/`), vhost Apache (`deploy/apache/`) o
     dependencias Python (`motor/requirements.txt`) **solo si cambiaron**;
   - reinicia **solo los servicios afectados** por el diff (o todos con `--all`);
   - comprueba que los servicios queden `active` y reporta.

   Opciones: `--all`, `--no-restart`, `--dry-run`, `--host`, `--path`.

### Mapa diff → servicios

| Rutas cambiadas | Servicio(s) reiniciado(s) |
|---|---|
| `capturador.php`, `motor/guarda_movimientosV3.py` | `rf-capturador` |
| `detector.php`, `motor/procesa_video.py`, `motor/archiva_video.py`, `motor/cruces.py`, `motor/clasificador.py` | `rf-detector` |
| `clasificadorV2.php` | `rf-clasificador` |
| `conciliador.php`, `libs/conciliador.php` | `rf-conciliador` |
| `vinculador.php`, `libs/vinculos.php` | `rf-vinculador` |
| `alarmador.php`, `libs/alarmas.php` | `rf-alarmador` |
| `procesos_panel_control.php`, `motor/pose.py` | `rf-panel-control` |
| `live/**` | `rf-live` |
| `motor/photo_worker.py` | `rf-photo` |
| `motor/calibrar.py`, `motor/vigilar_deriva.py` | rearma `rf-calibra.timer` / `rf-vigilar-deriva.timer` |
| `motor/core/**`, `libs/db.php`, `config/config.php`, `deploy/systemd/**`, `deploy/apache/**`, `motor/requirements.txt` | **todos** los daemons |
| `admin/**`, `includes/**`, `docs/**`, `tests/**` | ninguno (solo `git pull`) |

## Instalación / reactivación de producción

`deploy/install_services.sh` instala y arranca los servicios; `deploy/install_apache.sh`
instala el vhost del panel (`:8090`, detecta el socket php-fpm) y el symlink de
`/var/www/html/reconocimientoFacial`. El `install_services.sh` crea además los directorios
de runtime (`libs/threads_files_aux/`) y ajusta los permisos de `.env`
(`root:www-data`, `640`) para que php-fpm pueda leerlo.

## Notas

- **`.env` por entorno**: dev y prod tienen su propio `.env` (no versionado). No arrastres
  variables de un entorno a otro con el `pull`.
- **No reinventar el remoto**: el repo usa `origin` =
  `https://github.com/josuegarciajuan/reconocimientoFacialAI.git` (público).
- **Rollback**: si algo falla en producción tras el pull, revisar el cambio con
  `git log`/`git diff`; para datos, restaurar desde el backup previo. Nunca
  `git reset --hard` ni `git clean -fd` (machacan datos/estado).

## Reset del sistema (empezar a capturar caras desde cero)

> ⚠️ **EJECUTAR SIEMPRE EN PRODUCCIÓN (`<HOST_PRODUCCION>`), nunca en dev.**

El script `deploy/reset_datos.sh` (versionado en el repo) vuelve a cero los datos de
identidad y movimiento y rearranca los servicios, conservando la configuración (cámaras,
líneas, plano, local, auto-login):

```bash
# 1. Desplegar el script (si no está) y ejecutarlo en PRODUCCIÓN:
cd /root/reconocimientoFacial
git pull origin main
bash deploy/reset_datos.sh              # detiene servicios → mata procesos → vacía BD → borra motor → rearranca
bash deploy/reset_datos.sh --dry-run    # modo ensayo: solo muestra el plan
```

Qué borra:
- BD: `personas`, `estancias`, `fotos`, `videos`, `cruces_lineas`, `fichajes`,
  `alarmas`, `calibraciones` (+ `foto_audits`/`foto_audit_events` si existen).
- Galería y media del motor: `face_enc_v2`, `caras/`, `videos/`,
  `videos_archivo/`, `feedback/`, `revision/`, `dedup/`, `audit_queue/`, etc.

Qué conserva: `camaras`, `locales`, `lineas`, `lineas_plano`, `nodos`,
`senderos`, `dispositivos_autologin`, `alarmas_telefonos`.

Verificación tras el reset:
```bash
mysql -u<user> -p<pass> reconocimientofacial -e \
  "SELECT COUNT(*) FROM personas; SELECT COUNT(*) FROM videos;"
systemctl is-active rf-capturador rf-detector rf-clasificador
ps -eo pid,args | grep '[c]lasificador.py'   # debe salir SOLO el daemon fresco
```
