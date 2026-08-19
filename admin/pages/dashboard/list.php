<?php

/*
 * Dashboard — La Torre (2026-08-19).
 * Vista de pájaro de Mordor: estado global arriba, sala de guerra, alcance
 * fino (feed / dentro / falta / ranking) y la maquinaria viva (daemons).
 * PDO (B9). Los widgets compartidos viven en widgets.php (los usa también
 * el AJAX de refresco, admin/accionesAjax.php a=4/a=5).
 */

require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/widgets.php";

$local_id = (int)$_SESSION["local_id"];

/* ---------------------------------------------------------------
 * Datos del dashboard
 * ------------------------------------------------------------- */
$aforo   = dash_aforo($local_id);
$dentro  = dash_almas_dentro($local_id);
$almas_dentro = count($dentro);

$hoy_ini = date("Y-m-d 00:00:00");
$hoy_fin = date("Y-m-d 23:59:59");
$ayer_ini = date("Y-m-d 00:00:00", strtotime("-1 day"));
$ayer_fin = date("Y-m-d 23:59:59", strtotime("-1 day"));

$entradas_hoy = dash_movimientos_periodo($local_id, $hoy_ini, $hoy_fin, "entrada");
$salidas_hoy  = dash_movimientos_periodo($local_id, $hoy_ini, $hoy_fin, "salida");
$entradas_ayer = dash_movimientos_periodo($local_id, $ayer_ini, $ayer_fin, "entrada");

function dash_pct_cambio($actual, $anterior) {
    if ($anterior <= 0) { return $actual > 0 ? 100 : 0; }
    return round(($actual - $anterior) / $anterior * 100);
}
$pct_entradas = dash_pct_cambio($entradas_hoy, $entradas_ayer);

$total_trabajadores = (int)(DB::selectOne("SELECT COUNT(*) AS n FROM personas WHERE local_id = ? AND trabajador = 1", [$local_id])["n"] ?? 0);
$fichados_hoy = (int)(DB::selectOne("SELECT COUNT(DISTINCT persona_id) AS n FROM fichajes WHERE local_id = ? AND fecha = CURDATE()", [$local_id])["n"] ?? 0);
$pct_legion = $total_trabajadores > 0 ? round($fichados_hoy / $total_trabajadores * 100) : 0;

$total_camaras = (int)(DB::selectOne("SELECT COUNT(*) AS n FROM camaras WHERE local_id = ?", [$local_id])["n"] ?? 0);
$ciegas = (int)(DB::selectOne("SELECT COUNT(*) AS n FROM camaras WHERE local_id = ? AND encendida = 0", [$local_id])["n"] ?? 0);

$videos_hoy = (int)(DB::selectOne("SELECT COUNT(*) AS n FROM videos WHERE local_id = ? AND DATE(fecha_ini) = CURDATE()", [$local_id])["n"] ?? 0);
$peso_bytes = (int)(DB::selectOne("SELECT COALESCE(SUM(peso),0) AS p FROM videos WHERE local_id = ?", [$local_id])["p"] ?? 0);
$gb_tesoro = $peso_bytes > 0 ? round($peso_bytes / 1073741824, 2) : 0;

$prov_pasados = (int)(DB::selectOne("SELECT COUNT(*) AS n FROM fichajes WHERE local_id = ? AND estado = 'provisional' AND fecha < CURDATE()", [$local_id])["n"] ?? 0);
$anomalias = 0;
$detalle_anomalias = [];
if ($ciegas > 0)                { $anomalias++; $detalle_anomalias[] = "🔴 " . $ciegas . " cámara(s) apagada(s)"; }
if ($aforo["pct"] >= 85)        { $anomalias++; $detalle_anomalias[] = "🔥 Aforo al " . $aforo["pct"] . "%"; }
if ($prov_pasados > 0)          { $anomalias++; $detalle_anomalias[] = "⚖️ " . $prov_pasados . " fichaje(s) sin conciliar"; }

$pico = dash_pico_hoy($local_id);
$vigia = dash_vigia($local_id);

/* --- Series del Mapa de Asedio (filtro era: dia/semana/mes/anyo) --- */
$filtro = $_GET["filtro"] ?? "mes";
$v_etiquetas = []; $v_datos1 = []; $v_datos2 = [];
$txt1 = "Este mes"; $txt2 = "Mes pasado";
switch ($filtro) {
    case "dia":
        $txt1 = "Hoy"; $txt2 = "Ayer";
        for ($h = 0; $h < 24; $h++) {
            $hora = str_pad($h, 2, "0", STR_PAD_LEFT);
            $v_etiquetas[] = $hora . ":00";
            $v_datos1[] = dash_movimientos_periodo($local_id, date("Y-m-d $hora:00:00"), date("Y-m-d $hora:59:59"), "entrada");
            $v_datos2[] = dash_movimientos_periodo($local_id, date("Y-m-d $hora:00:00", strtotime("-1 day")), date("Y-m-d $hora:59:59", strtotime("-1 day")), "entrada");
        }
        break;
    case "semana":
        $txt1 = "Esta semana"; $txt2 = "Semana pasada";
        $dias_es = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
        $dias_en = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
        for ($i = 0; $i < 7; $i++) {
            $dia = $dias_en[$i];
            $v_etiquetas[] = $dias_es[$i];
            $v_datos1[] = dash_movimientos_periodo($local_id, date("Y-m-d 00:00:00", strtotime("$dia this week")), date("Y-m-d 23:59:59", strtotime("$dia this week")), "entrada");
            $v_datos2[] = dash_movimientos_periodo($local_id, date("Y-m-d 00:00:00", strtotime("$dia last week")), date("Y-m-d 23:59:59", strtotime("$dia last week")), "entrada");
        }
        break;
    case "anyo":
        $txt1 = "Este año"; $txt2 = "Año pasado";
        $meses_es = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
        for ($m = 1; $m <= 12; $m++) {
            $label = str_pad($m, 2, "0", STR_PAD_LEFT);
            $v_etiquetas[] = $meses_es[$m - 1];
            $v_datos1[] = dash_movimientos_periodo($local_id, date("Y-$label-01 00:00:00"), date("Y-$label-01 23:59:59"), "entrada");
            $v_datos2[] = dash_movimientos_periodo($local_id, date("Y-$label-01 00:00:00", strtotime("-1 year")), date("Y-$label-01 23:59:59", strtotime("-1 year")), "entrada");
        }
        break;
    case "mes":
    default:
        $txt1 = "Este mes"; $txt2 = "Mes pasado";
        $ultimo_dia = (int)date("t");
        for ($d = 1; $d <= $ultimo_dia; $d++) {
            $dia = str_pad($d, 2, "0", STR_PAD_LEFT);
            $v_etiquetas[] = $dia;
            $v_datos1[] = dash_movimientos_periodo($local_id, date("Y-m-$dia 00:00:00"), date("Y-m-$dia 23:59:59"), "entrada");
            $v_datos2[] = dash_movimientos_periodo($local_id, date("Y-m-$dia 00:00:00", strtotime("-1 month")), date("Y-m-$dia 23:59:59", strtotime("-1 month")), "entrada");
        }
        break;
}

/* --- Donut: actividad por cámara (mes) --- */
$cam_act = dash_camaras_actividad($local_id, 5);
$total_mov_mes = 0;
foreach ($cam_act as $c) { $total_mov_mes += (int)$c["n"]; }

/* --- Heatmap 7×24 --- */
list($heat, $heat_max) = dash_heatmap($local_id, 7);

/* --- Entradas vs salidas por hora (hoy) --- */
$por_hora = DB::select(
    "SELECT HOUR(e.fecha_ini) AS h,
            SUM(CASE WHEN c.puerta = 1 THEN 1 ELSE 0 END) AS entra,
            SUM(CASE WHEN c.salida = 1 THEN 1 ELSE 0 END) AS sale
     FROM estancias e JOIN camaras c ON c.id = e.camara_id
     WHERE c.local_id = ? AND DATE(e.fecha_ini) = CURDATE()
     GROUP BY h",
    [$local_id]
);
$h_entra = array_fill(0, 24, 0); $h_sale = array_fill(0, 24, 0);
foreach ($por_hora as $r) {
    $h_entra[(int)$r["h"]] = (int)$r["entra"];
    $h_sale[(int)$r["h"]]  = (int)$r["sale"];
}
$max_hora = max(1, max(array_merge($h_entra, $h_sale)));

/* --- Profecía de afluencia --- */
$profecia = dash_profecia($local_id);

/* --- Premios --- */
$madrugadora = dash_madrugadora($local_id);
$ranking = dash_ranking($local_id, 5);
$rachas = dash_rachas($local_id, 3);

/* ---------------------------------------------------------------
 * Render SVG (gráficos de línea dibujados a mano, sin Chart.js)
 * ------------------------------------------------------------- */
function dash_svg_line($labels, $series, $etiquetas_visibles = 6, $ancho = 680, $alto = 230) {
    $padL = 34; $padR = 14; $padT = 14; $padB = 26;
    $iw = $ancho - $padL - $padR;
    $ih = $alto - $padT - $padB;

    // máximo incluyendo bandas de confianza
    $max = 1;
    foreach ($series as $s) {
        foreach ($s["data"] as $v) { $max = max($max, (float)$v); }
        if (!empty($s["band"])) {
            foreach ($s["band"] as $v) { $max = max($max, (float)$v); }
        }
    }
    // paso "bonito" para la cuadrícula
    $step = $max / 4;
    $mag = pow(10, floor(log10($step > 0 ? $step : 1)));
    $norm = $step / $mag;
    $nice = $norm <= 1 ? 1 : ($norm <= 2 ? 2 : ($norm <= 5 ? 5 : 10));
    $step = $nice * $mag;
    $max = ceil($max / $step) * $step;

    $n = count($labels);
    $px = [];
    for ($i = 0; $i < $n; $i++) {
        $px[] = $n <= 1 ? $padL : $padL + $iw * $i / ($n - 1);
    }
    $py = function ($v) use ($padT, $ih, $max) {
        return $padT + $ih * (1 - ($max > 0 ? $v / $max : 0));
    };

    $svg = '<svg class="dash-svg" viewBox="0 0 ' . $ancho . ' ' . $alto . '" role="img" aria-label="Gráfico de líneas">';

    // defs: gradientes de relleno únicos por serie (id estable por índice)
    foreach ($series as $i => $s) {
        if (!empty($s["fill"])) {
            $svg .= '<defs><linearGradient id="dash-fill-' . $i . '" x1="0" y1="0" x2="0" y2="1">'
                . '<stop offset="0%" stop-color="' . htmlspecialchars($s["color"]) . '" stop-opacity="0.30"/>'
                . '<stop offset="100%" stop-color="' . htmlspecialchars($s["color"]) . '" stop-opacity="0.02"/>'
                . '</linearGradient></defs>';
        }
    }

    // cuadrícula horizontal + etiquetas Y
    for ($v = 0; $v <= $max; $v += $step) {
        $y = $py($v);
        $svg .= '<line class="dash-svg__grid" x1="' . $padL . '" y1="' . round($y, 1) . '" x2="' . ($ancho - $padR) . '" y2="' . round($y, 1) . '"/>';
        $svg .= '<text class="dash-svg__tick" x="' . ($padL - 6) . '" y="' . round($y + 3, 1) . '" text-anchor="end">' . (int)$v . '</text>';
    }
    // etiquetas X (subconjunto)
    $every = max(1, (int)ceil($n / max(1, $etiquetas_visibles)));
    for ($i = 0; $i < $n; $i++) {
        if ($i % $every !== 0 && $i !== $n - 1) { continue; }
        $svg .= '<text class="dash-svg__tick" x="' . round($px[$i], 1) . '" y="' . ($alto - 8) . '" text-anchor="middle">' . htmlspecialchars((string)$labels[$i]) . '</text>';
    }

    // bandas de confianza (relleno poligonal)
    foreach ($series as $i => $s) {
        if (empty($s["band"])) { continue; }
        $ptsU = []; $ptsL = [];
        foreach ($s["band"] as $j => $v) {
            $ptsU[] = round($px[$j], 1) . "," . round($py((float)$v), 1);
        }
        foreach (array_reverse($s["band"], true) as $j => $v) {
            $bajo = max(0, (float)$v * 0.62);
            $ptsL[] = round($px[$j], 1) . "," . round($py($bajo), 1);
        }
        $svg .= '<polygon class="dash-svg__band" points="' . implode(" ", $ptsU) . " " . implode(" ", $ptsL) . '"/>';
    }

    // líneas + área
    foreach ($series as $i => $s) {
        $pts = [];
        foreach ($s["data"] as $j => $v) {
            $pts[] = round($px[$j], 1) . "," . round($py((float)$v), 1);
        }
        $points = implode(" ", $pts);
        if (!empty($s["fill"])) {
            $svg .= '<polygon class="dash-svg__area" points="' . $padL . ',' . ($padT + $ih) . ' ' . $points . ' ' . ($ancho - $padR) . ',' . ($padT + $ih) . '" fill="url(#dash-fill-' . $i . ')"/>';
        }
        $dash_attr = !empty($s["dash"]) ? ' stroke-dasharray="6 5"' : '';
        $svg .= '<polyline class="dash-svg__line" stroke="' . htmlspecialchars($s["color"]) . '"' . $dash_attr . ' points="' . $points . '"/>';
        if (count($s["data"]) <= 31) {
            foreach ($pts as $j => $p) {
                $xy = explode(",", $p);
                $svg .= '<circle class="dash-svg__pt" cx="' . $xy[0] . '" cy="' . $xy[1] . '" r="2.4" fill="' . htmlspecialchars($s["color"]) . '"/>';
            }
        }
    }
    $svg .= '</svg>';
    return $svg;
}

/* ---------------------------------------------------------------
 * Utilidades de formato
 * ------------------------------------------------------------- */
function dash_fecha_larga($ts = null) {
    $ts = $ts ?: time();
    $dias = ["Domingo", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado"];
    $meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
    return $dias[(int)date("w", $ts)] . ", " . (int)date("j", $ts) . " de " . $meses[(int)date("n", $ts) - 1] . " de " . date("Y", $ts);
}
function dash_saludo() {
    $h = (int)date("G");
    if ($h < 6)  { return "Buenas noches"; }
    if ($h < 13) { return "Buenos días"; }
    if ($h < 21) { return "Buenas tardes"; }
    return "Buenas noches";
}
$usuario = $_SESSION["user"] ?? "Vigilante";

/* Normaliza la URL con page=dash (el dashboard es la página por defecto). */
?>
<script>
    (function () {
        var params = new URLSearchParams(window.location.search);
        var page = params.get("page");
        if (page === null || page === "") {
            var u = new URL(window.location.href);
            u.searchParams.set("page", "dash");
            history.replaceState(null, "", u.toString());
        }
    })();
</script>

<!-- ================================================================
     🧭 ACCESOS DIRECTOS (enlaces rápidos)
     ================================================================ -->
<div class="col-span-12 mt-8">
    <div class="intro-y flex items-center h-10">
        <h2 class="text-lg font-medium truncate mr-5">🧭 El Camino del Mensajero</h2>
        <a href="?page=dash" class="ml-auto flex text-theme-1 dark:text-theme-10">🔮 Reinvocar Datos</a>
    </div>
    <nav class="quick-links mt-3" aria-label="Accesos directos">
        <a class="quick-link quick-link--anchor" href="#seccion-fichajes"><span class="quick-link__emoji" aria-hidden="true">⏳</span><span class="quick-link__label">Fichajes de hoy</span></a>
        <a class="quick-link quick-link--anchor" href="#seccion-dentro"><span class="quick-link__emoji" aria-hidden="true">🔍</span><span class="quick-link__label">Quién está dentro</span></a>
        <a class="quick-link quick-link--anchor" href="#seccion-falta"><span class="quick-link__emoji" aria-hidden="true">⏰</span><span class="quick-link__label">Falta por fichar</span></a>
    </nav>
</div>

<!-- ================================================================
     🏰 HERO — ESTADO DE MORDOR (vista de pájaro)
     ================================================================ -->
<div class="col-span-12 mt-8">
    <div class="mordor-hero intro-y box p-6">
        <div class="mordor-hero__grid">
            <!-- Caldero de aforo -->
            <div class="mordor-hero__gauge">
                <div class="aforo-gauge aforo-gauge--<?= $aforo["estado"]; ?>" id="aforo-gauge">
                    <div class="aforo-gauge__vessel" role="img" aria-label="Caldero de aforo" data-lore="caldero-aforo">
                        <div class="aforo-gauge__lava" id="aforo-lava" style="--nivel:<?= min(100, $aforo["pct"]); ?>%"></div>
                        <span class="aforo-gauge__tick aforo-gauge__tick--t1" aria-hidden="true"></span>
                        <span class="aforo-gauge__tick aforo-gauge__tick--t2" aria-hidden="true"></span>
                        <span class="aforo-gauge__tick aforo-gauge__tick--t3" aria-hidden="true"></span>
                        <span class="aforo-gauge__tick aforo-gauge__tick--t4" aria-hidden="true"></span>
                    </div>
                    <div class="aforo-gauge__readout">
                        <div class="aforo-gauge__value tnum" id="aforo-actual"><?= (int)$aforo["actual"]; ?></div>
                        <div class="aforo-gauge__of">de <span id="aforo-max" class="tnum"><?= (int)$aforo["max"]; ?></span> plazas</div>
                        <div class="aforo-gauge__sem" id="aforo-sem" data-lore="semaforo-aforo"><?php
                            if ($aforo["estado"] === "full") { echo "🔴 Asedio · " . $aforo["pct"] . "%"; }
                            elseif ($aforo["estado"] === "warn") { echo "🟡 Animado · " . $aforo["pct"] . "%"; }
                            else { echo "🟢 Tranquilo · " . $aforo["pct"] . "%"; }
                        ?></div>
                        <div class="aforo-gauge__control">
                            <input type="number" id="aforo_input" class="input border w-24" min="0" placeholder="<?= (int)$aforo["actual"]; ?>" aria-label="Nuevo aforo actual de la fortaleza" title="Fijar el aforo actual">
                            <button type="button" class="button text-white bg-theme-1 shadow-md" data-lore="fijar-aforo" onclick="dashCambiarAforo()">⚙️ Fijar</button>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Saludo + estado -->
            <div class="mordor-hero__main">
                <div class="mordor-hero__eyebrow" aria-hidden="true">👁️ EL OJO VIGILA</div>
                <h1 class="mordor-hero__title">Estado de Mordor</h1>
                <p class="mordor-hero__saludo"><?= dash_saludo(); ?>, <strong><?= htmlspecialchars($usuario); ?></strong> — <?= htmlspecialchars(dash_fecha_larga()); ?> · <span id="dash-clock" class="tnum">--:--:--</span></p>

                <div class="hero-kpis">
                    <div class="hero-kpi" data-lore="almas-dentro-ahora">
                        <span class="hero-kpi__emoji" aria-hidden="true">👁️</span>
                        <span class="hero-kpi__num tnum" id="hero-dentro"><?= $almas_dentro; ?></span>
                        <span class="hero-kpi__lbl">almas dentro</span>
                    </div>
                    <div class="hero-kpi <?= $ciegas > 0 ? "hero-kpi--alerta" : ""; ?>" data-lore="camaras-en-pie">
                        <span class="hero-kpi__emoji" aria-hidden="true">📷</span>
                        <span class="hero-kpi__num tnum"><?= $total_camaras - $ciegas; ?>/<?= $total_camaras; ?></span>
                        <span class="hero-kpi__lbl">cámaras en pie</span>
                    </div>
                    <div class="hero-kpi <?= $anomalias > 0 ? "hero-kpi--alerta" : ""; ?>" data-lore="anomalias-ojo">
                        <span class="hero-kpi__emoji" aria-hidden="true">🔥</span>
                        <span class="hero-kpi__num tnum"><?= $anomalias; ?></span>
                        <span class="hero-kpi__lbl">anomalías</span>
                    </div>
                    <div class="hero-kpi" data-lore="pergaminos-ojo">
                        <span class="hero-kpi__emoji" aria-hidden="true">🎞️</span>
                        <span class="hero-kpi__num tnum"><?= $videos_hoy; ?></span>
                        <span class="hero-kpi__lbl">vídeos hoy</span>
                    </div>
                </div>

                <?php if ($anomalias > 0): ?>
                <div class="hero-alertas" role="alert">
                    <strong>🚨 Señales de alarma:</strong>
                    <?= htmlspecialchars(implode(" · ", $detalle_anomalias)); ?>
                </div>
                <?php endif; ?>
            </div>
        </div>
    </div>
</div>

<!-- ================================================================
     👁️ LA VANGUARDIA — tarjetas KPI
     ================================================================ -->
<div class="col-span-12 mt-8">
    <div class="intro-y flex items-center h-10">
        <h2 class="text-lg font-medium truncate mr-5">👁️ La Vanguardia</h2>
        <span class="ml-auto text-xs text-gray-500 dark:text-gray-500">lo esencial de un vistazo</span>
    </div>
    <div class="grid grid-cols-12 gap-6 mt-5">
        <!-- Puertas de Morannon -->
        <div class="col-span-12 sm:col-span-6 xl:col-span-4 intro-y">
            <div class="report-box zoom-in">
                <div class="box p-5 kpi-card kpi-card--brasas">
                    <div class="flex">
                        <div class="kpi-chip"><div class="menu__emoji kpi-emoji">🚪</div></div>
                        <div class="ml-auto"><span class="tendencia-pill tendencia-pill--<?= $pct_entradas >= 0 ? "up" : "down"; ?>"><?= ($pct_entradas > 0 ? "+" : "") . $pct_entradas . "%"; ?></span></div>
                    </div>
                    <div class="kpi-number mt-4 tnum count-up" data-count="<?= $entradas_hoy; ?>"><?= $entradas_hoy; ?></div>
                    <div class="kpi-label mt-1" data-lore="cruzaron-puerta">Cruzaron la Puerta Negra <span class="kpi-sub">· <?= $salidas_hoy; ?> salieron · neto <?= ($entradas_hoy - $salidas_hoy) >= 0 ? "+" : ""; ?><?= $entradas_hoy - $salidas_hoy; ?></span></div>
                </div>
            </div>
        </div>
        <!-- Almas Dentro -->
        <div class="col-span-12 sm:col-span-6 xl:col-span-4 intro-y">
            <div class="report-box zoom-in">
                <div class="box p-5 kpi-card kpi-card--oro">
                    <div class="flex">
                        <div class="kpi-chip"><div class="menu__emoji kpi-emoji">👁️</div></div>
                        <div class="ml-auto"><span class="live-dot" aria-hidden="true"></span></div>
                    </div>
                    <div class="kpi-number mt-4 tnum count-up" data-count="<?= $almas_dentro; ?>"><?= $almas_dentro; ?></div>
                    <div class="kpi-label mt-1">Almas dentro ahora <span class="kpi-sub">· <?= $aforo["max"] > 0 ? $aforo["pct"] . "% de la fortaleza" : "aforo sin límite"; ?></span></div>
                </div>
            </div>
        </div>
        <!-- Legión en Formación -->
        <div class="col-span-12 sm:col-span-6 xl:col-span-4 intro-y">
            <div class="report-box zoom-in">
                <div class="box p-5 kpi-card kpi-card--verde">
                    <div class="flex">
                        <div class="kpi-chip"><div class="menu__emoji kpi-emoji">🛡️</div></div>
                        <div class="ml-auto"><span class="tendencia-pill tendencia-pill--<?= $total_trabajadores > 0 ? ($pct_legion >= 70 ? "up" : ($pct_legion >= 40 ? "flat" : "down")) : "flat"; ?>"><?= $total_trabajadores > 0 ? $pct_legion . "%" : "—"; ?></span></div>
                    </div>
                    <?php if ($total_trabajadores > 0): ?>
                    <div class="kpi-number mt-4 tnum count-up" data-count="<?= $fichados_hoy; ?>"><?= $fichados_hoy; ?><span class="kpi-number__frac">/<?= $total_trabajadores; ?></span></div>
                    <div class="kpi-label mt-1">Legión en formación <span class="kpi-sub">· han fichado hoy</span></div>
                    <div class="kpi-progress kpi-progress--<?= $pct_legion >= 85 ? "full" : ($pct_legion >= 60 ? "warn" : "ok"); ?> mt-3"><div class="kpi-progress__fill" style="width:<?= $pct_legion; ?>%"></div></div>
                    <?php else: ?>
                    <div class="kpi-number mt-4 tnum">—</div>
                    <div class="kpi-label mt-1">Legión en formación <span class="kpi-sub">· sin trabajadores dados de alta</span></div>
                    <?php endif; ?>
                </div>
            </div>
        </div>
        <!-- Cámaras Ciegas -->
        <div class="col-span-12 sm:col-span-6 xl:col-span-3 intro-y">
            <div class="report-box zoom-in">
                <div class="box p-5 kpi-card <?= $ciegas > 0 ? "kpi-card--alerta" : "kpi-card--humo"; ?>">
                    <div class="flex">
                        <div class="kpi-chip"><div class="menu__emoji kpi-emoji">📷</div></div>
                        <div class="ml-auto"><?= $ciegas > 0 ? '<span class="tendencia-pill tendencia-pill--down">¡ojo!</span>' : '<span class="tendencia-pill tendencia-pill--flat">ok</span>'; ?></div>
                    </div>
                    <div class="kpi-number mt-4 tnum count-up" data-count="<?= $ciegas; ?>"><?= $ciegas; ?></div>
                    <div class="kpi-label mt-1">Cámaras ciegas <span class="kpi-sub">· <?= $total_camaras; ?> desplegadas</span></div>
                </div>
            </div>
        </div>
        <!-- Hora del Asedio -->
        <div class="col-span-12 sm:col-span-6 xl:col-span-3 intro-y">
            <div class="report-box zoom-in">
                <div class="box p-5 kpi-card kpi-card--brasas">
                    <div class="flex">
                        <div class="kpi-chip"><div class="menu__emoji kpi-emoji">⚔️</div></div>
                        <div class="ml-auto"><span class="live-dot" aria-hidden="true"></span></div>
                    </div>
                    <div class="kpi-number mt-4 tnum"><?= $pico ? str_pad((int)$pico["h"], 2, "0", STR_PAD_LEFT) . ":00" : "—"; ?></div>
                    <div class="kpi-label mt-1">Hora del asedio <span class="kpi-sub">· pico de hoy (<?= $pico ? (int)$pico["n"] . " movs" : "sin datos"; ?>)</span></div>
                </div>
            </div>
        </div>
        <!-- Pergaminos del Ojo -->
        <div class="col-span-12 sm:col-span-6 xl:col-span-3 intro-y">
            <div class="report-box zoom-in">
                <div class="box p-5 kpi-card kpi-card--humo">
                    <div class="flex">
                        <div class="kpi-chip"><div class="menu__emoji kpi-emoji">🎞️</div></div>
                        <div class="ml-auto"><span class="tendencia-pill tendencia-pill--flat">archivo</span></div>
                    </div>
                    <div class="kpi-number mt-4 tnum count-up" data-count="<?= $videos_hoy; ?>"><?= $videos_hoy; ?></div>
                    <div class="kpi-label mt-1">Pergaminos del Ojo <span class="kpi-sub">· 💾 <?= $gb_tesoro > 0 ? $gb_tesoro . " GB en la Forja" : "0 GB"; ?></span></div>
                </div>
            </div>
        </div>
        <!-- Vigía Incansable -->
        <div class="col-span-12 sm:col-span-6 xl:col-span-3 intro-y">
            <div class="report-box zoom-in">
                <div class="box p-5 kpi-card kpi-card--oro">
                    <div class="flex">
                        <div class="kpi-chip"><div class="menu__emoji kpi-emoji">📹</div></div>
                        <div class="ml-auto"><span class="tendencia-pill tendencia-pill--flat">hoy</span></div>
                    </div>
                    <div class="kpi-number mt-4 tnum" style="font-size:1.6rem;line-height:1.3"><?= htmlspecialchars($vigia["descripcion"] ?? "—"); ?></div>
                    <div class="kpi-label mt-1">El vigía incansable <span class="kpi-sub">· <?= $vigia ? (int)$vigia["n"] . " detecciones hoy" : "sin actividad"; ?></span></div>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- ================================================================
     ⚔️ LA SALA DE GUERRA — gráficos
     ================================================================ -->
<div class="col-span-12 mt-8">
    <div class="grid grid-cols-12 gap-6">
        <!-- Mapa de Asedio -->
        <div class="col-span-12 xl:col-span-7 intro-y">
            <div class="box p-5 h-full">
                <div class="flex flex-col xl:flex-row xl:items-center">
                    <div>
                        <h2 class="text-lg font-medium truncate mr-5">🗺️ Mapa de Asedio</h2>
                        <div class="flex items-center mt-1 gap-4">
                            <div class="flex items-center"><span class="dash-legend dash-legend--actual" aria-hidden="true"></span><span class="text-xs text-gray-600 dark:text-gray-500"><?= htmlspecialchars($txt1); ?> · <strong class="tnum"><?= array_sum($v_datos1); ?></strong></span></div>
                            <div class="flex items-center"><span class="dash-legend dash-legend--pasado" aria-hidden="true"></span><span class="text-xs text-gray-600 dark:text-gray-500"><?= htmlspecialchars($txt2); ?> · <strong class="tnum"><?= array_sum($v_datos2); ?></strong></span></div>
                        </div>
                    </div>
                    <div class="dropdown relative xl:ml-auto mt-3 xl:mt-0">
                        <button class="dropdown-toggle button font-normal border dark:border-dark-5 text-white dark:text-gray-300 relative flex items-center text-gray-700">🕰️ Elegir era</button>
                        <div class="dropdown-box mt-10 absolute w-40 top-0 xl:right-0 z-20">
                            <div class="dropdown-box__content box dark:bg-dark-1 p-2 overflow-y-auto h-32">
                                <a href="?page=dash&filtro=dia" class="flex items-center block p-2">🌅 Un amanecer</a>
                                <a href="?page=dash&filtro=semana" class="flex items-center block p-2">🌙 Una luna</a>
                                <a href="?page=dash&filtro=mes" class="flex items-center block p-2">📅 Un ciclo</a>
                                <a href="?page=dash&filtro=anyo" class="flex items-center block p-2">🏛️ Una era</a>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="mt-4">
                    <?= dash_svg_line($v_etiquetas, [
                        ["label" => $txt1, "data" => $v_datos1, "color" => "#ff5a1f", "fill" => true],
                        ["label" => $txt2, "data" => $v_datos2, "color" => "#8a8078", "dash" => true],
                    ]); ?>
                </div>
            </div>
        </div>

        <!-- La Puerta vs Las Cámaras -->
        <div class="col-span-12 xl:col-span-5 intro-y">
            <div class="box p-5 h-full">
                <h2 class="text-lg font-medium truncate">⚖️ La Puerta vs Las Cámaras</h2>
                <div class="text-xs text-gray-600 dark:text-gray-500 mt-1">actividad por cámara · último mes</div>
                <?php
                $donut_html = "";
                $sum = max(1, $total_mov_mes);
                $acum = 0; $grad = []; $i = 0;
                $paleta = ["#ff5a1f", "#c9a227", "#3d5a3a", "#8a8078", "#d8d0c4"];
                foreach ($cam_act as $c) {
                    $pct = round((int)$c["n"] / $sum * 100, 1);
                    $desde = $acum; $acum += $pct;
                    $grad[] = $paleta[$i % 5] . " " . $desde . "% " . $acum . "%";
                    $i++;
                }
                if (!$cam_act) { $grad[] = "#3d2b1a 0% 100%"; }
                ?>
                <div class="donut-wrap">
                    <div class="donut" style="background: conic-gradient(<?= implode(", ", $grad); ?>);" role="img" aria-label="Distribución de actividad por cámara">
                        <div class="donut__hole">
                            <div class="donut__total tnum"><?= $total_mov_mes; ?></div>
                            <div class="donut__lbl">movs / mes</div>
                        </div>
                    </div>
                    <ul class="donut-legend">
                        <?php foreach ($cam_act as $i => $c): ?>
                        <li class="donut-legend__li">
                            <span class="donut-legend__dot" style="background:<?= $paleta[$i % 5]; ?>" aria-hidden="true"></span>
                            <span class="donut-legend__name"><?= htmlspecialchars($c["descripcion"]); ?></span>
                            <span class="donut-legend__val tnum"><?= (int)$c["n"]; ?></span>
                        </li>
                        <?php endforeach; ?>
                        <?php if (!$cam_act): ?><li class="donut-legend__li"><span class="donut-legend__name">Sin actividad este mes</span></li><?php endif; ?>
                    </ul>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- ================================================================
     🔥 FRAGUAS POR HORA (heatmap 7×24) + ENTRADAS VS SALIDAS
     ================================================================ -->
<div class="col-span-12 mt-8">
    <div class="grid grid-cols-12 gap-6">
        <!-- Heatmap -->
        <div class="col-span-12 xl:col-span-7 intro-y">
            <div class="box p-5">
                <h2 class="text-lg font-medium truncate">🔥 Las Fraguas por Hora</h2>
                <div class="text-xs text-gray-600 dark:text-gray-500 mt-1">afluencia · últimos 7 días · pasa el cursor por una celda</div>
                <div class="heat-card mt-3">
                    <?php
                    $dias_heat = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
                    for ($d = 0; $d < 7; $d++) {
                        echo '<div class="heat-row">';
                        echo '<div class="heat-day">' . $dias_heat[$d] . '</div>';
                        for ($h = 0; $h < 24; $h++) {
                            $v = $heat[$d][$h];
                            $alpha = $v > 0 ? round(0.08 + 0.88 * ($v / $heat_max), 2) : 0;
                            echo '<span class="heat-cell' . ($v > 0 ? "" : " heat-cell--empty") . '" style="background:rgba(224,60,0,' . $alpha . ')" data-tip="' . $dias_heat[$d] . ' · ' . str_pad($h, 2, "0", STR_PAD_LEFT) . ':00 → ' . $v . ' movs"></span>';
                        }
                        echo '</div>';
                    }
                    ?>
                    <div class="heat-scale" aria-hidden="true">
                        <span>poco</span>
                        <div class="heat-scale__bar"></div>
                        <span>mucho</span>
                    </div>
                </div>
            </div>
        </div>

        <!-- Entradas vs Salidas hoy -->
        <div class="col-span-12 xl:col-span-5 intro-y">
            <div class="box p-5 h-full">
                <h2 class="text-lg font-medium truncate">🚪 Entradas vs Salidas · hoy</h2>
                <div class="flex items-center gap-4 mt-1 text-xs text-gray-600 dark:text-gray-500">
                    <span class="flex items-center gap-1"><span class="dash-legend dash-legend--actual" aria-hidden="true"></span>Entradas (puerta)</span>
                    <span class="flex items-center gap-1"><span class="dash-legend dash-legend--salidas" aria-hidden="true"></span>Salidas</span>
                </div>
                <div class="bars-chart mt-4" role="img" aria-label="Entradas y salidas por hora de hoy">
                    <?php for ($h = 0; $h < 24; $h++): ?>
                    <div class="bars-col">
                        <div class="bars-pair" data-tip="<?= str_pad($h, 2, "0", STR_PAD_LEFT) . ":00 · " . $h_entra[$h] . " entradas / " . $h_sale[$h] . " salidas"; ?>">
                            <div class="bars-bar bars-bar--entra" style="height:<?= round($h_entra[$h] / $max_hora * 100); ?>%"></div>
                            <div class="bars-bar bars-bar--sale" style="height:<?= round($h_sale[$h] / $max_hora * 100); ?>%"></div>
                        </div>
                        <?php if ($h % 4 === 0): ?><div class="bars-lbl"><?= str_pad($h, 2, "0", STR_PAD_LEFT); ?></div><?php else: ?><div class="bars-lbl bars-lbl--void"></div><?php endif; ?>
                    </div>
                    <?php endfor; ?>
                </div>
            </div>
        </div>
    </div>
</div>

<!-- ================================================================
     📜 EL ALCANCE — secciones expandibles
     ================================================================ -->
<div class="col-span-12 mt-8">
    <div class="intro-y flex items-center h-10">
        <h2 class="text-lg font-medium truncate mr-5">📜 El Alcance del Ojo</h2>
        <span class="ml-auto text-xs text-gray-500 dark:text-gray-500">despliega para más detalle</span>
    </div>

    <!-- Crónica del Ojo (feed) -->
    <section class="scroll-section scroll-section--open intro-y box p-5 mt-5" id="seccion-cronica">
        <button class="scroll-section__toggle" aria-expanded="true" aria-controls="cronica-body">
            <span class="scroll-section__emoji" aria-hidden="true">👁️</span>
            <span class="scroll-section__title">Crónica del Ojo en Vivo</span>
            <span class="scroll-section__hint">últimos movimientos · <span id="feed-actualizado">ahora</span></span>
            <span class="scroll-section__chevron" aria-hidden="true">▾</span>
        </button>
        <div class="scroll-section__body" id="cronica-body">
            <div class="live-feed" id="live-feed-list">
                <?= dash_feed_html($local_id, 10); ?>
            </div>
            <div class="mt-4 text-right">
                <a class="text-theme-1 dark:text-theme-10 text-xs font-semibold" href="?page=accesos">↳ Ver todos los Movimientos →</a>
            </div>
        </div>
    </section>

    <!-- Quién está Dentro -->
    <section class="scroll-section intro-y box p-5 mt-5" id="seccion-dentro">
        <button class="scroll-section__toggle" aria-expanded="false" aria-controls="dentro-body">
            <span class="scroll-section__emoji" aria-hidden="true">🚶</span>
            <span class="scroll-section__title">Quién está Dentro</span>
            <span class="scroll-section__hint"><span class="tnum" id="dentro-count"><?= $almas_dentro; ?></span> almas en la fortaleza</span>
            <span class="scroll-section__chevron" aria-hidden="true">▾</span>
        </button>
        <div class="scroll-section__body" id="dentro-body" hidden>
            <div id="inside-now-list"><?= dash_dentro_html($local_id); ?></div>
        </div>
    </section>

    <!-- Falta por Fichar -->
    <section class="scroll-section intro-y box p-5 mt-5" id="seccion-falta">
        <button class="scroll-section__toggle" aria-expanded="false" aria-controls="falta-body">
            <span class="scroll-section__emoji" aria-hidden="true">⏳</span>
            <span class="scroll-section__title">Falta por Fichar</span>
            <span class="scroll-section__hint"><span class="tnum" id="falta-count"><?= count(dash_falta_fichar($local_id)); ?></span> trabajadores aún en camino</span>
            <span class="scroll-section__chevron" aria-hidden="true">▾</span>
        </button>
        <div class="scroll-section__body" id="falta-body" hidden>
            <div id="missing-list"><?= dash_falta_html($local_id); ?></div>
        </div>
    </section>

    <!-- Fichajes de hoy -->
    <section class="scroll-section scroll-section--open intro-y box p-5 mt-5" id="seccion-fichajes">
        <button class="scroll-section__toggle" aria-expanded="true" aria-controls="fichajes-body">
            <span class="scroll-section__emoji" aria-hidden="true">⏳</span>
            <span class="scroll-section__title">Fichajes de hoy</span>
            <span class="scroll-section__hint"><span class="tnum"><?= $fichados_hoy; ?></span> trabajadores han fichado</span>
            <span class="scroll-section__chevron" aria-hidden="true">▾</span>
        </button>
        <div class="scroll-section__body" id="fichajes-body">
            <div id="fichajes-hoy-list"><?= dash_fichajes_html($local_id); ?></div>
            <div class="mt-4 text-right">
                <a class="text-theme-1 dark:text-theme-10 text-xs font-semibold" href="?page=fichajes">↳ Ver todos los Fichajes →</a>
            </div>
        </div>
    </section>

    <!-- El Concilio de los Fieles (ranking + premios) -->
    <section class="scroll-section intro-y box p-5 mt-5" id="seccion-ranking">
        <button class="scroll-section__toggle" aria-expanded="false" aria-controls="ranking-body">
            <span class="scroll-section__emoji" aria-hidden="true">👑</span>
            <span class="scroll-section__title">El Concilio de los Fieles</span>
            <span class="scroll-section__hint">rankings y glorias del mes</span>
            <span class="scroll-section__chevron" aria-hidden="true">▾</span>
        </button>
        <div class="scroll-section__body" id="ranking-body" hidden>
            <div class="grid grid-cols-12 gap-6">
                <div class="col-span-12 lg:col-span-7">
                    <h3 class="scroll-section__sub">🏆 Los más leales · 30 días</h3>
                    <ul class="ranking">
                        <?php foreach ($ranking as $i => $r):
                            $medallas = ["🥇", "🥈", "🥉"];
                            $medalla = $i < 3 ? $medallas[$i] : (($i + 1) . "º");
                            $pct_barra = $ranking[0]["n"] > 0 ? round((int)$r["n"] / (int)$ranking[0]["n"] * 100) : 0;
                            $img = "./caras_procesadas/" . (int)$r["foto_id"] . ".jpg";
                        ?>
                        <li class="ranking__li">
                            <span class="ranking__medal" aria-hidden="true"><?= $medalla; ?></span>
                            <img class="ranking__avatar" src="<?= htmlspecialchars($img); ?>" alt="" loading="lazy" onerror="this.onerror=null;this.src='./files/logo-sauron.png';">
                            <div class="ranking__info">
                                <div class="ranking__name"><?= htmlspecialchars($r["cod_interno"] . " - " . ($r["nombre"] !== "" ? $r["nombre"] : $r["cod_interno"])); ?></div>
                                <div class="ranking__bar"><div class="ranking__fill" style="width:<?= $pct_barra; ?>%"></div></div>
                            </div>
                            <span class="ranking__val tnum"><?= (int)$r["n"]; ?> <small>visitas</small></span>
                        </li>
                        <?php endforeach; ?>
                        <?php if (!$ranking): ?><li class="ranking__li ranking__li--empty">Aún no hay súbditos este mes. 🕸️</li><?php endif; ?>
                    </ul>
                </div>
                <div class="col-span-12 lg:col-span-5">
                    <h3 class="scroll-section__sub">✨ Glorias del Reino</h3>
                    <ul class="premios">
                        <li class="premio">
                            <span class="premio__emoji" aria-hidden="true">🌅</span>
                            <div class="premio__info">
                                <div class="premio__titulo">Alma madrugadora de hoy</div>
                                <div class="premio__valor"><?= $madrugadora ? htmlspecialchars($madrugadora["cod_interno"] . " · " . ($madrugadora["nombre"] !== "" ? $madrugadora["nombre"] : $madrugadora["cod_interno"])) . " a las " . date("H:i", strtotime($madrugadora["t"])) : "Nadie ha llegado aún 🕊️"; ?></div>
                            </div>
                        </li>
                        <li class="premio">
                            <span class="premio__emoji" aria-hidden="true">🏆</span>
                            <div class="premio__info">
                                <div class="premio__titulo">El Visitante más Leal</div>
                                <div class="premio__valor"><?= isset($ranking[0]) ? htmlspecialchars($ranking[0]["cod_interno"] . " · " . ($ranking[0]["nombre"] !== "" ? $ranking[0]["nombre"] : $ranking[0]["cod_interno"])) . " con " . (int)$ranking[0]["n"] . " visitas" : "—"; ?></div>
                            </div>
                        </li>
                        <li class="premio">
                            <span class="premio__emoji" aria-hidden="true">🔥</span>
                            <div class="premio__info">
                                <div class="premio__titulo">Rachas de presencia (14 días)</div>
                                <div class="premio__valor">
                                    <?php foreach ($rachas as $i => $r): ?>
                                        <span class="premio__racha"><?= htmlspecialchars(($r["nombre"] !== "" ? $r["nombre"] : $r["cod_interno"])); ?> · <?= (int)$r["dias"]; ?> días</span><?= $i < count($rachas) - 1 ? ", " : ""; ?>
                                    <?php endforeach; ?>
                                    <?php if (!$rachas): ?>—<?php endif; ?>
                                </div>
                            </div>
                        </li>
                    </ul>
                </div>
            </div>
        </div>
    </section>
</div>

<!-- ================================================================
     🔮 PROFECÍA DE AFLUENCIA
     ================================================================ -->
<div class="col-span-12 mt-8">
    <div class="intro-y box p-5">
        <div class="flex flex-col sm:flex-row sm:items-center gap-2">
            <div>
                <h2 class="text-lg font-medium truncate">🔮 Profecía de Afluencia</h2>
                <div class="text-xs text-gray-600 dark:text-gray-500 mt-1">real hoy (brasa) vs media de los mismos días de semana (oro) · últimos 28 días</div>
            </div>
            <div class="sm:ml-auto flex flex-wrap gap-2 text-xs">
                <span class="prophecy-pill">📅 esperado: <strong class="tnum"><?= $profecia["total_esperado"]; ?></strong></span>
                <span class="prophecy-pill">⚡ real (acumulado): <strong class="tnum"><?= $profecia["total_real"]; ?></strong></span>
                <?php if ($profecia["pico_h"] !== 0 || $profecia["pico_v"] > 0): ?>
                <span class="prophecy-pill">⏰ asedio previsto ~<strong class="tnum"><?= str_pad($profecia["pico_h"], 2, "0", STR_PAD_LEFT); ?>:00</strong></span>
                <?php endif; ?>
            </div>
        </div>
        <div class="mt-4">
            <?php
            $labels_p = [];
            for ($h = 0; $h < 24; $h++) { $labels_p[] = str_pad($h, 2, "0", STR_PAD_LEFT) . ":00"; }
            // banda de confianza: esperado *1.35 (la serie esperada es la media)
            $banda = array_map(fn($v) => $v * 1.35, $profecia["esperado"]);
            echo dash_svg_line($labels_p, [
                ["label" => "Esperado", "data" => $profecia["esperado"], "color" => "#c9a227", "dash" => true, "band" => $banda],
                ["label" => "Real hoy", "data" => $profecia["real"], "color" => "#ff5a1f", "fill" => true],
            ], 6, 680, 200);
            ?>
            <p class="prophecy__augur mt-2"><?php
                $d = $profecia["total_real"] - $profecia["total_esperado"];
                if ($profecia["total_esperado"] === 0) { echo "🜂 El fuego aún no habla; regresa cuando haya historia que leer."; }
                elseif ($d > 0) { echo "🜂 El fuego crece con fuerza: hoy llega más gente de lo habitual (" . $d . " almas por encima de lo esperado). ¡Preparad la puerta!"; }
                elseif ($d < 0) { echo "🜂 El fuego titubea: hoy hay " . abs($d) . " almas por debajo de lo esperado. Mordor descansa."; }
                else { echo "🜂 El fuego respira tranquilo: la afluencia sigue la profecía al pie de la letra."; }
            ?></p>
        </div>
    </div>
</div>

<!-- ================================================================
     ⚙️ LOS SEIS CENTINELAS — daemons
     ================================================================ -->
<div class="col-span-12 mt-8">
    <div class="intro-y box p-5">
        <div class="flex items-center">
            <h2 class="text-lg font-medium truncate">⚙️ Los Seis Centinelas</h2>
            <span class="ml-auto text-xs text-gray-500 dark:text-gray-500" id="daemons-updated">estado de los procesos · se refresca solo</span>
        </div>
        <div class="daemons mt-4" id="daemons-grid">
            <?= dash_daemons_html(); ?>
        </div>
    </div>
</div>
