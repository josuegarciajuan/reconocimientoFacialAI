# Reset total de las dos instancias

Procedimiento de borrado controlado que deja el sistema a cero conservando la
configuración.

## Alcance

| Instancia | Host | BD | Proyecto |
|---|---|---|---|
| `ojos` (personal) | `liveyourdre2` (local) | `reconocimientofacial_ojos` | `ojos` |
| `mail` (laboral) | `RF_PROD_HOST` (SSH) | la de su `.env` | `reconocimientoFacial` |

## Qué se conserva

- Cámaras, locales, líneas, planos, nodos, senderos y sus puntos.
- Usuarios, dispositivos auto-login y teléfonos de alarma.
- Calibraciones por cámara.
- Modelos, venv, configuración de despliegue y `.env`.

## Qué se borra

- Personas, galerías (`face_enc_v2`), fotos, avatares, retratos.
- Estancias, cruces, fichajes, alarmas históricas.
- Vídeos, vídeos archivados, `.units/` de captura.
- Colas del clasificador, dedup, audit, pending, evidence, caches.
- Cola duradera (`motor/jobs/`), manifiestos (`motor/artifacts/`).
- Métricas y publicaciones del pipeline.
- Peticiones y retornos pendientes de **esta instancia** en SuperServer.
- Uploads de registro y fotos publicadas del panel.

## Comandos

```bash
# 1) Inventario sin tocar nada
bash deploy/reset_all.sh --dry-run --instance all

# 2) Ejecución real (pide escribir RESET)
bash deploy/reset_all.sh --instance all

# 3) Solo una instancia
bash deploy/reset_all.sh --instance ojos
bash deploy/reset_all.sh --instance mail

# Sin interacción (operación desatendida)
bash deploy/reset_all.sh --instance all --yes
```

Opciones:

- `--start`: rearranca servicios al final. Por defecto quedan **apagados** para
  la puesta en marcha controlada.
- `--hold N`: pausa con re-verificación de que nada se autola.
- `--no-pull`: en `mail`, no hace `git pull` antes del reset.

## Garantías

1. **Host verificado**: `ojos` aborta si `hostname` no es `liveyourdre2`; `mail`
   aborta si su `.env` apunta a `proyecto=ojos`.
2. **Huella de configuración**: antes y después se calcula el número de filas de
   las tablas de configuración y el checksum de `camaras`. Si cambia, el script
   aborta con error.
3. **Generación invalidada**: al borrar `motor/jobs/` desaparece la generación
   activa. Un resultado antiguo que llegue después no puede aplicarse (no hay
   generación activa que lo valide); al arrancar el pipeline se crea una nueva.
4. **SuperServer acotado**: solo se eliminan peticiones cuyo `project` coincide
   y el directorio de retornos de esa instancia. Otros proyectos no se tocan.
5. **Motor apagado**: por defecto `--no-start`; no se procesa nada hasta la
   puesta en marcha.

## Verificación posterior

```bash
# Servicios (deben quedar inactivos salvo rf-live)
systemctl status rf-capturador rf-detector rf-pipeline --no-pager

# BD: identidad y movimiento a cero; configuración intacta
mysql ... -e "SELECT COUNT(*) FROM personas; SELECT COUNT(*) FROM videos; SELECT COUNT(*) FROM camaras;"

# Motor: galería y colas ausentes
ls motor/bbdd_reconocimiento/1/face_enc_v2 2>/dev/null || echo "galería limpia"
ls motor/jobs 2>/dev/null || echo "cola limpia"
```

## Reversión

El reset **no es reversible**. Antes de ejecutarlo en producción, hacer copia de
seguridad de la BD y del `.env` si se necesita conservar evidencia histórica.
