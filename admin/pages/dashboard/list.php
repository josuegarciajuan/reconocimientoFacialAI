<?php

/* 
 * Dashboard — listado (REFACTOR Fase 4b): PDO (B9) + fix B12 (división por cero, lafecha).
 */

require_once __DIR__ . "/../../../libs/db.php";

$local_id = (int)$_SESSION["local_id"];

$aforo_actual = 0;
$loc = DB::selectOne("SELECT aforo_actual FROM locales WHERE id = ?", [$local_id]);
if ($loc) {
    $aforo_actual = (int)$loc["aforo_actual"];
}

function entradas_periodo($local_id, $desde, $hasta) {
    $r = DB::selectOne(
        "SELECT COUNT(DISTINCT e.persona_id) AS cuenta
         FROM estancias e JOIN camaras c ON c.id = e.camara_id JOIN personas p ON p.id = e.persona_id
         WHERE p.trabajador = 0 AND c.puerta = 1 AND c.local_id = ? AND e.created >= ? AND e.created <= ?",
        [$local_id, $desde, $hasta]
    );
    return $r ? (int)$r["cuenta"] : 0;
}

// visitas hoy
$visitas_hoy = entradas_periodo($local_id, date("Y-m-d 00:00:00"), date("Y-m-d 23:59:59"));

// visitas medias diarias (media de cuentas por día)
$visitas_medias_diarias = 0;
$rows = DB::select(
    "SELECT COUNT(DISTINCT e.persona_id) AS cuenta
     FROM estancias e JOIN camaras c ON c.id = e.camara_id JOIN personas p ON p.id = e.persona_id
     WHERE p.trabajador = 0 AND c.puerta = 1 AND c.local_id = ?
     GROUP BY DATE(e.created)",
    [$local_id]
);
if ($rows) {
    $total = array_sum(array_column($rows, "cuenta"));
    $visitas_medias_diarias = round($total / count($rows));  // B12: sin división por cero
}

// visitantes recurrentes (personas en >1 día distinto)
$visitantes_recurrentes = 0;
$r = DB::selectOne(
    "SELECT COUNT(*) AS n FROM (
        SELECT e.persona_id FROM estancias e
        JOIN camaras c ON c.id = e.camara_id JOIN personas p ON p.id = e.persona_id
        WHERE p.trabajador = 0 AND c.puerta = 1 AND c.local_id = ?
        GROUP BY e.persona_id HAVING COUNT(DISTINCT DATE(e.fecha_ini)) > 1
     ) t",
    [$local_id]
);
$visitantes_recurrentes = $r ? (int)$r["n"] : 0;

// gráfico (periodo actual vs anterior)
$filtro = $_GET["filtro"] ?? "mes";
switch ($filtro) {
    case "dia":
        $txt1 = "Hoy"; $txt2 = "Ayer";
        $desde1 = date("Y-m-d 00:00:00"); $hasta1 = date("Y-m-d 23:59:59");
        $desde2 = date("Y-m-d 00:00:00", strtotime("-1 days")); $hasta2 = date("Y-m-d 23:59:59", strtotime("-1 days"));
        break;
    case "semana":
        $txt1 = "Esta semana"; $txt2 = "Semana pasada";
        $desde1 = date("Y-m-d 00:00:00", strtotime("monday this week")); $hasta1 = date("Y-m-d 23:59:59", strtotime("sunday this week"));
        $desde2 = date("Y-m-d 00:00:00", strtotime("monday last week")); $hasta2 = date("Y-m-d 23:59:59", strtotime("sunday last week"));
        break;
    case "anyo":
        $txt1 = "Este año"; $txt2 = "Año pasado";
        $desde1 = date("Y-01-01 00:00:00"); $hasta1 = date("Y-12-31 23:59:59");
        $desde2 = date("Y-01-01 00:00:00", strtotime("-1 year")); $hasta2 = date("Y-12-31 23:59:59", strtotime("-1 year"));
        break;
    case "mes":
    default:
        $txt1 = "Este mes"; $txt2 = "Mes pasado";
        $desde1 = date("Y-m-d 00:00:00", strtotime("first day of this month")); $hasta1 = date("Y-m-d 23:59:59", strtotime("last day of this month"));
        $desde2 = date("Y-m-d 00:00:00", strtotime("first day of previous month")); $hasta2 = date("Y-m-d 23:59:59", strtotime("last day of previous month"));
        break;
}
$txt1_1 = entradas_periodo($local_id, $desde1, $hasta1);
$txt2_2 = entradas_periodo($local_id, $desde2, $hasta2);

// --- Series para el gráfico de líneas (periodo actual vs anterior) ---
// Se calculan desde PHP según $filtro y se inyectan como variables globales
// (v_etiquetas / v_datos1 / v_datos2) antes del canvas. app.js las espera
// como: array de strings (etiquetas) y arrays de números (dos series).
$v_etiquetas = [];
$v_datos1 = [];
$v_datos2 = [];

switch ($filtro) {
    case "dia":
        // 24 franjas horarias: hoy vs ayer
        for ($h = 0; $h < 24; $h++) {
            $hora = str_pad($h, 2, "0", STR_PAD_LEFT);
            $v_etiquetas[] = $hora . ":00";
            $v_datos1[] = entradas_periodo($local_id, date("Y-m-d $hora:00:00"), date("Y-m-d $hora:59:59"));
            $v_datos2[] = entradas_periodo($local_id, date("Y-m-d $hora:00:00", strtotime("-1 day")), date("Y-m-d $hora:59:59", strtotime("-1 day")));
        }
        break;

    case "semana":
        // 7 días: esta semana vs semana pasada
        $dias_es = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"];
        $dias_en = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"];
        for ($i = 0; $i < 7; $i++) {
            $dia = $dias_en[$i];
            $v_etiquetas[] = $dias_es[$i];
            $v_datos1[] = entradas_periodo($local_id, date("Y-m-d 00:00:00", strtotime("$dia this week")), date("Y-m-d 23:59:59", strtotime("$dia this week")));
            $v_datos2[] = entradas_periodo($local_id, date("Y-m-d 00:00:00", strtotime("$dia last week")), date("Y-m-d 23:59:59", strtotime("$dia last week")));
        }
        break;

    case "mes":
        // días del mes en curso: este mes vs mes pasado
        $ultimo_dia = (int)date("t");
        for ($d = 1; $d <= $ultimo_dia; $d++) {
            $dia = str_pad($d, 2, "0", STR_PAD_LEFT);
            $v_etiquetas[] = $dia;
            $v_datos1[] = entradas_periodo($local_id, date("Y-m-$dia 00:00:00"), date("Y-m-$dia 23:59:59"));
            $v_datos2[] = entradas_periodo($local_id, date("Y-m-$dia 00:00:00", strtotime("-1 month")), date("Y-m-$dia 23:59:59", strtotime("-1 month")));
        }
        break;

    case "anyo":
        // 12 meses: este año vs año pasado
        $meses_es = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"];
        $meses_en = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
        for ($m = 1; $m <= 12; $m++) {
            $label = str_pad($m, 2, "0", STR_PAD_LEFT);
            $v_etiquetas[] = $meses_es[$m - 1];
            $v_datos1[] = entradas_periodo($local_id, date("Y-$label-01 00:00:00"), date("Y-$label-01 23:59:59"));
            $v_datos2[] = entradas_periodo($local_id, date("Y-$label-01 00:00:00", strtotime("-1 year")), date("Y-$label-01 23:59:59", strtotime("-1 year")));
        }
        break;
}

// tendencias para los indicadores de las tarjetas
function pct_cambio($actual, $anterior) {
    if ($anterior <= 0) {
        return $actual > 0 ? 100 : 0;
    }
    return round(($actual - $anterior) / $anterior * 100);
}

// Visitas Hoy vs Ayer
$visitas_ayer = entradas_periodo($local_id, date("Y-m-d 00:00:00", strtotime("-1 day")), date("Y-m-d 23:59:59", strtotime("-1 day")));
$pct_visitas = pct_cambio($visitas_hoy, $visitas_ayer);

// Media diaria mes anterior vs mes actual
$media_anterior = 0;
$rows_prev = DB::select(
    "SELECT COUNT(DISTINCT e.persona_id) AS cuenta
     FROM estancias e JOIN camaras c ON c.id = e.camara_id JOIN personas p ON p.id = e.persona_id
     WHERE p.trabajador = 0 AND c.puerta = 1 AND c.local_id = ?
       AND e.created >= ? AND e.created <= ?
     GROUP BY DATE(e.created)",
    [$local_id,
     date("Y-m-d 00:00:00", strtotime("first day of previous month")),
     date("Y-m-d 23:59:59", strtotime("last day of previous month"))]
);
if ($rows_prev) {
    $media_anterior = round(array_sum(array_column($rows_prev, "cuenta")) / count($rows_prev));
}
$pct_media = pct_cambio($visitas_medias_diarias, $media_anterior);

// Recurrentes: mes actual vs mes anterior
$recurrentes_anterior = 0;
$r2 = DB::selectOne(
    "SELECT COUNT(*) AS n FROM (
        SELECT e.persona_id FROM estancias e
        JOIN camaras c ON c.id = e.camara_id JOIN personas p ON p.id = e.persona_id
        WHERE p.trabajador = 0 AND c.puerta = 1 AND c.local_id = ?
          AND e.created >= ? AND e.created <= ?
        GROUP BY e.persona_id HAVING COUNT(DISTINCT DATE(e.fecha_ini)) > 1
     ) t",
    [$local_id,
     date("Y-m-d 00:00:00", strtotime("first day of previous month")),
     date("Y-m-d 23:59:59", strtotime("last day of previous month"))]
);
$recurrentes_anterior = $r2 ? (int)$r2["n"] : 0;
$pct_recurrentes = pct_cambio($visitantes_recurrentes, $recurrentes_anterior);

function tendencia_pill($pct) {
    $clase = $pct >= 0 ? "report-box__indicator--up" : "report-box__indicator--down";
    $signo = $pct > 0 ? "+" : "";
    $valor = $pct == 0 ? "0%" : $signo . $pct . "%";
    $icono = $pct >= 0
        ? '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"></polyline><polyline points="17 6 23 6 23 12"></polyline>'
        : '<polyline points="23 18 13.5 8.5 8.5 13.5 1 6"></polyline><polyline points="17 18 23 18 23 12"></polyline>';
    return '<div class="ml-auto"><div class="report-box__indicator ' . $clase . '">'
        . '<svg class="w-3 h-3 mr-1" xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">' . $icono . '</svg>'
        . $valor . '</div></div>';
}
?>

<div class="col-span-12 mt-8">
    <div class="intro-y flex items-center h-10">
        <h2 class="text-lg font-medium truncate mr-5">⚔️ Crónicas de Guerra</h2>
        <a href="?page=dash" class="ml-auto flex text-theme-1 dark:text-theme-10">🔮 Reinvocar Datos</a>
    </div>
    <div class="grid grid-cols-12 gap-6 mt-5">
        <div class="col-span-12 sm:col-span-6 xl:col-span-3 intro-y">
            <div class="report-box zoom-in">
                <div class="box p-5">
                    <div class="flex">
                        <div class="kpi-chip"><div class="menu__emoji kpi-emoji">👁️</div></div>
                        <div class="ml-auto aforo-control">
                            <span class="live-dot" aria-hidden="true"></span>
                            <input type="text" name="aforo_input" id="aforo_input" class="input border w-20" placeholder="<?= $aforo_actual; ?>" aria-label="Nuevo aforo máximo de la fortaleza" title="Nuevo aforo máximo">
                            <button type="button" class="button text-white bg-theme-1 shadow-md mr-2" onclick="cambiar_aforo()">Actualizar</button>
                        </div>
                    </div>
                    <div class="kpi-number mt-6 tnum"><?= $aforo_actual; ?></div>
                    <div class="kpi-label mt-1">Almas en la Fortaleza <span class="text-xs font-semibold uppercase tracking-wide text-green-600">· en vivo</span></div>
                </div>
            </div>
        </div>
        <div class="col-span-12 sm:col-span-6 xl:col-span-3 intro-y">
            <div class="report-box zoom-in">
                <div class="box p-5">
                    <div class="flex"><div class="kpi-chip"><div class="menu__emoji kpi-emoji">🔥</div></div><?= tendencia_pill($pct_visitas); ?></div>
                    <div class="kpi-number mt-6 tnum"><?= $visitas_hoy; ?></div>
                    <div class="kpi-label mt-1">Cruzaron la Puerta Negra</div>
                </div>
            </div>
        </div>
        <div class="col-span-12 sm:col-span-6 xl:col-span-3 intro-y">
            <div class="report-box zoom-in">
                <div class="box p-5">
                    <div class="flex"><div class="kpi-chip"><div class="menu__emoji kpi-emoji">🛡️</div></div><?= tendencia_pill($pct_media); ?></div>
                    <div class="kpi-number mt-6 tnum"><?= $visitas_medias_diarias; ?></div>
                    <div class="kpi-label mt-1">Huestes al Día</div>
                </div>
            </div>
        </div>
        <div class="col-span-12 sm:col-span-6 xl:col-span-3 intro-y">
            <div class="report-box zoom-in">
                <div class="box p-5">
                    <div class="flex"><div class="kpi-chip"><div class="menu__emoji kpi-emoji">💍</div></div><?= tendencia_pill($pct_recurrentes); ?></div>
                    <div class="kpi-number mt-6 tnum"><?= $visitantes_recurrentes; ?></div>
                    <div class="kpi-label mt-1">Leales a Mordor</div>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="col-span-12 lg:col-span-6 mt-8">
    <div class="intro-y block sm:flex items-center h-10">
        <h2 class="text-lg font-medium truncate mr-5">🗺️ Mapa de Asedio</h2>
    </div>
    <div class="intro-y box p-5 mt-12 sm:mt-5">
        <div class="flex flex-col xl:flex-row xl:items-center">
            <div class="flex">
                <div>
                    <div class="text-theme-20 dark:text-gray-300 text-lg xl:text-xl font-bold" id="datos_actual"><?= $txt1_1; ?></div>
                    <div class="text-gray-600 dark:text-gray-600" id="etiqueta_actual"><?= $txt1; ?></div>
                </div>
                <div class="w-px h-12 border border-r border-dashed border-gray-300 dark:border-dark-5 mx-4 xl:mx-6"></div>
                <div>
                    <div class="text-gray-600 dark:text-gray-600 text-lg xl:text-xl font-medium" id="datos_pasado"><?= $txt2_2; ?></div>
                    <div class="text-gray-600 dark:text-gray-600" id="etiqueta_pasado"><?= $txt2; ?></div>
                </div>
            </div>
            <div class="dropdown relative xl:ml-auto mt-5 xl:mt-0">
                <button class="dropdown-toggle button font-normal border dark:border-dark-5 text-white dark:text-gray-300 relative flex items-center text-gray-700">🕰️ Elegir era</button>
                <div class="dropdown-box mt-10 absolute w-40 top-0 xl:right-0 z-20">
                    <div class="dropdown-box__content box dark:bg-dark-1 p-2 overflow-y-auto h-32">
                        <a href="?page=dash&filtro=dia" class="flex items-center block p-2">Un amanecer</a>
                        <a href="?page=dash&filtro=semana" class="flex items-center block p-2">Una luna</a>
                        <a href="?page=dash&filtro=mes" class="flex items-center block p-2">Un ciclo</a>
                        <a href="?page=dash&filtro=anyo" class="flex items-center block p-2">Una era</a>
                    </div>
                </div>
            </div>
        </div>
        <script>
            // Series del gráfico calculadas en PHP según el filtro elegido.
            // app.js las consume como v_etiquetas / v_datos1 / v_datos2
            // (array de strings + arrays de números, formato idéntico al AJAX).
            var v_etiquetas = <?= json_encode($v_etiquetas, JSON_UNESCAPED_UNICODE); ?>;
            var v_datos1 = <?= json_encode($v_datos1); ?>;
            var v_datos2 = <?= json_encode($v_datos2); ?>;

            // El dashboard es la página por defecto del panel: si la URL no
            // lleva ?page=dash, app.js no detecta la sección y omite la carga
            // de las series (gráfico vacío). Normalizamos la URL sin recargar,
            // ANTES de que se ejecute app.js, para que el gráfico pinte en
            // cualquier vía de entrada (admin/, ?page=, filtro sin page...).
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
        <div class="report-chart">
            <canvas id="report-line-chart" class="mt-6"></canvas>
        </div>
    </div>
</div>
