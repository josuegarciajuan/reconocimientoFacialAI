# Reconocimiento Facial — reglas del proyecto (dev + producción)

## Entornos

- **Dev**: este servidor (`liveyourdre2`, `92.113.151.136`). Aquí se edita, se prueba y se
  integra. El motor **no** se ejecuta aquí.
- **Prod**: servidor remoto. Host, usuario, puerto y clave se definen **solo** en `.env`
  (`RF_PROD_HOST`, `RF_PROD_SSH_USER`, `RF_PROD_SSH_PASS`, `RF_PROD_SSH_PORT`,
  `RF_PROD_PATH`). **Nunca** se versionan ni se escriben en las specs.
- Los **datos reales** (BD, `face_enc_v2`, `caras/`, `videos/`, modelos, `.env`) viven
  **solo en producción** y no están en git (`.gitignore`). git = código, no datos.

## Protocolo git (global)

Cada cambio se trabaja en una copia aislada (`git worktree`, rama `work/<id>`), se integra
en `main` y se publica con `push` (ver comando `/git-workflow`). Nunca commitear `.env`,
secretos, `data/`, `*.pickle`, `*.bak`, etc.

## Regla obligatoria: desplegar cada cambio a producción

Al cerrar cualquier cambio (tras el merge en `main` y el `git push`), **ejecutar siempre
desde el árbol principal**:

```bash
bash deploy/deploy_prod.sh
```

No dar un cambio por terminado sin desplegarlo, salvo que el usuario indique lo contrario.
`deploy_prod.sh`:

1. hace `git pull --ff-only origin main` en producción;
2. aplica un gate de sintaxis (`php -l` / `py_compile`) sobre lo cambiado;
3. reinstala units systemd, vhost Apache o dependencias Python si esos ficheros cambiaron;
4. reinicia **solo los servicios afectados** por el diff (o todos con `--all`);
5. verifica que los servicios reiniciados queden `active` y reporta.

Opciones: `--all`, `--no-restart`, `--dry-run`. Si el deploy falla, hay que reportarlo y
**no** continuar como si hubiera ido bien (nunca `--no-verify` ni forzar estados).

## Datos y operaciones destructivas

- Reset, purgas y borrados de datos: **solo en producción** (`bash deploy/reset_datos.sh`),
  nunca en dev. Confirmar el host (`hostname`) antes de tocar datos.
- Rollback: revisar `git log` / `git diff`; nunca `git reset --hard`, `git clean -fd`,
  `git checkout --` ni `git stash`.

## Cambios en web/servicios

- Vhost del panel: plantilla versionada en `deploy/apache/rf-panel.conf` + instalador
  `deploy/install_apache.sh` (detecta el socket php-fpm de cada máquina).
- El vhost escucha en `:8090` y sirve `/reconocimientoFacial/admin`.
- Tras tocar `deploy/apache/` o `deploy/systemd/`, el propio `deploy_prod.sh` los reinstala.

## Documentación

- Flujo completo: `docs/specs/14-flujo-despliegue-dev-prod.md`.
- Credenciales: solo en `.env` (gitignored). Cualquier valor que parezca un secreto
  (`password`, `token`, `api_key`, …) está bloqueado por el hook pre-commit.
