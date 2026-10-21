# 20 — Instancia personal `ojos` (multi-instancia sobre el mismo código)

Estado: **implementado** (2026-10-21). `ojos` es una segunda ejecución del mismo
sistema, no un fork. Código compartido; BD, datos, PWA y SuperServer propios.

## Topología

| Instancia | Host | URL | BD | Datos |
|---|---|---|---|---|
| Laboral | `mail` | `https://josue.ink/rf/` | `reconocimientofacial` | `mail` |
| Personal `ojos` | `liveyourdre2` | `https://josue.ink/ojos/` | `reconocimientofacial_ojos` | `liveyourdre2` |

- Un solo repo `reconocimientoFacial` y una sola rama `main`.
- `ojos` se ejecuta desde el checkout `/root/reconocimientoFacial` de
  `liveyourdre2`; no se crea un directorio copia.
- Los cambios se mergean en `main` y se despliegan a las dos instancias:
  `deploy/deploy_prod.sh` (laboral) y `deploy/ojos/deploy_ojos.sh` (personal).

## Aislamiento

- **BD**: base y usuario propios (`reconocimientofacial_ojos` / `rf_ojos`).
  Esquema limpio sin datos, generado con `mysqldump --no-data`.
- **Datos**: los directorios runtime del checkout de `liveyourdre2` se archivan
  en `/root/onx-backups/ojos-preinit-*` y se recrean vacíos. Nada se copia de
  `mail`.
- **Web**: vhost interno `127.0.0.1:8088`, pool PHP-FPM `ojos`, sesión
  `OJOSSESSID` y cookie con path `/ojos/`.
- **PWA**: manifiesto dinámico `admin/manifest.php`, iconos propios, service
  worker con cache derivada de su scope y prompt de instalación con clave
  localStorage por instancia.
- **SuperServer**: proyecto `ojos` con `home: liveyourdre2`, spool/retornos/modo
  propios; la flota es compartida, la cola no.

## Cámaras

Las 5 cámaras se registran como “IP” con URL MJPEG del bridge local:

```
http://127.0.0.1:8111/camaraip/stream?camera=<id>
```

IDs: `esp32-oficina`, `cam-oficina`, `onx-josue`, `cam-portatil`,
`esp32-josue`. La captura se queda en `liveyourdre2`; el análisis pesado se
delega a SuperServer.

## Operación

```bash
# Provisión única (root, liveyourdre2)
bash deploy/ojos/init_ojos.sh

# Despliegue de cambios
bash deploy/ojos/deploy_ojos.sh

# Las dos instancias
bash deploy/ojos/deploy_all.sh
```

Credenciales de `ojos`: `/root/onx-secrets/ojos/credentials.env` (0600).
Panel: `https://josue.ink/ojos/admin/`.

## Encender SuperServer para `ojos`

```bash
printf 'superserver\n' > /var/lib/taildeck/projects/ojos.mode
# o desde el panel de SuperServer: Proyectos -> ojos -> COMPARTIENDO
```

Para volver a local: `printf 'local\n' > /var/lib/taildeck/projects/ojos.mode`.

## Límites

- No se abren puertos públicos nuevos.
- No se reinicia `josue` ni se restauran sus backups sin autorización.
- Si en el futuro las dos instancias comparten host, hará falta separar
  `RUTA_DATOS` del árbol de código; hoy están en hosts distintos.
