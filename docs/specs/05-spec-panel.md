# Spec 05 — Panel de administración (refactor completo)

> Estado: aprobado (Fase 0). Se implementa en Fase 4. PHP puro + PDO (decisión validada).

## 1. Objetivo

Reescribir la capa web eliminando: SQL injection, credenciales en claro, `chmod 777`,
`exec()` con input sin sanear, y todos los bugs funcionales del inventario (B9–B20).
Mantener el esquema MySQL y la funcionalidad existente.

## 2. Decisiones técnicas

| Decisión | Valor | Motivo |
|---|---|---|
| Acceso a datos | **PDO + prepared statements** (reemplaza `mysql.class.php` con concatenación) | Elimina SQLi de raíz. |
| Auth | `password_hash()`/`password_verify()` + rate-limit + session hardening | Hoy guarda claro + `md5` roto. |
| CSRF | Token por sesión en toda mutación (POST y mutaciones por GET se convierten a POST) | Sin protección hoy. |
| Inputs | Saneado/validación centralizada | Hoy `$_GET` crudo en todo. |
| Shell | Eliminar `exec()` de shell con input; las tareas Python se disparan por endpoints internos controlados | Hoy `exec("python3.7 …")` en la UI. |
| Routing | Whitelist central en `admin/index.php` + `content.php` saneado | Hoy switch frágil. |
| Errores | `display_errors=0` en producción + log | Hoy muestra SQL/errores. |

## 3. Alcance (módulos)

- **Locales**: CRUD + scaffolding de carpetas (crear dirs de forma segura, sin `chmod 777`
  global), password con hash, aforo.
- **Cámaras**: CRUD + parámetros de sensibilidad; arreglar "encendida" al crear; snapshot.
- **Config**: plano, creación/edición de cámaras y líneas; corregir índices de líneas
  (B16); selects sin miles de opciones.
- **Personas/visitantes**: listado (fix alias `c.id` B14, buscador sin inyección), editar
  (nombre, trabajador), unir personas (fix B11/B17), mover fotos (fix `cambiar_foto_de_persona.py`),
  registro webcam multi-pose (disparar `enrolamiento.py`, fix B18).
- **Movimientos/accesos**: listado con fechas correctas (fix B13) y filtros.
- **Fichajes**: agregación por trabajador/día correcta (fix B17), descarga funcional.
- **Líneas**: listado + filtros dirección correctos.
- **Rutas**: ver Spec 04.
- **Dashboard**: KPIs sin división por cero (B12), gráficas ligeras.

## 4. Bugs del inventario cubiertos

B9 (SQLi), B10 (login/password), B11 (notificaciones), B12 (dashboard), B13 (fechas PM),
B14 (alias c.id), B15 (rutas `in()`), B16 (índices líneas), B17 (fichajes `$aux`/descarga),
B18 (subir_video2), B19 (`?descargar=` roto), B20 (`exit;` capturador).

## 5. Estructura propuesta

```
admin/
  index.php            # shell + session + whitelist de páginas
  auth.php             # login (password_verify, rate-limit), logout
  csrf.php             # generación/validación de token
  db.php               # conexión PDO única (DSN por entorno)
  content.php          # router
  pages/<modulo>/
    index.php          # lógica (POST → acción → redirect)
    list.php           # render
    javascript.php
libs/db.php            # PDO centralizado (sustituye mysql.class.php)
```

## 6. Testing

- `php -l` en todos los archivos tocados.
- Pruebas manuales guionizadas por módulo (login admin/local, CRUD, filtros, unir, mover).
- Auditoría: grep de `exec(`/`$_GET`/`$_POST` sin saneado; grep de `mysql_query`/concat SQL.
- (Opcional) phpstan nivel básico en los módulos críticos.

## 7. Criterios de éxito

- [ ] Cero SQLi verificable (grep + prueba con payload en buscador y filtros).
- [ ] Login admin y local funcionales (password hasheado, rate-limit).
- [ ] Todas las mutaciones con CSRF.
- [ ] Fechas/filtros correctos (AM/PM, rangos).
- [ ] `chmod 777` eliminado de la aplicación (solo dirs de datos necesarios, 775 con ACL si hace falta).
- [ ] Enrolamiento multi-pose dispara `motor/enrolamiento.py` (venv).
