# Spec 08 — Fichajes con horario habitual y conciliador

> Estado: implementado (2026-08-19). Fase: panel (fichajes v2).

## 1. Problema

El listado de fichajes (v1) agrupaba estancias por trabajador y día tomando
"la primera cámara puerta" como entrada y "la última cámara salida" como salida,
sin horario de referencia y sin distinguir jornada partida. Eso provocaba que:

- Los pasos intermedios por la puerta (fumar, recoger, recados) no se distinguían
  de la salida definitiva.
- Con jornada partida (entrar/salir 2 veces) solo se veía 1 entrada y 1 salida.
- No había forma de que "la última salida del día" se fijara como salida definitiva.

## 2. Solución

### 2.1 Horario por local

Nuevas columnas en `locales` (migración `sql/2026-08-19-horarios-fichajes.sql`):

| Columna | Tipo | Descripción |
|---|---|---|
| `jornada_partida` | TINYINT | 0 = continua (1 bloque), 1 = partida (hasta 2 bloques) |
| `hora_entrada1` | TIME | hora habitual de entrada (bloque 1) |
| `hora_salida1` | TIME | hora habitual de salida (bloque 1) |
| `hora_entrada2` | TIME | hora habitual de entrada (bloque 2, tarde) |
| `hora_salida2` | TIME | hora habitual de salida (bloque 2, tarde) |
| `margen_fichaje_min` | INT | tolerancia en minutos para las ventanas de horario (def. 30) |

Sin horario configurado => comportamiento legacy (1 entrada + 1 salida al día).
UI: `admin/pages/locales/edit.php` + persistencia en `admin/pages/locales/acciones.php`.

### 2.2 Tabla `fichajes` (resultado conciliado)

El daemon conciliador escribe aquí el resultado por (persona, día, bloque):

- `entrada_*` / `salida_*`: hora, cámara y estancia origen (para mostrar foto).
- `estado`: `provisional` (día en curso, la salida puede cambiar) o `conciliado`
  (día cerrado, salida definitiva).
- Upsert idempotente: se borran los bloques del (persona, día) y se reinsertan.
  v1 sin edición manual: el conciliador siempre puede recomputar.

### 2.3 Algoritmo de conciliación (`libs/conciliador.php`)

Entrada: estancias del día en cámaras `puerta=1 OR salida=1` (eventos ENTRY/EXIT).

1. **Sin horario** => 1 bloque: `entrada = 1er ENTRY`, `salida = último EXIT`.
2. **Con horario** (margen `M`; `e2_inicio = hora_entrada2 − M`):
   - `hay_bloque2 = jornada_partida AND existe ENTRY ≥ e2_inicio`
     (la persona "volvió por la tarde").
   - Si `hay_bloque2` (jornada partida real):
     - `entrada1 = 1er ENTRY del día`
     - `entrada2 = 1er ENTRY ≥ e2_inicio`
     - `salida1 = último EXIT anterior a entrada2` (salida a comer)
     - `salida2 = último EXIT del día` (salida definitiva)
   - Si no: 1 bloque con `entrada = 1er ENTRY` y `salida = último EXIT`.

**Anomalías cubiertas** (testeado en `tests/fichajes_conciliador_test.php`):

| Caso | Resultado |
|---|---|
| Pasos intermedios por la puerta (fumar, recados) | Ignorados: solo importan 1er ENTRY y último EXIT de cada bloque |
| Jornada partida normal | 2 bloques (mañana y tarde) con salida a comer |
| Jornada partida configurada pero media jornada | 1 bloque (no hay ENTRY por la tarde) |
| Jornada partida configurada pero jornada continua | 1 bloque (nunca sale a comer) |
| Horario distinto al configurado | 1 bloque con primer ENTRY / último EXIT |
| Vuelta de comer muy tarde (fuera de ventana) | Sigue formando bloque 2 |
| Sin salida aún (día en curso) | `salida = null`, estado provisional |

### 2.4 Daemon `conciliador.php` (rf-conciliador)

Nuevo servicio systemd (p6), patrón `while(true)` como `clasificadorV2.php`:

- Cada `CONFIG_CONCILIADOR_LOOP` segundos (def. 60):
  - **Hoy**: fichajes provisionales (salida en vivo).
  - **Ayer** (+ días abiertos anteriores): conciliados (salida definitiva).
  - **1ª vez por local**: backfill de `CONFIG_CONCILIADOR_BACKFILL_DIAS` días (def. 30).
- Logs por stdout -> `journalctl -u rf-conciliador -f`.

Constantes en `config/config.php`: `CONFIG_CONCILIADOR_LOOP`,
`CONFIG_CONCILIADOR_BACKFILL_DIAS`, `CONFIG_CONCILIADOR_MARGEN_DEFECTO`.

### 2.5 Listado (`admin/pages/fichajes/list.php`)

Lee `fichajes` (join personas/cámaras/fotos) y muestra por trabajador y día
hasta 2 bloques con entrada (hora+cámara+foto), salida (hora+cámara+foto),
duración del bloque y estado (provisional/conciliado). Filtros: persona y rango.

## 3. Verificación

- `php -l` en todos los PHP tocados.
- `php tests/fichajes_conciliador_test.php` => 13/13 OK (lógica pura sin BD).
- Migración aplicada: `mysql -uroot reconocimientofacial < sql/2026-08-19-horarios-fichajes.sql`.
- Servicio: `sudo bash deploy/install_services.sh start` (incluye rf-conciliador).

## 4. Limitaciones v1

- Sin edición manual de fichajes (el conciliador siempre recomputa).
- Horario único para todos los días de la semana y para todo el local
  (sin override por persona).
- La dirección entrada/salida la da el flag de cámara (`puerta`/`salida`),
  igual que en la versión anterior.
