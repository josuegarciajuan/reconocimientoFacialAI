# Spec 04 — Rutas

> Estado: aprobado (Fase 0). Se implementa en Fase 3.

## 1. Objetivo

Trazar el recorrido de una persona dentro del recinto a partir de sus estancias en las
cámaras, dibujándolo sobre el plano con nodos intermedios y calculando tiempos.

## 2. Comportamiento actual (a mantener y corregir)

- `estancias` guarda (persona_id, camara_id, fecha_ini, fecha_fin) por paso.
- `nodos` guarda puntos intermedios entre pares de cámaras (camara_id1, camara_id2, x, y, orden).
- `rutas/list.php` agrupa la cadena entrada→salida de una persona y `javascript.php` dibuja
  la ruta con polilíneas (fetch síncrono de nodos por par de cámaras).

## 3. Problemas a resolver (Fase 3)

| # | Problema | Solución |
|---|---|---|
| R1 | `camara_id in()` vacío si no hay cámaras puerta/salida → error SQL | SQL defensivo (condición vacía → sin filtro). |
| R2 | Cadena de estancias frágil (lógica repartida PHP/JS, template strings) | Calcular la cadena **en PHP** (orden por fecha_ini) y pasar JSON limpio al JS. |
| R3 | `getCursorPosition` / clic en canvas muerto (referencias a variables de código comentado) | Eliminar código muerto; clic opcional para inspeccionar nodo. |
| R4 | Ruta con líneas rectas entre cámaras sin nodos | Usar nodos existentes; si no hay nodos para el par, dibujar recta con aviso. |

## 4. Diseño propuesto

1. **Backend**: función `construye_ruta(persona_id, fecha_ini, fecha_fin)` → cadena de
   estancias ordenada (cámara, entrada, salida, foto), tiempo total, lista de cámaras.
2. **Nodos**: `nodos_entre(cam_a, cam_b)` → puntos ordenados (ya existe en `acciones_ajax` a=2).
3. **Frontend**: `ver_ruta()` consume JSON único (rutas + nodos), dibuja plano + polilínea
   + marcadores con tiempos. Un solo fetch (no N síncronos).
4. Eliminar el `a=1` muerto de `rutas/acciones_ajax.php`.

## 5. Criterios de éxito

- [ ] Persona que pasa por N cámaras → ruta continua entrada→salida.
- [ ] Tiempo total correcto (fecha_fin última − fecha_ini primera).
- [ ] Sin errores SQL con/sin cámaras puerta/salida.
- [ ] Nodos intermedios usados cuando existen; recta con aviso si no.
