<?php

/*
 * terminos.php — Terminología del panel por tema.
 *
 * El panel tiene dos temas:
 *   - "mordor"     : jerga temática de El Señor de los Anillos (actual).
 *   - "pro"        : vocabulario profesional (por defecto).
 *
 * FUENTE ÚNICA DE VERDAD del texto visible dependiente del tema.
 *
 * Uso en vistas:
 *   <?= rf_term_html("nav-torre") ?>      -> <span class="rf-term" data-mordor=… data-pro=…>texto actual</span>
 *   <?= rf_term("buscar-ph") ?>          -> texto plano (para atributos: placeholder, aria-label, title…)
 *
 * El span lleva AMBOS textos en data-* y admin/files/terminos.js intercambia
 * el texto en caliente al cambiar de tema (sin recargar). El texto inicial lo
 * pinta el servidor según la cookie rf_theme (por defecto: pro).
 *
 * Reglas:
 *  - Las claves son slugs estables (kebab-case). No cambiarlas: el HTML y
 *    terminos.js las referencian.
 *  - Si un término no se traduce (mismo texto en ambos temas) no se registra:
 *    se deja el texto literal en la vista.
 */

/** Tema activo según la cookie (por defecto: profesional). */
function rf_tema_activo() {
    return (($_COOKIE["rf_theme"] ?? "") === "mordor") ? "mordor" : "pro";
}

/** Mapa clave => ["mordor" => texto, "pro" => texto]. */
function rf_terminos() {
    return [

        /* ---------------- Marca / topbar ---------------- */
        "marca"        => ["mordor" => "Barad-dûr", "pro" => "Panel de Vigilancia"],
        "marca-sub"    => ["mordor" => "El Ojo que Todo lo Ve", "pro" => "Reconocimiento facial · Control de accesos"],
        "buscar"       => ["mordor" => "Buscar en Mordor", "pro" => "Buscar en el panel"],
        "buscar-ph"    => ["mordor" => "Buscar en Mordor…", "pro" => "Buscar en el panel…"],
        "abandonar"    => ["mordor" => "Abandonar Mordor 🚪", "pro" => "Cerrar sesión 🚪"],

        /* ---------------- Menú superior / drawer ---------------- */
        "nav-torre"      => ["mordor" => "La Torre", "pro" => "Panel"],
        "nav-camaras"    => ["mordor" => "El Ojo en Vivo", "pro" => "Cámaras en directo"],
        "nav-config"     => ["mordor" => "La Forja", "pro" => "Configuración"],
        "nav-alarmas"    => ["mordor" => "La Almenara", "pro" => "Alarmas"],
        "nav-accesos"    => ["mordor" => "Movimientos", "pro" => "Accesos"],
        "nav-visitantes" => ["mordor" => "Pueblos", "pro" => "Visitantes"],
        "nav-rutas"      => ["mordor" => "Caminos", "pro" => "Rutas"],
        "nav-lineas"     => ["mordor" => "Líneas", "pro" => "Líneas"],
        "nav-ayuda"      => ["mordor" => "El Concilio", "pro" => "Ayuda"],

        /* ---------------- Centro de mando (hub) ---------------- */
        "anillo"          => ["mordor" => "Un Anillo", "pro" => "Centro de mando"],
        "anillo-titulo"   => ["mordor" => "Un Anillo para gobernarlos", "pro" => "Centro de mando"],
        "anillo-aria"     => ["mordor" => "Un Anillo para gobernarlos a todos — abre el centro de mando",
                              "pro"    => "Abre el centro de mando del panel"],
        "centinelas"      => ["mordor" => "Los Seis Centinelas", "pro" => "Servicios del sistema"],
        "power-on"        => ["mordor" => "Encender el Ojo", "pro" => "Iniciar el sistema"],
        "power-off"       => ["mordor" => "Apagar el Ojo", "pro" => "Detener el sistema"],
        "vigila"          => ["mordor" => "El Ojo vigila", "pro" => "Sistema en línea"],
        "revisando"       => ["mordor" => "Revisando los centinelas…", "pro" => "Comprobando servicios…"],

        /* ---------------- Notificaciones / cuenta ---------------- */
        "senales"     => ["mordor" => "Señales de Guerra", "pro" => "Notificaciones"],
        "sin-senales" => ["mordor" => "Ninguna señal de guerra", "pro" => "Sin notificaciones"],
        "senales-sub" => ["mordor" => "Los movimientos de puerta y salida aparecerán aquí",
                          "pro"    => "Los accesos de entrada y salida aparecerán aquí"],

        /* ---------------- Banner de alarma ---------------- */
        "banner-cta"   => ["mordor" => "Ir a La Almenara →", "pro" => "Ir a Alarmas →"],
        "banner-alerta"=> ["mordor" => "Alarma sin revisar", "pro" => "Alarma sin revisar"],

        /* ---------------- Dashboard ---------------- */
        "dash-guia"       => ["mordor" => "El Camino del Mensajero", "pro" => "Accesos rápidos"],
        "dash-vanguardia" => ["mordor" => "La Vanguardia", "pro" => "Métricas principales"],
        "dash-alcance"    => ["mordor" => "El Alcance del Ojo", "pro" => "Detalle de actividad"],
        "dash-concilio"   => ["mordor" => "El Concilio de los Fieles", "pro" => "Visitantes destacados"],
        "dash-centinelas" => ["mordor" => "Los Seis Centinelas", "pro" => "Servicios del sistema"],
        "dash-torre"      => ["mordor" => "La Torre", "pro" => "Panel"],
        "dash-aforo"      => ["mordor" => "Almas en la Fortaleza", "pro" => "Aforo actual"],
        "dash-caldero"    => ["mordor" => "Caldero de aforo", "pro" => "Indicador de aforo"],

        /* ---------------- Secciones ---------------- */
        "forja"        => ["mordor" => "La Forja", "pro" => "Configuración"],
        "fortalezas"   => ["mordor" => "Fortalezas", "pro" => "Locales"],
        "yunque"       => ["mordor" => "El Yunque — Plano del local", "pro" => "Plano del local"],
        "almenara"     => ["mordor" => "La Almenara", "pro" => "Alarmas"],
        "movimientos"  => ["mordor" => "Listado Movimientos", "pro" => "Listado de accesos"],
        "caminos"      => ["mordor" => "Caminos", "pro" => "Rutas"],
        "concilio"     => ["mordor" => "El Concilio · Ayuda", "pro" => "Ayuda"],
        "ir-torre"     => ["mordor" => "👁️ Ir a La Torre", "pro" => "Ir al Panel"],

        /* ---------------- Dashboard · hero ---------------- */
        "dash-reinvocar"       => ["mordor" => "Reinvocar Datos", "pro" => "Actualizar datos"],
        "dash-estado-sistema"  => ["mordor" => "Estado de Mordor", "pro" => "Estado del sistema"],
        "hero-ojo-vigila"      => ["mordor" => "EL OJO VIGILA", "pro" => "VIGILANCIA ACTIVA"],
        "dash-almas-dentro"    => ["mordor" => "almas dentro", "pro" => "personas dentro"],
        "dash-camaras-en-pie"  => ["mordor" => "cámaras en pie", "pro" => "cámaras activas"],
        "dash-anomalias"       => ["mordor" => "anomalías", "pro" => "incidencias"],
        "dash-videos-hoy"      => ["mordor" => "vídeos hoy", "pro" => "vídeos de hoy"],
        "dash-cruzaron-puerta" => ["mordor" => "Cruzaron la Puerta Negra", "pro" => "Entradas registradas"],
        "dash-almas-ahora"     => ["mordor" => "Almas dentro ahora", "pro" => "Personas dentro ahora"],
        "de-fortaleza"         => ["mordor" => "de la fortaleza", "pro" => "del aforo"],
        "dash-legion-formacion"=> ["mordor" => "Legión en formación", "pro" => "Trabajadores presentes"],
        "dash-camaras-ciegas"  => ["mordor" => "Cámaras ciegas", "pro" => "Cámaras apagadas"],
        "dash-desplegadas"     => ["mordor" => "desplegadas", "pro" => "instaladas"],
        "dash-hora-asedio"     => ["mordor" => "Hora del asedio", "pro" => "Hora punta"],
        "dash-pergaminos-ojo"  => ["mordor" => "Pergaminos del Ojo", "pro" => "Vídeos grabados"],
        "dash-gb-forja"        => ["mordor" => "GB en la Forja", "pro" => "GB almacenados"],
        "dash-vigia-incansable"=> ["mordor" => "El vigía incansable", "pro" => "Cámara más activa"],
        "dash-senales-alarma"  => ["mordor" => "Señales de alarma", "pro" => "Alertas"],

        /* ---------------- Dashboard · gráficos ---------------- */
        "dash-mapa-asedio"      => ["mordor" => "Mapa de Asedio", "pro" => "Mapa de actividad"],
        "dash-elegir-era"       => ["mordor" => "Elegir era", "pro" => "Elegir periodo"],
        "era-dia"               => ["mordor" => "Un amanecer", "pro" => "Un día"],
        "era-semana"            => ["mordor" => "Una luna", "pro" => "Una semana"],
        "era-mes"               => ["mordor" => "Un ciclo", "pro" => "Un mes"],
        "era-anyo"              => ["mordor" => "Una era", "pro" => "Un año"],
        "dash-puerta-vs-camaras"=> ["mordor" => "La Puerta vs Las Cámaras", "pro" => "Entradas vs cámaras"],
        "dash-fraguas-hora"     => ["mordor" => "Las Fraguas por Hora", "pro" => "Actividad por hora"],

        /* ---------------- Dashboard · alcance ---------------- */
        "dash-cronica-ojo"        => ["mordor" => "Crónica del Ojo en Vivo", "pro" => "Actividad en directo"],
        "dash-almas-fortaleza"    => ["mordor" => "almas en la fortaleza", "pro" => "personas en el local"],
        "dash-trabajadores-camino"=> ["mordor" => "trabajadores aún en camino", "pro" => "trabajadores pendientes"],
        "dash-ver-todos-movimientos" => ["mordor" => "Ver todos los Movimientos", "pro" => "Ver todos los accesos"],
        "dash-glorias-mes"        => ["mordor" => "rankings y glorias del mes", "pro" => "rankings y destacados del mes"],
        "dash-mas-leales"         => ["mordor" => "Los más leales · 30 días", "pro" => "Visitantes más frecuentes · 30 días"],
        "dash-sin-subditos"       => ["mordor" => "Aún no hay súbditos este mes. 🕸️", "pro" => "Aún no hay visitantes este mes. 🕸️"],
        "dash-glorias-reino"      => ["mordor" => "Glorias del Reino", "pro" => "Destacados del mes"],
        "dash-alma-madrugadora"   => ["mordor" => "Alma madrugadora de hoy", "pro" => "Primera entrada de hoy"],
        "dash-visitante-leal"     => ["mordor" => "El Visitante más Leal", "pro" => "Visitante más frecuente"],
        "dash-rachas-presencia"   => ["mordor" => "Rachas de presencia (14 días)", "pro" => "Días seguidos de presencia (14 días)"],

        /* ---------------- Dashboard · profecía ---------------- */
        "dash-profecia"        => ["mordor" => "Profecía de Afluencia", "pro" => "Previsión de afluencia"],
        "dash-profecia-detalle"=> ["mordor" => "real hoy (brasa) vs media de los mismos días de semana (oro) · últimos 28 días",
                                   "pro"    => "actividad real de hoy vs media de los mismos días de la semana · últimos 28 días"],
        "dash-asedio-previsto" => ["mordor" => "asedio previsto", "pro" => "pico previsto"],
        "augur-sin-historia"   => ["mordor" => "🜂 El fuego aún no habla; regresa cuando haya historia que leer.",
                                   "pro"    => "🜂 Aún no hay datos suficientes para la previsión."],
        "augur-crece-pre"      => ["mordor" => "🜂 El fuego crece con fuerza: hoy llega más gente de lo habitual (",
                                   "pro"    => "🜂 La afluencia supera lo previsto en "],
        "augur-crece-post"     => ["mordor" => " almas por encima de lo esperado). ¡Preparad la puerta!",
                                   "pro"    => " personas. Conviene reforzar la entrada."],
        "augur-titubea-pre"    => ["mordor" => "🜂 El fuego titubea: hoy hay ",
                                   "pro"    => "🜂 La afluencia es inferior a lo previsto en "],
        "augur-titubea-post"   => ["mordor" => " almas por debajo de lo esperado. Mordor descansa.",
                                   "pro"    => " personas. Jornada tranquila."],
        "augur-encaja"         => ["mordor" => "🜂 El fuego respira tranquilo: la afluencia sigue la profecía al pie de la letra.",
                                   "pro"    => "🜂 La afluencia se ajusta a la previsión."],

        /* ---------------- Dashboard · widgets (AJAX) ---------------- */
        "feed-vacio"            => ["mordor" => "Silencio en Mordor", "pro" => "Sin actividad reciente"],
        "feed-vacio-hint"       => ["mordor" => "Aún no hay movimientos registrados. El Ojo sigue vigilando.",
                                    "pro"    => "Aún no hay movimientos registrados."],
        "dentro-vacio"          => ["mordor" => "La fortaleza está vacía", "pro" => "No hay nadie dentro"],
        "dentro-vacio-hint"     => ["mordor" => "Nadie dentro ahora mismo. El Ojo descansa tranquilo.",
                                    "pro"    => "Nadie dentro ahora mismo."],
        "falta-sin-legion"      => ["mordor" => "La legión aún no está registrada", "pro" => "Aún no hay trabajadores registrados"],
        "falta-sin-legion-hint" => ["mordor" => 'Marca trabajadores en "Pueblos" (👹) para que el conciliador genere sus fichajes.',
                                    "pro"    => "Marca trabajadores en Visitantes (👹) para que el sistema genere sus fichajes."],
        "falta-guardia-completa"=> ["mordor" => "La guardia está completa", "pro" => "Todo el personal ha fichado"],
        "falta-guardia-hint"    => ["mordor" => "Todos los trabajadores han cruzado la puerta hoy.",
                                    "pro"    => "Todos los trabajadores han registrado su entrada hoy."],
        "fichajes-vacio-hint"   => ["mordor" => "El Conciliador los genera cuando los trabajadores cruzan la puerta. Si nadie ha llegado, el reloj sigue en silencio.",
                                    "pro"    => "El sistema los genera cuando los trabajadores registran su entrada. Si nadie ha llegado, no hay fichajes."],
        "tag-acceso"            => ["mordor" => "Movimiento", "pro" => "Acceso"],

        /* ---------------- Centinelas / daemons ---------------- */
        "daemon-vigia"       => ["mordor" => "El Vigía", "pro" => "Capturador"],
        "daemon-rastreador"  => ["mordor" => "El Rastreador", "pro" => "Detector"],
        "daemon-mirada"      => ["mordor" => "La Mirada", "pro" => "Clasificador"],
        "daemon-atador"      => ["mordor" => "El Atador", "pro" => "Vinculador"],
        "daemon-conciliador" => ["mordor" => "El Conciliador", "pro" => "Conciliador"],
        "daemon-mensajero"   => ["mordor" => "El Mensajero", "pro" => "Mensajero en vivo"],
        "estado-en-pie"      => ["mordor" => "en pie", "pro" => "activo"],
        "estado-caido"       => ["mordor" => "caído", "pro" => "detenido"],
        "estado-dormido"     => ["mordor" => "dormido", "pro" => "inactivo"],
        "estado-desconocido" => ["mordor" => "desconocido", "pro" => "sin datos"],

        /* ---------------- Aforo ---------------- */
        "aforo-full"       => ["mordor" => "Asedio", "pro" => "Saturación"],
        "aforo-warn"       => ["mordor" => "Animado", "pro" => "Alta ocupación"],
        "aforo-ok"         => ["mordor" => "Tranquilo", "pro" => "Normal"],
        "aforo-nuevo-aria" => ["mordor" => "Nuevo aforo actual de la fortaleza", "pro" => "Nuevo aforo actual del local"],

        /* ---------------- Sustantivos temáticos ---------------- */
        "almas"            => ["mordor" => "almas", "pro" => "personas"],
        "fortaleza"        => ["mordor" => "fortaleza", "pro" => "local"],
        "reino"            => ["mordor" => "reino", "pro" => "recinto"],
        "legion"           => ["mordor" => "legión", "pro" => "plantilla"],
        "centinela"        => ["mordor" => "centinela", "pro" => "sistema"],
        "conciliador"      => ["mordor" => "el conciliador", "pro" => "el sistema"],
        "vinculador"       => ["mordor" => "el vinculador", "pro" => "el sistema de vinculación"],
        "sendero"          => ["mordor" => "sendero", "pro" => "trayecto"],
        "senderos"         => ["mordor" => "Senderos", "pro" => "Trayectos"],
        "modo-senderos"    => ["mordor" => "Modo senderos", "pro" => "Modo trayectos"],
        "modo-senderos-lc" => ["mordor" => "modo senderos", "pro" => "modo trayectos"],
        "fortaleza-label"  => ["mordor" => "Fortaleza:", "pro" => "Local:"],
        "el-yunque-corto"  => ["mordor" => "El Yunque", "pro" => "Plano"],

        /* ---------------- La Forja · pestañas / acciones ---------------- */
        "config-tab-forjar"  => ["mordor" => "Forjar", "pro" => "Gestión"],
        "config-tab-trazos"  => ["mordor" => "Trazos", "pro" => "Trazado"],
        "config-tab-plano"   => ["mordor" => "El Yunque", "pro" => "Disposición"],
        "config-tab-locales" => ["mordor" => "Fortalezas", "pro" => "Gestión"],
        "forjar"             => ["mordor" => "Forjar", "pro" => "Crear"],
        "templar"            => ["mordor" => "Templar", "pro" => "Calibrar"],
        "ritual"             => ["mordor" => "ritual", "pro" => "prueba"],
        "el-ritual"          => ["mordor" => "el ritual", "pro" => "la prueba"],
        "del-ritual"         => ["mordor" => "del ritual", "pro" => "de la prueba"],
        "rituales"           => ["mordor" => "Rituales", "pro" => "Pruebas"],
        "rituales-lc"        => ["mordor" => "rituales", "pro" => "pruebas"],
        "de-los-rituales"    => ["mordor" => "de los rituales", "pro" => "de las pruebas"],
        "estado-iniciando-ritual"  => ["mordor" => "Iniciando ritual ", "pro" => "Iniciando prueba "],
        "estado-ritual-curso"      => ["mordor" => "Ritual en curso… (", "pro" => "Prueba en curso… ("],
        "estado-error-red-ritual"  => ["mordor" => "Error de red al iniciar el ritual.", "pro" => "Error de red al iniciar la prueba."],
        "estado-ritual-error"      => ["mordor" => "El ritual terminó con error: ", "pro" => "La prueba terminó con error: "],
        "estado-ritual-completado-pre"  => ["mordor" => "Ritual ", "pro" => "Prueba "],
        "estado-ritual-completado-post" => ["mordor" => " completado en ", "pro" => " completada en "],
        "duracion-ritual"    => ["mordor" => "Duración del ritual (s)", "pro" => "Duración de la prueba (s)"],
        "elige-ritual"       => ["mordor" => "Elige un ritual y pulsa «Iniciar».", "pro" => "Elige una prueba y pulsa «Iniciar»."],
        "iniciar-ritual"     => ["mordor" => "Iniciar ritual", "pro" => "Iniciar prueba"],
        "ritual-e"           => ["mordor" => "El ritual E (identidad)", "pro" => "La prueba E (identidad)"],
        "ritual-alcance"     => ["mordor" => "Alcance", "pro" => "Distancia"],
        "ritual-enfoque"     => ["mordor" => "Enfoque", "pro" => "Nitidez"],

        /* ---------------- La Almenara ---------------- */
        "asedios"         => ["mordor" => "Asedios", "pro" => "Críticas"],
        "alarma-asedio"   => ["mordor" => "ASEDIO", "pro" => "CRÍTICA"],
        "volver-almenara" => ["mordor" => "Volver a La Almenara", "pro" => "Volver a Alarmas"],

        /* ---------------- Fortalezas (Config) ---------------- */
        "nueva-fortaleza"        => ["mordor" => "Nueva fortaleza", "pro" => "Nuevo local"],
        "editar-fortaleza"       => ["mordor" => "Editar fortaleza: ", "pro" => "Editar local: "],
        "fortaleza-no-encontrada"=> ["mordor" => "Fortaleza no encontrada", "pro" => "Local no encontrado"],
        "guardar-fortaleza"      => ["mordor" => "Guardar fortaleza", "pro" => "Guardar local"],

        /* ---------------- Ayuda ---------------- */
        "ayuda-guia-reino"    => ["mordor" => "Guía del Reino", "pro" => "Guía de uso"],
        "ayuda-ultimo-recurso"=> ["mordor" => "Último Recurso", "pro" => "Soporte"],
        "ayuda-torre"         => ["mordor" => "La Torre · Dashboard", "pro" => "Dashboard"],
        "ayuda-locales"       => ["mordor" => "Fortalezas · Locales", "pro" => "Locales"],
        "ayuda-visitantes"    => ["mordor" => "Pueblos · Visitantes", "pro" => "Visitantes"],
        "ayuda-accesos"       => ["mordor" => "Movimientos · Accesos", "pro" => "Accesos"],
        "ayuda-rutas"         => ["mordor" => "Caminos · Rutas", "pro" => "Rutas"],
        "ayuda-config"        => ["mordor" => "La Forja · Configuración", "pro" => "Configuración"],
        "ayuda-camaras"       => ["mordor" => "El Ojo en Vivo · Cámaras", "pro" => "Cámaras"],
        "avatar-monigote"     => ["mordor" => "Avatar del monigote (Caminos)", "pro" => "Avatar para rutas"],
        "camino-persona"      => ["mordor" => "Camino de la persona", "pro" => "Recorrido de la persona"],
        "ver-camino"          => ["mordor" => "▶ Ver camino", "pro" => "▶ Ver recorrido"],
        "camino-prefix"       => ["mordor" => "Camino · ", "pro" => "Recorrido · "],
        "camino-error"        => ["mordor" => "No se pudo cargar el camino: ", "pro" => "No se pudo cargar el recorrido: "],
        "sendero-creado"      => ["mordor" => "Sendero creado.", "pro" => "Trayecto creado."],
        "sendero-eliminar"    => ["mordor" => "¿Eliminar este sendero?", "pro" => "¿Eliminar este trayecto?"],
        "sendero-no-guardar"  => ["mordor" => "No se pudo guardar el sendero.", "pro" => "No se pudo guardar el trayecto."],
        "sendero-no-actualizar" => ["mordor" => "No se pudo actualizar el sendero.", "pro" => "No se pudo actualizar el trayecto."],
        "sendero-no-eliminar" => ["mordor" => "No se pudo eliminar el sendero.", "pro" => "No se pudo eliminar el trayecto."],
        "elige-ritual-js"     => ["mordor" => "Elige un ritual (A · Alcance … F · Enfoque).", "pro" => "Elige una prueba (A · Distancia … F · Nitidez)."],

        /* ---------------- AJAX / DataTables (texto plano) ---------------- */
        "camaras-apagadas"  => ["mordor" => "cámara(s) apagada(s)", "pro" => "cámaras apagadas"],
        "centinelas-caidos" => ["mordor" => "centinela(s) caído(s)", "pro" => "servicios detenidos"],

        /* ---------------- Login ---------------- */
        "login-titulo"   => ["mordor" => "👁️ La Puerta Negra", "pro" => "Iniciar sesión"],
        "login-sub"      => ["mordor" => "El Ojo vigila a quien osa cruzar. Identifícate, o la torre te rechazará.",
                             "pro"    => "Accede con tus credenciales para entrar al panel."],
        "login-entrar"   => ["mordor" => "🔥 Entrar a Mordor", "pro" => "Entrar"],
        "login-espera"   => ["mordor" => "El Ojo te observa…", "pro" => "Comprobando credenciales…"],
        "login-error"    => ["mordor" => "La Puerta Negra te ha rechazado. Usuario o contraseña incorrectos.",
                             "pro"    => "Usuario o contraseña incorrectos."],
        "login-marca"    => ["mordor" => "Mordor", "pro" => "Panel de Vigilancia"],
        "login-tagline1" => ["mordor" => "“Ash nazg durbatulûk, ash nazg gimbatul, ash nazg thrakatulûk agh burzum-ishi krimpatul.”",
                             "pro"    => "Vigilancia y control de accesos por reconocimiento facial."],
        "login-tagline2" => ["mordor" => "Un Anillo para gobernarlos a todos… y El Ojo que todo lo ve vigila cada acceso por reconocimiento facial.",
                             "pro"    => "Identifica a cada persona que entra y sale de tus instalaciones, en tiempo real."],
    ];
}

/** Texto plano para el tema activo (o el indicado). Para atributos HTML. */
function rf_term($clave, $tema = null) {
    $mapa = rf_terminos();
    if (!isset($mapa[$clave])) { return $clave; }
    if ($tema === null) { $tema = rf_tema_activo(); }
    $e = $mapa[$clave];
    if ($tema === "mordor") { return $e["mordor"] ?? ($e["pro"] ?? $clave); }
    return $e["pro"] ?? ($e["mordor"] ?? $clave);
}

/** Span con ambos textos (data-mordor / data-pro) y el activo ya pintado. */
function rf_term_html($clave) {
    $mapa = rf_terminos();
    if (!isset($mapa[$clave])) {
        return htmlspecialchars($clave, ENT_QUOTES);
    }
    $e  = $mapa[$clave];
    $md = $e["mordor"] ?? "";
    $pr = $e["pro"] ?? $md;
    $tema = rf_tema_activo();
    $txt  = ($tema === "mordor") ? $md : $pr;
    return '<span class="rf-term" data-mordor="' . htmlspecialchars($md, ENT_QUOTES) . '"'
         . ' data-pro="' . htmlspecialchars($pr, ENT_QUOTES) . '">'
         . htmlspecialchars($txt, ENT_QUOTES) . '</span>';
}

/** Mapa serializado a JSON para el intercambio en caliente (terminos.js). */
function rf_terminos_json() {
    return json_encode(rf_terminos(), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
}
