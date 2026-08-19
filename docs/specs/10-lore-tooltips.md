# Spec 10 — Lore Tooltips: bocadillos de terminología temática

> Estado: **aprobado e implementado (2026-08-19)**.
> El panel usa una temática Mordor / El Señor de los Anillos (Barad-dûr, El Ojo que
> Todo lo Ve, La Puerta Negra…) con nomenclatura que un usuario que no siga la saga
> no entiende. Esta spec fija el sistema que explica **cada término temático** al pasar
> el ratón o enfocar: **qué significa**.

## 1. Objetivo

Todo término de temática presente en el panel (menú, dashboard, notificaciones, config,
login, ayudas) debe mostrar un bocadillo explicativo sin necesidad de indicador visual:
basta con posarse encima. Un usuario sin contexto de la saga entiende qué es cada cosa.

## 2. Regla "por defecto" (obligatoria para futuras UIs)

> **Cualquier texto temático nuevo que se introduzca en el panel DEBE terminar explicado
> por un bocadillo de lore, sin excepción.** El motor lo consigue automáticamente si el
> término está registrado en el glosario:

1. Añadir la entrada al glosario central **`admin/includes/glosario.php`** (función
   `rf_glosario()`). Es la **única fuente de verdad**.
2. El motor (`admin/files/lore.js`) lo detecta solo por **texto** cuando `match:"auto"`
   (mayoría de casos). **No hace falta tocar el HTML**.
3. Si el término es **ambiguo** (aparece con otro significado en texto normal:
   "Puerta", "Salida", "Encendida"...), declararlo con `match:"explicito"` y poner
   `data-lore="<clave>"` en el elemento HTML exacto que debe explicarse.

### Flujo de resolución del motor (lore.js)

```
1. ¿El elemento (o un ancestro) tiene data-lore="<clave>"?  -> usar esa entrada.
2. Si no: tomar el texto del elemento "titular" más cercano
   (a, button, h1-h5, th, label, summary, .*title, .*label, breadcrumb…).
3. Limpiar texto (quitar emojis/puntuación, minúsculas).
4. ¿Igualdad exacta con un término match:"auto"?  -> usar esa entrada.
5. ¿Contención con límite de palabra y texto <= 90 caracteres? -> usar esa entrada.
6. Sin coincidencia -> no mostrar bocadillo (texto no temático).
```

## 3. Contrato de entradas del glosario

```php
"<clave-slug>" => [
    "termino"     => "Texto temático exacto tal y como aparece", // string
    "significado" => "Qué es en la realidad de la app",           // string
    "match"       => "auto" | "explicito",                        // string
],
```

Reglas:
- La **clave** es un slug estable (`kebab-case`), inmutable una vez creada (los `data-lore`
  la referencian).
- `termino` debe coincidir con el texto visible (el motor normaliza emojis/puntuación y
  minúsculas, pero **mantiene acentos**: `Líneas ≠ Lineas`).
- `match:"auto"` es el valor por defecto recomendado: máxima cobertura "gratis".
- `match:"explicito"` solo para términos que colisionen con lenguaje normal.

## 4. Componentes

| Componente | Ruta | Rol |
|---|---|---|
| Glosario (fuente) | `admin/includes/glosario.php` | Array `rf_glosario()` + `rf_glosario_json()` (→ `window.RF_GLOSARIO`) |
| Motor | `admin/files/lore.js` | Delegación `pointerover`/`focusin`; resuelve clave; pinta/oculta bocadillo |
| Estilos | `admin/files/custom.css` (`.rf-lore*`) | Bocadillo carbón + oro, caret, Cinzel, `prefers-reduced-motion` |
| Carga en panel | `admin/index.php` | `require glosario.php` + `<script>RF_GLOSARIO</script>` + `lore.js` |
| Carga en login | `admin/login.php` | Ídem (el login ya carga `custom.css`) |
| Términos ambiguos | HTML con `data-lore="<clave>"` | p. ej. radios Puerta/Salida/Encendida en `config/edit.php` |

## 5. Accesibilidad y comportamiento

- **Hover** (ratón) y **focus** (teclado) muestran el bocadillo; `blur`, `pointerout`
  (con 120 ms de gracia), **Esc**, scroll o resize lo ocultan.
- El bocadillo es `role="tooltip"`, `pointer-events:none`, y se reposiciona para no
  desbordar el viewport (flipa hacia arriba si no cabe abajo).
- Sin indicador visual en los elementos: se asume que casi todo tiene explicación.
- `prefers-reduced-motion`: sin transiciones.
- El match automático **nunca** dispara en `input`, `textarea` o `select`.

## 6. Catálogo actual (2026-08-19)

### Marca global
| Clave | Término | Significado |
|---|---|---|
| `mordor` | Mordor | El sistema completo de vigilancia y control de accesos |
| `barad-dur` | Barad-dûr | El panel de administración (la Torre Oscura) |
| `ojo-todo-lo-ve` | El Ojo que Todo lo Ve | La red de cámaras de vigilancia |
| `puerta-negra` | La Puerta Negra | Pantalla de login |
| `entrar-mordor` | Entrar a Mordor | Iniciar sesión |
| `abandonar-mordor` | Abandonar Mordor | Cerrar sesión |
| `el-ojo-observa` | El Ojo te observa | Espera del login |
| `un-anillo` | Un Anillo | Decorativo (ex toggle de tema) |
| `inscripcion-anillo` | Inscripción del Anillo | Frase en Lengua Negra del Anillo Único |
| `buscar-mordor` | Buscar en Mordor | Buscador global |

### Menú
| Clave | Término | Significado |
|---|---|---|
| `la-torre` | La Torre | Dashboard con KPIs y gráfico |
| `fortalezas` | Fortalezas | Locales/sedes con cámaras, plano y aforo |
| `pueblos` | Pueblos | Visitantes con identidad facial |
| `movimientos` | Movimientos | Accesos: entradas y salidas |
| `lineas` | Líneas | Cruces de línea virtuales |
| `caminos` | Caminos | Rutas entre cámaras |
| `la-forja` | La Forja | Configuración |
| `ojo-en-vivo` | El Ojo en Vivo | Cámaras en directo |
| `fichajes` | Fichajes | Control horario de trabajadores |
| `el-concilio` | El Concilio | Ayuda |

### Dashboard
| Clave | Término | Significado |
|---|---|---|
| `cronicas-guerra` | Crónicas de Guerra | Panel de KPIs |
| `reinvocar-datos` | Reinvocar Datos | Refrescar datos |
| `almas-fortaleza` | Almas en la Fortaleza | Aforo actual |
| `cruzaron-puerta` | Cruzaron la Puerta Negra | Visitas de hoy |
| `huestes-dia` | Huestes al Día | Media diaria de visitas |
| `leales-mordor` | Leales a Mordor | Visitantes recurrentes |
| `mapa-asedio` | Mapa de Asedio | Gráfico actual vs anterior |
| `elegir-era` | Elegir era | Selector de periodo |
| `un-amanecer` / `una-luna` / `un-ciclo` / `una-era` | — | Filtros día/semana/mes/año |

### Notificaciones
| Clave | Término | Significado |
|---|---|---|
| `senal-guerra` | Señales de Guerra | Notificaciones de puerta/salida |
| `ninguna-senal` | Ninguna señal de guerra | Sin notificaciones pendientes |

### La Forja (ambiguos, `match:"explicito"` + `data-lore`)
| Clave | Término | Significado |
|---|---|---|
| `puerta-camara` | Puerta | Cámara de entrada |
| `salida-camara` | Salida | Cámara de salida |
| `encendida` | Encendida | Cámara activa |

### El Concilio
| Clave | Término | Significado |
|---|---|---|
| `guia-reino` | Guía del Reino | Resumen de secciones |
| `preguntas-frecuentes` | Preguntas Frecuentes | FAQ |
| `ultimo-recurso` | Último Recurso | Contacto / diagnóstico |

## 7. Criterios de aceptación

- [ ] Todo término del catálogo muestra bocadillo (hover y focus) con significado.
- [ ] Texto no temático NO dispara bocadillos (cero falsos positivos verificados en listados).
- [ ] Términos ambiguos solo se explican donde llevan `data-lore`.
- [ ] `php -l` verde en los PHP tocados.
