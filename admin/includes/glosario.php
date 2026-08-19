<?php

/*
 * Glosario de lore — Barad-dûr (Mordor)
 *
 * FUENTE ÚNICA DE VERDAD de la terminología temática del panel.
 * El motor admin/files/lore.js consume esta lista (vía window.RF_GLOSARIO)
 * para mostrar bocadillos explicativos al pasar el ratón / enfocar:
 * "¿qué significa este término?".
 *
 * Convención (ver docs/specs/10-lore-tooltips.md):
 *  - Cada término temático del panel DEBE estar aquí.
 *  - match:
 *      "auto"      -> el motor lo detecta automáticamente por texto
 *                     (palabra exacta o contenida con límite de palabra).
 *      "explicito" -> solo se muestra con data-lore="<clave>" en el HTML
 *                     (para términos ambiguos: Puerta, Salida, Encendida...).
 */

function rf_glosario() {
    return [

        /* ---------------- Marca global ---------------- */
        "mordor" => [
            "termino"    => "Mordor",
            "significado" => "Nombre temático del sistema completo de vigilancia y control de accesos por reconocimiento facial. Todo lo que ves aquí es 'Mordor'.",
            "match"      => "auto",
        ],
        "barad-dur" => [
            "termino"    => "Barad-dûr",
            "significado" => "La 'Torre Oscura' de Sauron: en la app es el panel de administración, el lugar desde el que se vigila y se gestiona todo.",
            "match"      => "auto",
        ],
        "ojo-todo-lo-ve" => [
            "termino"    => "El Ojo que Todo lo Ve",
            "significado" => "El Ojo de Sauron: en la app es la red de cámaras que vigila en tiempo real cada entrada y salida.",
            "match"      => "auto",
        ],
        "puerta-negra" => [
            "termino"    => "La Puerta Negra",
            "significado" => "La entrada a Mordor: en la app es la pantalla de inicio de sesión. Cruza la puerta solo si tienes credenciales.",
            "match"      => "auto",
        ],
        "entrar-mordor" => [
            "termino"    => "Entrar a Mordor",
            "significado" => "Iniciar sesión en el panel. El botón de acceso de la Puerta Negra.",
            "match"      => "auto",
        ],
        "abandonar-mordor" => [
            "termino"    => "Abandonar Mordor",
            "significado" => "Cerrar sesión y salir del panel. Al abandonar Mordor, el Ojo deja de vigilarte a ti.",
            "match"      => "auto",
        ],
        "el-ojo-observa" => [
            "termino"    => "El Ojo te observa",
            "significado" => "Mensaje de espera mientras el login comprueba tus credenciales. El sistema está 'mirándote' antes de dejarte pasar.",
            "match"      => "auto",
        ],
        "un-anillo" => [
            "termino"    => "Un Anillo",
            "significado" => "Centro de mando del panel (abajo a la derecha): abre búsqueda global, accesos rápidos y el estado de los Seis Centinelas. 'Un Anillo para gobernarlos a todos'. Si arde en brasa, hay anomalías en Mordor.",
            "match"      => "auto",
        ],
        "inscripcion-anillo" => [
            "termino"    => "Inscripción del Anillo",
            "significado" => "Frase en Lengua Negra grabada en el Anillo Único: 'Ash nazg durbatulûk, ash nazg gimbatul…' = 'Un Anillo para gobernarlos a todos, uno para encontrarlos, uno para atraerlos a todos y atarlos en las tinieblas'. Decorativa.",
            "match"      => "explicito",
        ],
        "buscar-mordor" => [
            "termino"    => "Buscar en Mordor",
            "significado" => "Buscador global del panel: localiza visitantes, movimientos y demás registros en todo el sistema.",
            "match"      => "auto",
        ],

        /* ---------------- Menú / secciones ---------------- */
        "la-torre" => [
            "termino"    => "La Torre",
            "significado" => "Barad-dûr, el cuartel general: en la app es el dashboard con los indicadores (KPIs) y el gráfico de visitas.",
            "match"      => "auto",
        ],
        "fortalezas" => [
            "termino"    => "Fortalezas",
            "significado" => "Cada fortaleza es un local/sede: tiene sus cámaras, su plano, su aforo y sus visitantes.",
            "match"      => "auto",
        ],
        "pueblos" => [
            "termino"    => "Pueblos",
            "significado" => "Los pueblos sometidos de Mordor: en la app son los visitantes con identidad facial registrada.",
            "match"      => "auto",
        ],
        "movimientos" => [
            "termino"    => "Movimientos",
            "significado" => "Las tropas en marcha: en la app son los accesos, es decir, cada entrada y salida registrada por las cámaras de puerta.",
            "match"      => "auto",
        ],
        "lineas" => [
            "termino"    => "Líneas",
            "significado" => "Líneas virtuales dibujadas sobre el plano de la cámara: cuando alguien las cruza se registra un 'cruce de línea' con su dirección.",
            "match"      => "auto",
        ],
        "caminos" => [
            "termino"    => "Caminos",
            "significado" => "Los caminos de Mordor: en la app son las rutas que reconstruyen el recorrido de una persona entre cámaras (entrada → salida).",
            "match"      => "auto",
        ],
        "la-forja" => [
            "termino"    => "La Forja",
            "significado" => "Donde se forjaron los Anillos: en la app es la configuración (cámaras, plano, líneas, nodos y parámetros). Cambia con cuidado: afecta a todo el reino.",
            "match"      => "auto",
        ],
        "ojo-en-vivo" => [
            "termino"    => "El Ojo en Vivo",
            "significado" => "El Ojo vigilando ahora mismo: en la app son las cámaras con su stream en tiempo real y su último snapshot.",
            "match"      => "auto",
        ],
        "fichajes" => [
            "termino"    => "Fichajes",
            "significado" => "Control horario de los trabajadores: entrada (primera captura por cámara de puerta) y salida (última por cámara de salida) de cada día.",
            "match"      => "auto",
        ],
        "el-concilio" => [
            "termino"    => "El Concilio",
            "significado" => "El Concilio Blanco, donde se decide: en la app es la ayuda, con la guía del panel y las preguntas frecuentes.",
            "match"      => "auto",
        ],

        /* ---------------- Dashboard (La Torre) ---------------- */
        "cronicas-guerra" => [
            "termino"    => "Crónicas de Guerra",
            "significado" => "El cuadro de indicadores (KPIs) del dashboard: aforo, visitas de hoy, media diaria y visitantes recurrentes.",
            "match"      => "auto",
        ],
        "reinvocar-datos" => [
            "termino"    => "Reinvocar Datos",
            "significado" => "Recargar los datos del dashboard para traer las últimas crónicas del reino (refresca la página).",
            "match"      => "auto",
        ],
        "almas-fortaleza" => [
            "termino"    => "Almas en la Fortaleza",
            "significado" => "Aforo actual: cuántas personas hay ahora mismo dentro del local. Se puede editar el máximo permitido.",
            "match"      => "auto",
        ],
        "cruzaron-puerta" => [
            "termino"    => "Cruzaron la Puerta Negra",
            "significado" => "Visitas de hoy: cuántas personas distintas entraron por las cámaras de puerta en el día actual.",
            "match"      => "auto",
        ],
        "huestes-dia" => [
            "termino"    => "Huestes al Día",
            "significado" => "Media diaria de visitas: el promedio de personas distintas que entran cada día.",
            "match"      => "auto",
        ],
        "leales-mordor" => [
            "termino"    => "Leales a Mordor",
            "significado" => "Visitantes recurrentes: personas que repiten visita en más de un día distinto.",
            "match"      => "auto",
        ],
        "mapa-asedio" => [
            "termino"    => "Mapa de Asedio",
            "significado" => "Gráfico de visitas que compara el periodo elegido (amanecer/luna/ciclo/era) con el anterior.",
            "match"      => "auto",
        ],
        "elegir-era" => [
            "termino"    => "Elegir era",
            "significado" => "Selector del periodo del gráfico del Mapa de Asedio.",
            "match"      => "auto",
        ],
        "un-amanecer" => [
            "termino"    => "Un amanecer",
            "significado" => "Filtro del gráfico: hoy (periodo de un día).",
            "match"      => "auto",
        ],
        "una-luna" => [
            "termino"    => "Una luna",
            "significado" => "Filtro del gráfico: esta semana (periodo de siete días).",
            "match"      => "auto",
        ],
        "un-ciclo" => [
            "termino"    => "Un ciclo",
            "significado" => "Filtro del gráfico: este mes.",
            "match"      => "auto",
        ],
        "una-era" => [
            "termino"    => "Una era",
            "significado" => "Filtro del gráfico: este año.",
            "match"      => "auto",
        ],

        /* ---------------- Dashboard v2 (La Torre, rediseño 2026-08-19) ---------------- */
        "estado-mordor" => [
            "termino"    => "Estado de Mordor",
            "significado" => "Resumen general del panel: el estado actual de Mordor de un vistazo (aforo, cámaras en pie, anomalías y vídeos de hoy).",
            "match"      => "auto",
        ],
        "camino-mensajero" => [
            "termino"    => "El Camino del Mensajero",
            "significado" => "Los accesos directos del dashboard: atajos de un clic a las secciones más usadas (fichajes, cámaras, movimientos, pueblos…).",
            "match"      => "auto",
        ],
        "vanguardia" => [
            "termino"    => "La Vanguardia",
            "significado" => "Las tarjetas KPI del dashboard: las métricas esenciales (entradas, aforo, fichajes, cámaras…) que se leen de un vistazo.",
            "match"      => "auto",
        ],
        "almas-dentro-ahora" => [
            "termino"    => "Almas dentro ahora",
            "significado" => "Personas que están dentro del local en este momento: su último cruce de entrada es posterior a su última salida.",
            "match"      => "auto",
        ],
        "legion-formacion" => [
            "termino"    => "Legión en formación",
            "significado" => "Trabajadores que ya han fichado hoy frente al total de trabajadores dados de alta en el local.",
            "match"      => "auto",
        ],
        "camaras-ciegas" => [
            "termino"    => "Cámaras ciegas",
            "significado" => "Cámaras apagadas: el Ojo no vigila por ellas. Si hay alguna, hay que revisarla en 'El Ojo en Vivo'.",
            "match"      => "auto",
        ],
        "hora-asedio" => [
            "termino"    => "Hora del asedio",
            "significado" => "La hora de hoy con más actividad (el pico de afluencia): cuándo se concentra la gente para prever aforo y turnos.",
            "match"      => "auto",
        ],
        "pergaminos-ojo" => [
            "termino"    => "Pergaminos del Ojo",
            "significado" => "Los vídeos de movimiento grabados: cuántos se generaron hoy y cuánto espacio (GB) ocupan en disco.",
            "match"      => "auto",
        ],
        "vigia-incansable" => [
            "termino"    => "El vigía incansable",
            "significado" => "La cámara más activa de hoy: la que más detecciones ha generado en lo que va de día.",
            "match"      => "auto",
        ],
        "puerta-vs-camaras" => [
            "termino"    => "La Puerta vs Las Cámaras",
            "significado" => "Distribución de la actividad por cámara en el último mes: qué cámaras captan más movimiento (gráfico de anillo).",
            "match"      => "auto",
        ],
        "fraguas-hora" => [
            "termino"    => "Las Fraguas por Hora",
            "significado" => "Mapa de calor de 7 días × 24 horas: la afluencia por día de la semana y hora, para ver los patrones de un vistazo.",
            "match"      => "auto",
        ],
        "entradas-salidas" => [
            "termino"    => "Entradas vs Salidas",
            "significado" => "Comparativa de entradas (cámara de puerta) y salidas (cámara de salida) por hora de hoy.",
            "match"      => "auto",
        ],
        "alcance-ojo" => [
            "termino"    => "El Alcance del Ojo",
            "significado" => "Las secciones de detalle del dashboard: feed en vivo, quién está dentro, quién falta por fichar y rankings.",
            "match"      => "auto",
        ],
        "cronica-ojo-en-vivo" => [
            "termino"    => "Crónica del Ojo en Vivo",
            "significado" => "Feed en tiempo real con los últimos movimientos registrados: quién entra o sale, por qué cámara y con su foto.",
            "match"      => "auto",
        ],
        "quien-esta-dentro" => [
            "termino"    => "Quién está Dentro",
            "significado" => "Lista de las personas que están ahora mismo dentro de la fortaleza, con su hora de entrada.",
            "match"      => "auto",
        ],
        "falta-por-fichar" => [
            "termino"    => "Falta por Fichar",
            "significado" => "Trabajadores que todavía no han fichado hoy, según el horario habitual del local.",
            "match"      => "auto",
        ],
        "concilio-fieles" => [
            "termino"    => "El Concilio de los Fieles",
            "significado" => "Rankings y glorias del mes: los visitantes más leales, el alma madrugadora y las rachas de presencia.",
            "match"      => "auto",
        ],
        "los-mas-leales" => [
            "termino"    => "Los más leales",
            "significado" => "Ranking de los visitantes más frecuentes en los últimos 30 días (quién visita más la fortaleza).",
            "match"      => "auto",
        ],
        "glorias-reino" => [
            "termino"    => "Glorias del Reino",
            "significado" => "Reconocimientos destacados: alma madrugadora de hoy, visitante más leal y rachas de presencia.",
            "match"      => "auto",
        ],
        "profecia-afluencia" => [
            "termino"    => "Profecía de Afluencia",
            "significado" => "Previsión de afluencia de hoy (línea dorada) frente a la media de los mismos días de semana de las últimas 4 semanas.",
            "match"      => "auto",
        ],
        "seis-centinelas" => [
            "termino"    => "Los Seis Centinelas",
            "significado" => "Los 6 procesos (daemons) del sistema: capturador, detector, clasificador, vinculador, conciliador y live. Si alguno cae, la vigilancia se resiente.",
            "match"      => "auto",
        ],
        "fichajes-hoy" => [
            "termino"    => "Fichajes de hoy",
            "significado" => "Acceso directo al listado de fichajes ya filtrado al día de hoy.",
            "match"      => "auto",
        ],
        "senal-alarma" => [
            "termino"    => "Señales de alarma",
            "significado" => "Alertas activas del dashboard: cámaras apagadas, aforo al límite o fichajes sin conciliar.",
            "match"      => "auto",
        ],

        /* Dashboard v2 — términos explícitos (solo con data-lore) */
        "caldero-aforo" => [
            "termino"    => "Caldero de aforo",
            "significado" => "Representa el aforo actual frente al máximo: la 'lava' sube según cuántas almas hay dentro.",
            "match"      => "explicito",
        ],
        "semaforo-aforo" => [
            "termino"    => "Semáforo de aforo",
            "significado" => "Nivel de ocupación de la fortaleza: Tranquilo (verde, <60%), Animado (oro, 60-85%) o Asedio (rojo, >85%).",
            "match"      => "explicito",
        ],
        "fijar-aforo" => [
            "termino"    => "Fijar el aforo",
            "significado" => "Actualizar manualmente el número de personas que hay dentro ahora (el aforo actual).",
            "match"      => "explicito",
        ],
        "camaras-en-pie" => [
            "termino"    => "Cámaras en pie",
            "significado" => "Cámaras encendidas (operativas) frente al total de cámaras desplegadas.",
            "match"      => "explicito",
        ],
        "anomalias-ojo" => [
            "termino"    => "Anomalías del Ojo",
            "significado" => "Alertas activas: cámaras apagadas, aforo al límite o fichajes provisionales sin conciliar de días anteriores.",
            "match"      => "explicito",
        ],
        "el-vigia" => [
            "termino"    => "El Vigía",
            "significado" => "Daemon capturador (rf-capturador): detecta movimiento y graba los vídeos en H.264.",
            "match"      => "explicito",
        ],
        "el-rastreador" => [
            "termino"    => "El Rastreador",
            "significado" => "Daemon detector (rf-detector): detecta cruces de línea y extrae las caras de los vídeos.",
            "match"      => "explicito",
        ],
        "la-mirada" => [
            "termino"    => "La Mirada",
            "significado" => "Daemon clasificador (rf-clasificador): ingesta a la base de datos (personas, estancias y fotos).",
            "match"      => "explicito",
        ],
        "el-atador" => [
            "termino"    => "El Atador",
            "significado" => "Daemon vinculador (rf-vinculador): enlaza los vídeos con las personas y los cruces de línea.",
            "match"      => "explicito",
        ],
        "el-conciliador" => [
            "termino"    => "El Conciliador",
            "significado" => "Daemon conciliador (rf-conciliador): calcula y concilia los fichajes diarios según el horario del local.",
            "match"      => "explicito",
        ],
        "el-mensajero" => [
            "termino"    => "El Mensajero",
            "significado" => "Daemon live (rf-live): sirve los snapshots en tiempo real para 'El Ojo en Vivo'.",
            "match"      => "explicito",
        ],

        /* ---------------- Notificaciones (Señales de Guerra) ---------------- */
        "senal-guerra" => [
            "termino"    => "Señales de Guerra",
            "significado" => "Las notificaciones: avisos de movimientos de puerta y salida (quién entró/salió y cuándo).",
            "match"      => "auto",
        ],
        "ninguna-senal" => [
            "termino"    => "Ninguna señal de guerra",
            "significado" => "No hay notificaciones pendientes: las puertas están en calma.",
            "match"      => "auto",
        ],

        /* ---------------- La Forja (Config) ---------------- */
        "el-yunque" => [
            "termino"    => "El Yunque",
            "significado" => "El plano del local: el lienzo donde se colocan cámaras y nodos y se dibujan las líneas. Es la base sobre la que se trabaja en La Forja.",
            "match"      => "explicito",
        ],
        "forjar" => [
            "termino"    => "Forjar",
            "significado" => "Crear una cámara nueva: dar forma al metal. Marca su posición en el lienzo y dale nombre.",
            "match"      => "explicito",
        ],
        "forja-camaras" => [
            "termino"    => "Forjar (Cámaras)",
            "significado" => "La sección de cámaras de La Forja: aquí se crean y se templan (editan) las cámaras del local.",
            "match"      => "explicito",
        ],
        "templar" => [
            "termino"    => "Templar",
            "significado" => "Editar una cámara existente y ajustar sus parámetros de análisis. El temple es el ajuste fino de la dureza del metal.",
            "match"      => "explicito",
        ],
        "cadenas" => [
            "termino"    => "Cadenas",
            "significado" => "Los nodos: puntos que unen dos cámaras en el plano. Son los eslabones que permiten reconstruir los caminos de las personas entre cámaras.",
            "match"      => "explicito",
        ],
        "unir-nodos" => [
            "termino"    => "Unir",
            "significado" => "Crear nodos: marcar en el lienzo los puntos del camino que une dos cámaras.",
            "match"      => "explicito",
        ],
        "mover-nodos" => [
            "termino"    => "Mover",
            "significado" => "Editar los nodos de un camino: arrastrar cada eslabón para recolocarlo sobre el plano real, o borrarlo con clic derecho.",
            "match"      => "explicito",
        ],
        "romper" => [
            "termino"    => "Romper",
            "significado" => "Eliminar la cadena de nodos que une dos cámaras.",
            "match"      => "explicito",
        ],
        "trazos" => [
            "termino"    => "Trazos",
            "significado" => "Las líneas de vigilancia: líneas virtuales dibujadas sobre la foto de una cámara. Cuando alguien las cruza se registra un cruce con su dirección.",
            "match"      => "explicito",
        ],
        "trazar" => [
            "termino"    => "Trazar",
            "significado" => "Dibujar una línea nueva sobre la foto de la cámara: dos clics, uno para el inicio y otro para el final.",
            "match"      => "explicito",
        ],
        "corregir" => [
            "termino"    => "Corregir",
            "significado" => "Editar una línea existente: reposicionar sus extremos sobre la foto de la cámara.",
            "match"      => "explicito",
        ],
        "puerta-camara" => [
            "termino"    => "Puerta",
            "significado" => "Cámara de entrada: marca el instante en que alguien cruza hacia dentro (genera el 'acceso' de entrada y los fichajes). Puede ser también de salida si se marca ambas.",
            "match"      => "explicito",
        ],
        "salida-camara" => [
            "termino"    => "Salida",
            "significado" => "Cámara de salida: marca el instante en que alguien cruza hacia fuera (genera el acceso de salida y cierra los fichajes del día). Puede ser también de entrada si se marca ambas.",
            "match"      => "explicito",
        ],
        "puerta-y-salida" => [
            "termino"    => "Entrada y salida a la vez",
            "significado" => "Una cámara puede ser de Puerta (entrada) y Salida a la vez si las personas entran y salen por el mismo sitio.",
            "match"      => "explicito",
        ],
        "encendida" => [
            "termino"    => "Encendida",
            "significado" => "Cámara activa: está capturando y analizando vídeo. Apagada, el Ojo no vigila por esa cámara.",
            "match"      => "explicito",
        ],

        /* ---------------- El Concilio (Ayuda) ---------------- */
        "guia-reino" => [
            "termino"    => "Guía del Reino",
            "significado" => "Resumen de qué se hace en cada sección del panel (la Torre, Fortalezas, Pueblos, Movimientos…).",
            "match"      => "auto",
        ],
        "preguntas-frecuentes" => [
            "termino"    => "Preguntas Frecuentes",
            "significado" => "FAQ: dudas habituales sobre cámaras, registro de visitantes, movimientos, aforo, plano y rutas.",
            "match"      => "auto",
        ],
        "ultimo-recurso" => [
            "termino"    => "Último Recurso",
            "significado" => "Contacto con el administrador: incluye los datos de sesión (fortaleza, URL, fecha) para diagnosticar el problema.",
            "match"      => "auto",
        ],
    ];
}

/**
 * Devuelve el glosario serializado a JSON para inyectar en la página
 * como window.RF_GLOSARIO. El motor lore.js lo consume.
 */
function rf_glosario_json() {
    return json_encode(rf_glosario(), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
}
