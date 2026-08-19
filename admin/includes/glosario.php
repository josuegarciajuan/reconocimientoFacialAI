<?php

/*
 * Glosario de lore — Barad-dûr (Mordor)
 *
 * FUENTE ÚNICA DE VERDAD de la terminología temática del panel.
 * El motor admin/files/lore.js consume esta lista (vía window.RF_GLOSARIO)
 * para mostrar bocadillos explicativos al pasar el ratón / enfocar:
 * "¿qué significa este término y a dónde apunta?".
 *
 * Convención (ver docs/specs/10-lore-tooltips.md):
 *  - Cada término temático del panel DEBE estar aquí.
 *  - match:
 *      "auto"      -> el motor lo detecta automáticamente por texto
 *                     (palabra exacta o contenida con límite de palabra).
 *      "explicito" -> solo se muestra con data-lore="<clave>" en el HTML
 *                     (para términos ambiguos: Puerta, Salida, Encendida...).
 *  - href: enlace relativo del panel (opcional). En login.php se suprime
 *          automáticamente (el motor lo detecta por body.login).
 */

function rf_glosario() {
    return [

        /* ---------------- Marca global ---------------- */
        "mordor" => [
            "termino"    => "Mordor",
            "significado" => "Nombre temático del sistema completo de vigilancia y control de accesos por reconocimiento facial. Todo lo que ves aquí es 'Mordor'.",
            "destino"    => "Toda la aplicación",
            "href"       => null,
            "match"      => "auto",
        ],
        "barad-dur" => [
            "termino"    => "Barad-dûr",
            "significado" => "La 'Torre Oscura' de Sauron: en la app es el panel de administración, el lugar desde el que se vigila y se gestiona todo.",
            "destino"    => "Panel de administración",
            "href"       => "?",
            "match"      => "auto",
        ],
        "ojo-todo-lo-ve" => [
            "termino"    => "El Ojo que Todo lo Ve",
            "significado" => "El Ojo de Sauron: en la app es la red de cámaras que vigila en tiempo real cada entrada y salida.",
            "destino"    => "Cámaras (El Ojo en Vivo)",
            "href"       => "?page=camaras",
            "match"      => "auto",
        ],
        "puerta-negra" => [
            "termino"    => "La Puerta Negra",
            "significado" => "La entrada a Mordor: en la app es la pantalla de inicio de sesión. Cruza la puerta solo si tienes credenciales.",
            "destino"    => "Login",
            "href"       => "login.php",
            "match"      => "auto",
        ],
        "entrar-mordor" => [
            "termino"    => "Entrar a Mordor",
            "significado" => "Iniciar sesión en el panel. El botón de acceso de la Puerta Negra.",
            "destino"    => "Login",
            "href"       => "login.php",
            "match"      => "auto",
        ],
        "abandonar-mordor" => [
            "termino"    => "Abandonar Mordor",
            "significado" => "Cerrar sesión y salir del panel. Al abandonar Mordor, el Ojo deja de vigilarte a ti.",
            "destino"    => "Cerrar sesión",
            "href"       => null,
            "match"      => "auto",
        ],
        "el-ojo-observa" => [
            "termino"    => "El Ojo te observa",
            "significado" => "Mensaje de espera mientras el login comprueba tus credenciales. El sistema está 'mirándote' antes de dejarte pasar.",
            "destino"    => "Login (proceso)",
            "href"       => null,
            "match"      => "auto",
        ],
        "un-anillo" => [
            "termino"    => "Un Anillo",
            "significado" => "Elemento decorativo (herencia del antiguo interruptor de tema oscuro). 'Un Anillo para gobernarlos a todos': solo adorno.",
            "destino"    => "Decorativo",
            "href"       => null,
            "match"      => "auto",
        ],
        "inscripcion-anillo" => [
            "termino"    => "Inscripción del Anillo",
            "significado" => "Frase en Lengua Negra grabada en el Anillo Único: 'Ash nazg durbatulûk, ash nazg gimbatul…' = 'Un Anillo para gobernarlos a todos, uno para encontrarlos, uno para atraerlos a todos y atarlos en las tinieblas'. Decorativa.",
            "destino"    => "Login (marca)",
            "href"       => null,
            "match"      => "explicito",
        ],
        "buscar-mordor" => [
            "termino"    => "Buscar en Mordor",
            "significado" => "Buscador global del panel: localiza visitantes, movimientos y demás registros en todo el sistema.",
            "destino"    => "Buscador global",
            "href"       => null,
            "match"      => "auto",
        ],

        /* ---------------- Menú / secciones ---------------- */
        "la-torre" => [
            "termino"    => "La Torre",
            "significado" => "Barad-dûr, el cuartel general: en la app es el dashboard con los indicadores (KPIs) y el gráfico de visitas.",
            "destino"    => "Dashboard",
            "href"       => "?page=dash",
            "match"      => "auto",
        ],
        "fortalezas" => [
            "termino"    => "Fortalezas",
            "significado" => "Cada fortaleza es un local/sede: tiene sus cámaras, su plano, su aforo y sus visitantes.",
            "destino"    => "Locales",
            "href"       => "?page=locales",
            "match"      => "auto",
        ],
        "pueblos" => [
            "termino"    => "Pueblos",
            "significado" => "Los pueblos sometidos de Mordor: en la app son los visitantes con identidad facial registrada.",
            "destino"    => "Visitantes",
            "href"       => "?page=visitantes",
            "match"      => "auto",
        ],
        "movimientos" => [
            "termino"    => "Movimientos",
            "significado" => "Las tropas en marcha: en la app son los accesos, es decir, cada entrada y salida registrada por las cámaras de puerta.",
            "destino"    => "Accesos",
            "href"       => "?page=accesos",
            "match"      => "auto",
        ],
        "lineas" => [
            "termino"    => "Líneas",
            "significado" => "Líneas virtuales dibujadas sobre el plano de la cámara: cuando alguien las cruza se registra un 'cruce de línea' con su dirección.",
            "destino"    => "Líneas (cruces)",
            "href"       => "?page=lineas",
            "match"      => "auto",
        ],
        "caminos" => [
            "termino"    => "Caminos",
            "significado" => "Los caminos de Mordor: en la app son las rutas que reconstruyen el recorrido de una persona entre cámaras (entrada → salida).",
            "destino"    => "Rutas",
            "href"       => "?page=rutas",
            "match"      => "auto",
        ],
        "la-forja" => [
            "termino"    => "La Forja",
            "significado" => "Donde se forjaron los Anillos: en la app es la configuración (cámaras, plano, líneas, nodos y parámetros). Cambia con cuidado: afecta a todo el reino.",
            "destino"    => "Configuración",
            "href"       => "?page=config",
            "match"      => "auto",
        ],
        "ojo-en-vivo" => [
            "termino"    => "El Ojo en Vivo",
            "significado" => "El Ojo vigilando ahora mismo: en la app son las cámaras con su stream en tiempo real y su último snapshot.",
            "destino"    => "Cámaras",
            "href"       => "?page=camaras",
            "match"      => "auto",
        ],
        "fichajes" => [
            "termino"    => "Fichajes",
            "significado" => "Control horario de los trabajadores: entrada (primera captura por cámara de puerta) y salida (última por cámara de salida) de cada día.",
            "destino"    => "Fichajes",
            "href"       => "?page=fichajes",
            "match"      => "auto",
        ],
        "el-concilio" => [
            "termino"    => "El Concilio",
            "significado" => "El Concilio Blanco, donde se decide: en la app es la ayuda, con la guía del panel y las preguntas frecuentes.",
            "destino"    => "Ayuda",
            "href"       => "?page=ayuda",
            "match"      => "auto",
        ],

        /* ---------------- Dashboard (La Torre) ---------------- */
        "cronicas-guerra" => [
            "termino"    => "Crónicas de Guerra",
            "significado" => "El cuadro de indicadores (KPIs) del dashboard: aforo, visitas de hoy, media diaria y visitantes recurrentes.",
            "destino"    => "Dashboard · KPIs",
            "href"       => "?page=dash",
            "match"      => "auto",
        ],
        "reinvocar-datos" => [
            "termino"    => "Reinvocar Datos",
            "significado" => "Recargar los datos del dashboard para traer las últimas crónicas del reino (refresca la página).",
            "destino"    => "Dashboard · refrescar",
            "href"       => "?page=dash",
            "match"      => "auto",
        ],
        "almas-fortaleza" => [
            "termino"    => "Almas en la Fortaleza",
            "significado" => "Aforo actual: cuántas personas hay ahora mismo dentro del local. Se puede editar el máximo permitido.",
            "destino"    => "Dashboard · aforo",
            "href"       => "?page=dash",
            "match"      => "auto",
        ],
        "cruzaron-puerta" => [
            "termino"    => "Cruzaron la Puerta Negra",
            "significado" => "Visitas de hoy: cuántas personas distintas entraron por las cámaras de puerta en el día actual.",
            "destino"    => "Accesos de hoy",
            "href"       => "?page=accesos",
            "match"      => "auto",
        ],
        "huestes-dia" => [
            "termino"    => "Huestes al Día",
            "significado" => "Media diaria de visitas: el promedio de personas distintas que entran cada día.",
            "destino"    => "Dashboard · media",
            "href"       => "?page=dash",
            "match"      => "auto",
        ],
        "leales-mordor" => [
            "termino"    => "Leales a Mordor",
            "significado" => "Visitantes recurrentes: personas que repiten visita en más de un día distinto.",
            "destino"    => "Visitantes",
            "href"       => "?page=visitantes",
            "match"      => "auto",
        ],
        "mapa-asedio" => [
            "termino"    => "Mapa de Asedio",
            "significado" => "Gráfico de visitas que compara el periodo elegido (amanecer/luna/ciclo/era) con el anterior.",
            "destino"    => "Dashboard · gráfico",
            "href"       => "?page=dash",
            "match"      => "auto",
        ],
        "elegir-era" => [
            "termino"    => "Elegir era",
            "significado" => "Selector del periodo del gráfico del Mapa de Asedio.",
            "destino"    => "Dashboard · filtro",
            "href"       => "?page=dash",
            "match"      => "auto",
        ],
        "un-amanecer" => [
            "termino"    => "Un amanecer",
            "significado" => "Filtro del gráfico: hoy (periodo de un día).",
            "destino"    => "Dashboard · filtro día",
            "href"       => "?page=dash&filtro=dia",
            "match"      => "auto",
        ],
        "una-luna" => [
            "termino"    => "Una luna",
            "significado" => "Filtro del gráfico: esta semana (periodo de siete días).",
            "destino"    => "Dashboard · filtro semana",
            "href"       => "?page=dash&filtro=semana",
            "match"      => "auto",
        ],
        "un-ciclo" => [
            "termino"    => "Un ciclo",
            "significado" => "Filtro del gráfico: este mes.",
            "destino"    => "Dashboard · filtro mes",
            "href"       => "?page=dash&filtro=mes",
            "match"      => "auto",
        ],
        "una-era" => [
            "termino"    => "Una era",
            "significado" => "Filtro del gráfico: este año.",
            "destino"    => "Dashboard · filtro año",
            "href"       => "?page=dash&filtro=anyo",
            "match"      => "auto",
        ],

        /* ---------------- Notificaciones (Señales de Guerra) ---------------- */
        "senal-guerra" => [
            "termino"    => "Señales de Guerra",
            "significado" => "Las notificaciones: avisos de movimientos de puerta y salida (quién entró/salió y cuándo).",
            "destino"    => "Notificaciones",
            "href"       => null,
            "match"      => "auto",
        ],
        "ninguna-senal" => [
            "termino"    => "Ninguna señal de guerra",
            "significado" => "No hay notificaciones pendientes: las puertas están en calma.",
            "destino"    => "Notificaciones (vacío)",
            "href"       => null,
            "match"      => "auto",
        ],

        /* ---------------- La Forja (Config) ---------------- */
        "puerta-camara" => [
            "termino"    => "Puerta",
            "significado" => "Cámara de entrada: marca el instante en que alguien cruza hacia dentro (genera el 'acceso' de entrada y los fichajes).",
            "destino"    => "Config · tipo de cámara",
            "href"       => "?page=config",
            "match"      => "explicito",
        ],
        "salida-camara" => [
            "termino"    => "Salida",
            "significado" => "Cámara de salida: marca el instante en que alguien cruza hacia fuera (genera el acceso de salida y cierra los fichajes del día).",
            "destino"    => "Config · tipo de cámara",
            "href"       => "?page=config",
            "match"      => "explicito",
        ],
        "encendida" => [
            "termino"    => "Encendida",
            "significado" => "Cámara activa: está capturando y analizando vídeo. Apagada, el Ojo no vigila por esa cámara.",
            "destino"    => "Config · estado de cámara",
            "href"       => "?page=config",
            "match"      => "explicito",
        ],

        /* ---------------- El Concilio (Ayuda) ---------------- */
        "guia-reino" => [
            "termino"    => "Guía del Reino",
            "significado" => "Resumen de qué se hace en cada sección del panel (la Torre, Fortalezas, Pueblos, Movimientos…).",
            "destino"    => "Ayuda",
            "href"       => "?page=ayuda",
            "match"      => "auto",
        ],
        "preguntas-frecuentes" => [
            "termino"    => "Preguntas Frecuentes",
            "significado" => "FAQ: dudas habituales sobre cámaras, registro de visitantes, movimientos, aforo, plano y rutas.",
            "destino"    => "Ayuda · FAQ",
            "href"       => "?page=ayuda",
            "match"      => "auto",
        ],
        "ultimo-recurso" => [
            "termino"    => "Último Recurso",
            "significado" => "Contacto con el administrador: incluye los datos de sesión (fortaleza, URL, fecha) para diagnosticar el problema.",
            "destino"    => "Ayuda · contacto",
            "href"       => "?page=ayuda",
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
