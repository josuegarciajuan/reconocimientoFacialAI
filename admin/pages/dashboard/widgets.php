<?php

/*
 * Dashboard — widgets (2026-08-19).
 * Funciones compartidas de datos y render para el nuevo dashboard "La Torre".
 * Se usan tanto desde pages/dashboard/list.php (render server-side) como desde
 * admin/accionesAjax.php (a=4 feed en vivo, a=5 daemons, a=6 aforo) para que
 * el refresco AJAX pinte EXACTAMENTE el mismo markup que la carga inicial.
 *
 * Todas las funciones reciben $local_id explícito (nunca dependen de sesión).
 */

require_once __DIR__ . "/../../../libs/db.php";

/* ---------------------------------------------------------------
 * Utilidades
 * ------------------------------------------------------------- */

/** Escapado para atributos onclick (patrón ui-common: verFoto('url','titulo')). */
function dash_js_quote($s) {
    return htmlspecialchars(str_replace(["\\", "'"], ["\\\\", "\\'"], (string)$s), ENT_QUOTES);
}

/** Tiempo relativo en castellano ("hace 3 min") o fecha corta si es antiguo. */
function dash_tiempo_relativo($fecha) {
    $ts = strtotime($fecha);
    if ($ts === false) { return ""; }
    $d = time() - $ts;
    if ($d < 60)  { return "hace " . max(1, $d) . " s"; }
    if ($d < 3600){ return "hace " . floor($d / 60) . " min"; }
    if ($d < 86400){ return "hace " . floor($d / 3600) . " h"; }
    return date("d/m H:i", $ts);
}

/** Primera foto (caras_procesadas/<fid>.jpg) de una persona, o 0. */
function dash_foto_persona($persona_id) {
    $f = DB::selectOne(
        "SELECT MIN(f.id) AS fid FROM fotos f JOIN estancias e ON e.id = f.estancia_id WHERE e.persona_id = ?",
        [(int)$persona_id]
    );
    return $f && $f["fid"] ? (int)$f["fid"] : 0;
}

/** Fotos (MIN id) de varias personas en una sola consulta. */
function dash_fotos_personas(array $persona_ids) {
    $ids = array_values(array_unique(array_filter(array_map("intval", $persona_ids))));
    if (!$ids) { return []; }
    $in = implode(",", array_fill(0, count($ids), "?"));
    $rows = DB::select(
        "SELECT e.persona_id AS pid, MIN(f.id) AS fid
         FROM fotos f JOIN estancias e ON e.id = f.estancia_id
         WHERE e.persona_id IN ($in)
         GROUP BY e.persona_id",
        $ids
    );
    $map = [];
    foreach ($rows as $r) { $map[(int)$r["pid"]] = (int)$r["fid"]; }
    return $map;
}

/* ---------------------------------------------------------------
 * Datos agregados
 * ------------------------------------------------------------- */

/** Personas distintas que pasaron por cámara puerta (entrada) o salida en el rango. */
function dash_movimientos_periodo($local_id, $desde, $hasta, $tipo) {
    $flag = $tipo === "salida" ? "c.salida = 1" : "c.puerta = 1";
    $r = DB::selectOne(
        "SELECT COUNT(DISTINCT e.persona_id) AS cuenta
         FROM estancias e
         JOIN camaras c ON c.id = e.camara_id
         JOIN personas p ON p.id = e.persona_id
         WHERE $flag AND c.local_id = ? AND e.created >= ? AND e.created <= ?",
        [$local_id, $desde, $hasta]
    );
    return $r ? (int)$r["cuenta"] : 0;
}

/** Aforo del local: actual, máximo, % y semáforo (ok <60, warn 60-85, full >85). */
function dash_aforo($local_id) {
    $loc = DB::selectOne("SELECT nombre, url_logo, aforo_max, aforo_actual FROM locales WHERE id = ?", [(int)$local_id]);
    $max    = (int)($loc["aforo_max"] ?? 0);
    $actual = (int)($loc["aforo_actual"] ?? 0);
    $pct    = $max > 0 ? round($actual / $max * 100) : 0;
    $estado = $pct >= 85 ? "full" : ($pct >= 60 ? "warn" : "ok");
    return [
        "nombre" => (string)($loc["nombre"] ?? ""),
        "logo"   => (string)($loc["url_logo"] ?? ""),
        "max"    => $max,
        "actual" => $actual,
        "pct"    => $pct,
        "estado" => $estado,
    ];
}

/**
 * Personas que están DENTRO ahora mismo: su último cruce de puerta (entrada)
 * es más reciente que su último cruce de salida (o nunca salieron).
 */
function dash_almas_dentro($local_id) {
    $rows = DB::select(
        "SELECT p.id, p.cod_interno, p.nombre, MAX(e.fecha_ini) AS ultimo,
                MAX(CASE WHEN c.puerta = 1 THEN e.fecha_ini END) AS ult_entrada
         FROM personas p
         JOIN estancias e ON e.persona_id = p.id
         JOIN camaras c ON c.id = e.camara_id
         WHERE c.local_id = ? AND (c.puerta = 1 OR c.salida = 1)
         GROUP BY p.id
         HAVING MAX(CASE WHEN c.puerta = 1 THEN e.fecha_ini END)
              > COALESCE(MAX(CASE WHEN c.salida = 1 THEN e.fecha_ini END), '1970-01-01 00:00:00')
         ORDER BY ultimo DESC",
        [(int)$local_id]
    );
    $map = dash_fotos_personas(array_column($rows, "id"));
    foreach ($rows as &$r) { $r["foto_id"] = $map[(int)$r["id"]] ?? 0; }
    return $rows;
}

/** Trabajadores del local que aún no tienen fichaje hoy (ordenados por horario esperado). */
function dash_falta_fichar($local_id) {
    $rows = DB::select(
        "SELECT p.id, p.cod_interno, p.nombre
         FROM personas p
         WHERE p.trabajador = 1 AND p.local_id = ?
           AND p.id NOT IN (SELECT persona_id FROM fichajes WHERE local_id = ? AND fecha = CURDATE())
         ORDER BY p.nombre ASC, p.cod_interno ASC",
        [(int)$local_id, (int)$local_id]
    );
    $map = dash_fotos_personas(array_column($rows, "id"));
    foreach ($rows as &$r) { $r["foto_id"] = $map[(int)$r["id"]] ?? 0; }
    return $rows;
}

/** Top visitantes del último mes (por nº de estancias). */
function dash_ranking($local_id, $limite = 5) {
    $rows = DB::select(
        "SELECT e.persona_id AS pid, p.cod_interno, p.nombre, COUNT(*) AS n, MAX(e.fecha_ini) AS ultima
         FROM estancias e
         JOIN personas p ON p.id = e.persona_id
         JOIN camaras c ON c.id = e.camara_id
         WHERE c.local_id = ? AND e.fecha_ini >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
         GROUP BY e.persona_id
         ORDER BY n DESC, ultima DESC
         LIMIT " . (int)$limite,
        [(int)$local_id]
    );
    $map = dash_fotos_personas(array_column($rows, "pid"));
    foreach ($rows as &$r) { $r["foto_id"] = $map[(int)$r["pid"]] ?? 0; }
    return $rows;
}

/** Días distintos de presencia por persona (últimos 14 días) — para "rachas". */
function dash_rachas($local_id, $limite = 3) {
    return DB::select(
        "SELECT e.persona_id AS pid, p.cod_interno, p.nombre,
                COUNT(DISTINCT DATE(e.fecha_ini)) AS dias
         FROM estancias e
         JOIN personas p ON p.id = e.persona_id
         JOIN camaras c ON c.id = e.camara_id
         WHERE c.local_id = ? AND e.fecha_ini >= DATE_SUB(CURDATE(), INTERVAL 14 DAY)
         GROUP BY e.persona_id
         ORDER BY dias DESC, p.nombre ASC
         LIMIT " . (int)$limite,
        [(int)$local_id]
    );
}

/** Primera persona en cruzar hoy (el "alma madrugadora"). */
function dash_madrugadora($local_id) {
    $r = DB::selectOne(
        "SELECT p.cod_interno, p.nombre, MIN(e.fecha_ini) AS t
         FROM estancias e
         JOIN personas p ON p.id = e.persona_id
         JOIN camaras c ON c.id = e.camara_id
         WHERE c.local_id = ? AND DATE(e.fecha_ini) = CURDATE()
         GROUP BY e.persona_id
         ORDER BY t ASC LIMIT 1",
        [(int)$local_id]
    );
    return $r ? $r : null;
}

/** Hora de hoy con más actividad (el "pico del asedio"). */
function dash_pico_hoy($local_id) {
    $r = DB::selectOne(
        "SELECT HOUR(e.fecha_ini) AS h, COUNT(*) AS n
         FROM estancias e JOIN camaras c ON c.id = e.camara_id
         WHERE c.local_id = ? AND DATE(e.fecha_ini) = CURDATE()
         GROUP BY h ORDER BY n DESC, h ASC LIMIT 1",
        [(int)$local_id]
    );
    return $r ? $r : null;
}

/** Cámara más activa hoy (el "vigía incansable"). */
function dash_vigia($local_id) {
    $r = DB::selectOne(
        "SELECT c.descripcion, COUNT(*) AS n
         FROM estancias e JOIN camaras c ON c.id = e.camara_id
         WHERE c.local_id = ? AND DATE(e.fecha_ini) = CURDATE()
         GROUP BY e.camara_id ORDER BY n DESC LIMIT 1",
        [(int)$local_id]
    );
    return $r ? $r : null;
}

/** Matriz de calor 7×24 (días Lun..Dom × horas) de los últimos 7 días. */
function dash_heatmap($local_id, $dias = 7) {
    $rows = DB::select(
        "SELECT DAYOFWEEK(e.fecha_ini) AS dow, HOUR(e.fecha_ini) AS h, COUNT(*) AS n
         FROM estancias e JOIN camaras c ON c.id = e.camara_id
         WHERE c.local_id = ? AND e.fecha_ini >= DATE_SUB(CURDATE(), INTERVAL " . (int)$dias . " DAY)
         GROUP BY dow, h",
        [(int)$local_id]
    );
    $mat = array_fill(0, 7, array_fill(0, 24, 0));
    $max = 1;
    foreach ($rows as $r) {
        $dow = (int)$r["dow"];            // 1=Dom .. 7=Sáb
        $idx = ($dow + 5) % 7;            // -> 0=Lun .. 6=Dom
        $v = (int)$r["n"];
        $mat[$idx][(int)$r["h"]] = $v;
        $max = max($max, $v);
    }
    return [$mat, $max];
}

/**
 * Profecía de afluencia: serie real de hoy (por hora) vs esperada
 * (media del mismo día de semana de las últimas 4 semanas).
 */
function dash_profecia($local_id) {
    $hoy_dow = (int)date("w") + 1;        // DAYOFWEEK MySQL: hoy
    $rows = DB::select(
        "SELECT HOUR(e.fecha_ini) AS h, COUNT(DISTINCT e.persona_id) AS n
         FROM estancias e JOIN camaras c ON c.id = e.camara_id
         WHERE c.local_id = ? AND e.fecha_ini >= DATE_SUB(CURDATE(), INTERVAL 28 DAY)
           AND e.fecha_ini < CURDATE() AND DAYOFWEEK(e.fecha_ini) = ?
         GROUP BY h",
        [(int)$local_id, $hoy_dow]
    );
    $esperado = array_fill(0, 24, 0);
    foreach ($rows as $r) { $esperado[(int)$r["h"]] = round((int)$r["n"] / 4); }

    $rows2 = DB::select(
        "SELECT HOUR(e.fecha_ini) AS h, COUNT(DISTINCT e.persona_id) AS n
         FROM estancias e JOIN camaras c ON c.id = e.camara_id
         WHERE c.local_id = ? AND DATE(e.fecha_ini) = CURDATE()
         GROUP BY h",
        [(int)$local_id]
    );
    $real = array_fill(0, 24, 0);
    foreach ($rows2 as $r) { $real[(int)$r["h"]] = (int)$r["n"]; }

    $ahora = (int)date("G");
    $total_esperado = array_sum($esperado);
    $total_real = array_sum($real);
    $pico_h = 0; $pico_v = 0;
    foreach ($esperado as $h => $v) { if ($v > $pico_v) { $pico_v = $v; $pico_h = $h; } }
    return [
        "esperado" => $esperado, "real" => $real, "ahora" => $ahora,
        "total_esperado" => $total_esperado, "total_real" => $total_real,
        "pico_h" => $pico_h, "pico_v" => $pico_v,
    ];
}

/** Cámaras por actividad del mes (para el donut "La Puerta vs Las Cámaras"). */
function dash_camaras_actividad($local_id, $limite = 5) {
    $rows = DB::select(
        "SELECT c.id, c.descripcion, COUNT(*) AS n
         FROM estancias e JOIN camaras c ON c.id = e.camara_id
         WHERE c.local_id = ? AND e.fecha_ini >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
         GROUP BY c.id
         ORDER BY n DESC
         LIMIT " . (int)$limite,
        [(int)$local_id]
    );
    return $rows;
}

/* ---------------------------------------------------------------
 * Estado de los daemons (systemd)
 * ------------------------------------------------------------- */

/** Estado de un servicio systemd ("active", "inactive", "failed", "unknown"). */
function dash_daemon_estado($svc) {
    static $cache = [];
    if (isset($cache[$svc])) { return $cache[$svc]; }
    $out = "";
    if (function_exists("shell_exec")) {
        $out = @shell_exec("systemctl is-active " . escapeshellarg($svc) . " 2>&1");
    }
    $cache[$svc] = trim((string)$out);
    if ($cache[$svc] === "") { $cache[$svc] = "unknown"; }
    return $cache[$svc];
}

/** Lista de daemons con estado (los 6 centinelas). */
function dash_daemons() {
    $lista = [
        ["svc" => "rf-capturador",   "nombre" => "El Vigía",       "emoji" => "📡", "rol" => "Graba movimientos", "lore" => "el-vigia"],
        ["svc" => "rf-detector",     "nombre" => "El Rastreador",  "emoji" => "🐺", "rol" => "Cruces + caras",      "lore" => "el-rastreador"],
        ["svc" => "rf-clasificador", "nombre" => "La Mirada",      "emoji" => "👁️", "rol" => "Ingesta a la BD",    "lore" => "la-mirada"],
        ["svc" => "rf-vinculador",   "nombre" => "El Atador",      "emoji" => "⛓️", "rol" => "Vídeo ↔ personas",  "lore" => "el-atador"],
        ["svc" => "rf-conciliador",  "nombre" => "El Conciliador", "emoji" => "⚖️", "rol" => "Fichajes diarios",  "lore" => "el-conciliador"],
        ["svc" => "rf-live",         "nombre" => "El Mensajero",   "emoji" => "📯", "rol" => "Snapshots en vivo", "lore" => "el-mensajero"],
    ];
    foreach ($lista as &$d) {
        $st = dash_daemon_estado($d["svc"]);
        $d["estado"] = $st;
        if ($st === "active")       { $d["clase"] = "active"; $d["texto"] = "en pie"; }
        elseif ($st === "failed")   { $d["clase"] = "failed"; $d["texto"] = "caído"; }
        elseif ($st === "inactive") { $d["clase"] = "idle";   $d["texto"] = "dormido"; }
        else                        { $d["clase"] = "unknown"; $d["texto"] = "desconocido"; }
    }
    return $lista;
}

/* ---------------------------------------------------------------
 * Render de fragmentos (usados por list.php y por el AJAX)
 * ------------------------------------------------------------- */

/** Feed en vivo: últimos movimientos con miniatura de cara. */
function dash_feed_html($local_id, $limite = 10) {
    $rows = DB::select(
        "SELECT e.id, e.fecha_ini, e.persona_id, e.camara_id, c.descripcion AS cam, c.puerta, c.salida,
                p.cod_interno, p.nombre
         FROM estancias e
         JOIN camaras c ON c.id = e.camara_id
         JOIN personas p ON p.id = e.persona_id
         WHERE c.local_id = ?
         ORDER BY e.id DESC LIMIT " . (int)$limite,
        [(int)$local_id]
    );
    if (!$rows) {
        return '<div class="empty-state"><div class="empty-state__icon">🕸️</div>'
            . '<div class="empty-state__title">Silencio en Mordor</div>'
            . '<div class="empty-state__hint">Aún no hay movimientos registrados. El Ojo sigue vigilando.</div></div>';
    }
    $fids = DB::select(
        "SELECT estancia_id, MIN(id) AS fid FROM fotos WHERE estancia_id IN ("
        . implode(",", array_map("intval", array_column($rows, "id")))
        . ") GROUP BY estancia_id"
    );
    $foto_por_est = [];
    foreach ($fids as $f) { $foto_por_est[(int)$f["estancia_id"]] = (int)$f["fid"]; }

    $out = "";
    $i = 0;
    foreach ($rows as $r) {
        $nombre = $r["nombre"] !== "" ? $r["nombre"] : $r["cod_interno"];
        $fid = $foto_por_est[(int)$r["id"]] ?? 0;
        $img = "./caras_procesadas/" . $fid . ".jpg";
        if ((int)$r["puerta"] === 1)      { $tag = "entrada"; $tag_txt = "⚔️ Entrada"; }
        elseif ((int)$r["salida"] === 1)  { $tag = "salida";  $tag_txt = "🚪 Salida"; }
        else                              { $tag = "mov";     $tag_txt = "👣 Movimiento"; }
        $titulo = $nombre . " · " . $r["cam"];
        $out .= '<div class="feed-item" style="--i:' . $i . '">'
            . '<img class="feed-avatar" src="' . htmlspecialchars($img) . '" alt="Foto de ' . htmlspecialchars($nombre) . '" loading="lazy"'
            . ' onclick="verFoto(\'' . dash_js_quote($img) . '\',\'' . dash_js_quote($titulo) . '\')"'
            . ' onerror="this.onerror=null;this.src=\'./files/logo-sauron.png\';">'
            . '<div class="feed-item__body">'
            . '<div class="feed-item__name">' . htmlspecialchars($r["cod_interno"] . " - " . $nombre)
            . ' <span class="feed-item__tag feed-item__tag--' . $tag . '">' . $tag_txt . '</span></div>'
            . '<div class="feed-item__meta">📷 ' . htmlspecialchars($r["cam"]) . ' · ' . dash_tiempo_relativo($r["fecha_ini"]) . '</div>'
            . '</div>'
            . ($i === 0 ? '<span class="feed-item__dot" aria-hidden="true"></span>' : '')
            . '</div>';
        $i++;
    }
    return $out;
}

/** Quién está dentro ahora: pila de avatares + lista. */
function dash_dentro_html($local_id) {
    $dentro = dash_almas_dentro($local_id);
    if (!$dentro) {
        return '<div class="empty-state"><div class="empty-state__icon">🕊️</div>'
            . '<div class="empty-state__title">La fortaleza está vacía</div>'
            . '<div class="empty-state__hint">Nadie dentro ahora mismo. El Ojo descansa tranquilo.</div></div>';
    }
    $out = '<div class="avatar-stack" aria-hidden="true">';
    foreach ($dentro as $i => $p) {
        if ($i >= 6) { break; }
        $img = "./caras_procesadas/" . (int)$p["foto_id"] . ".jpg";
        $out .= '<img class="avatar-stack__img" src="' . htmlspecialchars($img) . '" alt="" loading="lazy"'
            . ' onerror="this.onerror=null;this.src=\'./files/logo-sauron.png\';">';
    }
    if (count($dentro) > 6) {
        $out .= '<span class="avatar-stack__more">+' . (count($dentro) - 6) . '</span>';
    }
    $out .= '</div>'
        . '<div class="inside-now__count tnum"><span class="count-up" data-count="' . count($dentro) . '">' . count($dentro) . '</span>'
        . ' <span class="inside-now__lbl">almas dentro</span></div>'
        . '<ul class="inside-now__list">';
    foreach ($dentro as $p) {
        $nombre = $p["nombre"] !== "" ? $p["nombre"] : $p["cod_interno"];
        $img = "./caras_procesadas/" . (int)$p["foto_id"] . ".jpg";
        $out .= '<li class="inside-now__li">'
            . '<img class="inside-now__avatar" src="' . htmlspecialchars($img) . '" alt="" loading="lazy"'
            . ' onerror="this.onerror=null;this.src=\'./files/logo-sauron.png\';">'
            . '<span class="inside-now__name">' . htmlspecialchars($p["cod_interno"] . " - " . $nombre) . '</span>'
            . '<span class="inside-now__when">' . dash_tiempo_relativo($p["ultimo"]) . '</span>'
            . '</li>';
    }
    $out .= '</ul>';
    return $out;
}

/** Quién falta por fichar hoy. */
function dash_falta_html($local_id) {
    $hay_trabajadores = (int)(DB::selectOne("SELECT COUNT(*) AS n FROM personas WHERE local_id = ? AND trabajador = 1", [(int)$local_id])["n"] ?? 0);
    if ($hay_trabajadores === 0) {
        return '<div class="empty-state"><div class="empty-state__icon">🫏</div>'
            . '<div class="empty-state__title">La legión aún no está registrada</div>'
            . '<div class="empty-state__hint">Marca trabajadores en "Pueblos" (👹) para que el conciliador genere sus fichajes.</div></div>';
    }
    $falta = dash_falta_fichar($local_id);
    if (!$falta) {
        return '<div class="empty-state"><div class="empty-state__icon">🛡️</div>'
            . '<div class="empty-state__title">La guardia está completa</div>'
            . '<div class="empty-state__hint">Todos los trabajadores han cruzado la puerta hoy.</div></div>';
    }
    $loc = DB::selectOne("SELECT hora_entrada1, hora_entrada2, jornada_partida FROM locales WHERE id = ?", [(int)$local_id]);
    $hora_esp = $loc && $loc["hora_entrada1"] ? substr($loc["hora_entrada1"], 0, 5) : "";
    $out = '<ul class="missing__list">';
    foreach ($falta as $p) {
        $nombre = $p["nombre"] !== "" ? $p["nombre"] : $p["cod_interno"];
        $img = "./caras_procesadas/" . (int)$p["foto_id"] . ".jpg";
        $out .= '<li class="missing__li">'
            . '<img class="missing__avatar" src="' . htmlspecialchars($img) . '" alt="" loading="lazy"'
            . ' onerror="this.onerror=null;this.src=\'./files/logo-sauron.png\';">'
            . '<span class="missing__name">' . htmlspecialchars($p["cod_interno"] . " - " . $nombre) . '</span>'
            . '<span class="missing__when">' . ($hora_esp !== "" ? "🕐 esperado ~" . $hora_esp : "sin horario") . '</span>'
            . '</li>';
    }
    $out .= '</ul>';
    return $out;
}

/** Tiles de estado de los 6 daemons. */
function dash_daemons_html() {
    $daemons = dash_daemons();
    $out = "";
    foreach ($daemons as $d) {
        $out .= '<div class="daemon-tile daemon-tile--' . $d["clase"] . '" data-svc="' . htmlspecialchars($d["svc"]) . '" data-lore="' . htmlspecialchars($d["lore"]) . '">'
            . '<span class="daemon-tile__led" aria-hidden="true"></span>'
            . '<div class="daemon-tile__emoji" aria-hidden="true">' . $d["emoji"] . '</div>'
            . '<div class="daemon-tile__name">' . htmlspecialchars($d["nombre"]) . '</div>'
            . '<div class="daemon-tile__svc">' . htmlspecialchars($d["svc"]) . '</div>'
            . '<div class="daemon-tile__estado">' . htmlspecialchars($d["texto"]) . '</div>'
            . '</div>';
    }
    return $out;
}
