# Spec 11 — El Ojo del Anillo: hub maestro flotante

> Estado: **aprobado (2026-08-19) — implementado en esta misma sesión**.
> El widget "💍 Un Anillo" (fijo abajo a la derecha, herencia del antiguo toggle de
> modo oscuro) era decorativo. Esta spec lo convierte en el **centro de mando flotante**
> del panel: búsqueda global, navegación rápida, estado de los Seis Centinelas en vivo
> y semáforo pasivo de anomalías ("El Anillo arde").

## 1. Objetivo

Dar utilidad real a un elemento que ocupaba espacio de forma permanente: el anillo pasa
a ser el punto de entrada a las acciones más frecuentes desde **cualquier página** del
panel, sin navegar al dashboard. Además, en reposo comunica el estado de salud del
sistema de un vistazo.

## 2. Comportamiento

### 2.1 El anillo como botón

- El widget pasa de `div[role=img]` a `button` con `aria-haspopup="dialog"`,
  `aria-expanded` y `aria-controls`.
- **Clic** en el anillo → abre/cierra el hub. **`Esc`** o **clic fuera** → cierra.
  **`Ctrl+K`** (o `Cmd+K`) → abre desde teclado.
- Al abrir: foco al campo de búsqueda. Al cerrar: retorno de foco al botón.
- El hub es un `role="dialog"` anclado al anillo (abajo a la derecha), `z-index: 80`,
  por debajo de los tooltips (`rf-tip` 100, `rf-lore` 300).

### 2.2 Zonas del hub

1. **Cabecera**: título "💍 Un Anillo para gobernarlos" + línea de estado resumida
   (`5/6 centinelas · 3/4 cámaras · aforo 67%`) + botón cerrar.
2. **Buscar en Mordor**: input + botón "Ir" (form). Mismo destino que el buscador del
   top bar: `?page=visitantes&buscador=<término>`.
3. **Navegación rápida**: grid de 2 columnas con las 10 secciones del menú (emojis y
   títulos ya existentes; "Fortalezas" solo si `$_SESSION["admin"] == 1`).
4. **Los Seis Centinelas**: estado en vivo de los daemons, reutilizando
   `dash_daemons_html()` vía `accionesAjax.php?a=5`, refresco cada 10 s **solo mientras
   el hub está abierto**.

### 2.3 Semáforo pasivo (anillo en reposo)

- **OK** → anillo dorado con brillo sutil (estado actual).
- **Alerta** → el anillo **"arde"**: `ring-widget--arde` con glow naranja/rojo pulsante
  + badge con el nº de anomalías.
- Fuente: nuevo `accionesAjax.php?a=7` → JSON:
  `{ daemons:{en_pie,total,caidos}, camaras:{total,apagadas}, aforo:{actual,max,pct,estado},
    anomalias, detalle[] }`. Polling cada 15 s siempre (barato: 3 consultas + systemctl).
- Anomalías contadas: centinela caído, cámara apagada (`encendida=0`), aforo ≥ 85 %.
  (Mismo criterio que las "anomalías" del dashboard.)
- Si el AJAX falla: el anillo queda dorado neutro (degradación elegante, sin romper).

## 3. Componentes y archivos

| Archivo | Rol |
|---|---|
| `admin/files/ring-hub.js` (**nuevo**) | Motor del hub: abrir/cerrar, atajos, búsqueda, polling de centinelas y semáforo. Vanilla JS (sin jQuery), mismo patrón que `dashboard.js` |
| `admin/files/custom.css` | Estados del botón (`--arde`, badge), popover `.ring-hub` y tiles de centinelas compactos (el `dashboard.css` no se carga fuera del dashboard) |
| `admin/index.php` | Markup del botón + hub; carga de `ring-hub.js` tras `ui-common.js` |
| `admin/accionesAjax.php` | `case "7"`: resumen JSON de anomalías (reutiliza `dash_daemons()`, `dash_aforo()`, consulta de cámaras) |
| `admin/includes/glosario.php` | Actualizado el término `un-anillo` (ya no "solo adorno") |
| `docs/specs/11-anillo-hub.md` | Esta spec |

### Detalles técnicos

- **Sin duplicar lógica**: los centinelas se sirven por `a=5` (idéntico al dashboard);
  el semáforo solo agrega un endpoint de resumen.
- **CSS**: las clases `.daemon-tile` usadas por `dash_daemons_html()` se re-estilan
  bajo `.ring-hub` porque `dashboard.css` no se carga en el resto de páginas. Keyframes
  propios (`ring-hub-live-pulse`, `ring-hub-alerta-pulso`) para no depender de los del
  dashboard.
- **Lore**: los textos del hub ("Un Anillo", "Buscar en Mordor", "La Torre", "El Ojo en
  Vivo"…) se explican solos por el motor de lore (glosario `match:"auto"`), coherente con
  el resto del panel. No se usa `data-tip` en el botón para evitar tooltips duplicados.
- **Accesibilidad**: botón con `aria-expanded`/`aria-controls`, `role="dialog"` con
  `aria-hidden` gestionado, retorno de foco, y `prefers-reduced-motion` apaga animaciones
  (`ring-widget--arde`, leds, transición del hub).

## 4. Seguridad

- `a=7` reutiliza `dash_daemons()` (ya protegida: `systemctl is-active` con
  `escapeshellarg`) y consultas PDO parametrizadas por `local_id` de sesión.
- No introduce endpoints de escritura ni exposición de datos nuevos.

## 5. Alcance / no-alcance

- **Sí**: hub funcional en todas las páginas del panel (index.php es el shell común).
- **No**: búsqueda por secciones múltiples (el buscador global actual solo filtra
  visitantes); atajo personalizable; persistencia de "abierto".
