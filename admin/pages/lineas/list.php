<?php

/* 
 * Listado de cruces de línea (REFACTOR Fase 4b): PDO (B9) + fechas correctas (B13).
 */

require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/fechas.php";
require_once __DIR__ . "/../../../libs/etiquetas.php";

$local_id = (int)$_SESSION["local_id"];

$camara_filtro = (isset($_GET["camara"]) && $_GET["camara"] !== "" && $_GET["camara"] !== "-") ? (int)$_GET["camara"] : 0;
$linea_filtro = (isset($_GET["linea"]) && $_GET["linea"] !== "" && $_GET["linea"] !== "-") ? (int)$_GET["linea"] : 0;
$trayectoria = (isset($_GET["trayectoria"]) && $_GET["trayectoria"] !== "" && $_GET["trayectoria"] !== "-") ? (int)$_GET["trayectoria"] : 0;
$persona_filtro = (isset($_GET["persona_id"]) && $_GET["persona_id"] !== "" && $_GET["persona_id"] !== "-") ? (int)$_GET["persona_id"] : 0;

$desde_sql = rango_a_sql($_GET["desde"] ?? "", date("Y-m-d 00:00:00"));
$hasta_sql = rango_a_sql($_GET["hasta"] ?? "", date("Y-m-d 23:59:59"));
$desde = $_GET["desde"] ?? (date("n/d") . " 12:01 AM");
$hasta = $_GET["hasta"] ?? (date("n/d") . " 12:59 PM");

$camaras = DB::select("SELECT id, descripcion FROM camaras WHERE local_id = ?", [$local_id]);

// personas del local (para el filtro por persona en cruces)
$personas = DB::select(
    "SELECT p.id, p.cod_interno, p.nombre FROM personas p
     WHERE p.id IN (SELECT persona_id FROM estancias WHERE camara_id IN (SELECT id FROM camaras WHERE local_id = ?))
     ORDER BY p.nombre ASC, p.cod_interno ASC",
    [$local_id]
);

// líneas (opcionalmente filtradas por cámara)
$lineas_where = "camara_id IN (SELECT id FROM camaras WHERE local_id = ?)";
$lineas_params = [$local_id];
if ($camara_filtro) {
    $lineas_where = "camara_id = ?";
    $lineas_params = [$camara_filtro];
}
$lineas = DB::select("SELECT id, nombre FROM lineas WHERE " . $lineas_where, $lineas_params);
?>

<div class="intro-y flex flex-col sm:flex-row items-center mt-8">
    <h2 class="text-lg font-medium mr-auto">Listado Cruces Lineas</h2>
    <div class="filter-bar mt-4 sm:mt-0">
        <div class="filter-item">
            <label for="camara">Cámara</label>
            <select class="input border" id="camara">
                <option value="-" <?php if (!$camara_filtro) { echo "selected='selected'"; } ?>>Todas</option>
                <?php foreach ($camaras as $c): ?>
                    <option value="<?= $c["id"]; ?>" <?php if ($camara_filtro === (int)$c["id"]) { echo "selected='selected'"; } ?>><?= htmlspecialchars(camara_label($c["descripcion"])); ?></option>
                <?php endforeach; ?>
            </select>
        </div>
        <div class="filter-item">
            <label for="linea">Línea</label>
            <select class="input border" id="linea">
                <option value="-" <?php if (!$linea_filtro) { echo "selected='selected'"; } ?>>Todas</option>
                <?php foreach ($lineas as $l): ?>
                    <option value="<?= $l["id"]; ?>" <?php if ($linea_filtro === (int)$l["id"]) { echo "selected='selected'"; } ?>><?= htmlspecialchars($l["nombre"]); ?></option>
                <?php endforeach; ?>
            </select>
        </div>
        <div class="filter-item">
            <label for="trayectoria">Dirección</label>
            <select class="input border" id="trayectoria">
                <option value="-" <?php if (!$trayectoria) { echo "selected='selected'"; } ?>>Todas</option>
                <option value="2" <?php if ($trayectoria === 2) { echo "selected='selected'"; } ?>>→ Izquierda a Derecha</option>
                <option value="1" <?php if ($trayectoria === 1) { echo "selected='selected'"; } ?>>← Derecha a Izquierda</option>
            </select>
        </div>
        <div class="filter-item">
            <label for="persona_id">Persona</label>
            <select class="input border" id="persona_id">
                <option value="-" <?php if (!$persona_filtro) { echo "selected='selected'"; } ?>>Todas</option>
                <?php foreach ($personas as $p): ?>
                    <option value="<?= $p["id"]; ?>" <?php if ($persona_filtro === (int)$p["id"]) { echo "selected='selected'"; } ?>><?= htmlspecialchars(persona_label($p["nombre"], $p["cod_interno"])); ?></option>
                <?php endforeach; ?>
            </select>
        </div>
        <div class="filter-item">
            <label for="desde">Desde</label>
            <input data-timepicker="true" class="datepicker input border w-32" id="desde" value="<?= $desde; ?>">
        </div>
        <div class="filter-item">
            <label for="hasta">Hasta</label>
            <input data-timepicker="true" class="datepicker input border w-32" id="hasta" value="<?= $hasta; ?>">
        </div>
        <button class="button text-white bg-theme-1 shadow-md" onclick="buscar()">Buscar</button>
    </div>
</div>

<div class="intro-y datatable-wrapper box p-5 mt-5 table-wrap">
        <table class="table table-report table-report--bordered display datatable w-full" data-datatable-source="lineas" data-filters="camara,linea,trayectoria,persona_id,desde,hasta">
        <thead>
            <tr>
                <th class="border-b-2 text-center">HORA</th>
                <th class="border-b-2 text-center">CÁMARA</th>
                <th class="border-b-2 text-center">LINEA</th>
                <th class="border-b-2 text-center">DIRECCION</th>
                <th class="border-b-2 text-center">PERSONA</th>
                <th class="border-b-2 text-center">VÍDEO</th>
                <th class="border-b-2 text-center">FOTOS</th>
            </tr>
        </thead>
        <tbody></tbody>
        <?php if (false) {
        $where = ["cl.fecha >= ?", "cl.fecha <= ?"];
        $params = [$desde_sql, $hasta_sql];

        if ($camara_filtro) { $where[] = "cl.linea_id IN (SELECT id FROM lineas WHERE camara_id = ?)"; $params[] = $camara_filtro; }
        if ($linea_filtro) { $where[] = "cl.linea_id = ?"; $params[] = $linea_filtro; }
        if ($trayectoria) { $where[] = "cl.direccion = ?"; $params[] = $trayectoria; }
        if ($persona_filtro) { $where[] = "cl.persona_id = ?"; $params[] = $persona_filtro; }
        if (!$camara_filtro && !$linea_filtro && !$trayectoria && !$persona_filtro) {
            $where[] = "cl.linea_id IN (SELECT id FROM lineas WHERE camara_id IN (SELECT id FROM camaras WHERE local_id = ?))";
            $params[] = $local_id;
        }

        $cruces = DB::select(
            "SELECT cl.id, cl.linea_id, cl.direccion, cl.identificador, cl.fecha,
                    cl.persona_id, cl.video_id,
                    l.nombre AS linea_nombre, c.descripcion AS camara_nombre, c.id AS camara_id,
                    p.nombre AS persona_nombre, p.cod_interno AS persona_cod,
                    v.poster AS video_poster, v.nombre AS video_nombre
             FROM cruces_lineas cl
             LEFT JOIN lineas l ON l.id = cl.linea_id
             LEFT JOIN camaras c ON c.id = l.camara_id
             LEFT JOIN personas p ON p.id = cl.persona_id
             LEFT JOIN videos v ON v.id = cl.video_id
             WHERE " . implode(" AND ", $where) . " ORDER BY cl.created DESC",
            $params
        );

        $js_quote = function ($s) {
            return htmlspecialchars(str_replace(["\\", "'"], ["\\\\", "\\'"], (string)$s), ENT_QUOTES);
        };
        $par = "odd";
        foreach ($cruces as $cr) {
            // Convención del panel (legado): 1 = de derecha a izquierda, 2 = de izquierda a derecha (pantalla).
            $dir_flecha = ((int)$cr["direccion"] === 1) ? "←" : "→";
            $dir_texto  = ((int)$cr["direccion"] === 1) ? "Derecha a Izquierda" : "Izquierda a Derecha";
            $imagen = URL_BASE_SERVER . "motor/fotos_lineas/" . $cr["linea_id"] . "/" . $cr["identificador"] . ".jpg";
            $ts = strtotime($cr["fecha"]);
            $fecha_fmt = $ts ? date("d/m/Y H:i:s", $ts) : $cr["fecha"];
            // persona vinculada (FK nullable: puede no existir)
            $persona_id_cruce = (int)($cr["persona_id"] ?? 0);
            $persona_nombre = ($persona_id_cruce > 0)
                ? (($cr["persona_nombre"] ?? "") !== "" ? $cr["persona_nombre"] : $cr["persona_cod"])
                : "";
            // vídeo de movimiento vinculado (FK nullable)
            $video_id_cruce = (int)($cr["video_id"] ?? 0);
        ?>
            <tr class="<?= $par; ?>">
                <td class="text-center border-b"><?= htmlspecialchars($fecha_fmt); ?></td>
                <td class="text-center border-b"><?= camara_link((int)($cr["camara_id"] ?? 0), $cr["camara_nombre"] ?? ""); ?></td>
                <td class="text-center border-b"><?= htmlspecialchars($cr["linea_nombre"] ?? ""); ?></td>
                <td class="text-center border-b">
                    <span class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-semibold bg-gray-800 dark:bg-gray-900 text-gray-300 border border-gray-700 dark:border-gray-700">
                        <span aria-hidden="true"><?= $dir_flecha; ?></span><?= $dir_texto; ?>
                    </span>
                </td>
                <td class="text-center border-b">
                    <?php if ($persona_id_cruce > 0): ?>
                    <a class="text-theme-1 font-medium hover:underline" href="?page=visitantes&mode=editar&id=<?= $persona_id_cruce; ?>">
                        <?= htmlspecialchars($persona_nombre); ?>
                    </a>
                    <?php else: ?>
                    <span class="text-xs text-gray-500 dark:text-gray-600">—</span>
                    <?php endif; ?>
                </td>
                <td class="text-center border-b">
                    <?php if ($video_id_cruce > 0): ?>
                    <a href="javascript:;" title="Ver el vídeo del movimiento"
                       onclick="rfVideoModal(<?= $video_id_cruce; ?>,'../video.php?id=<?= $video_id_cruce; ?>','<?= $js_quote("../video.php?id=" . $video_id_cruce . "&poster=1"); ?>','<?= $js_quote("Cruce · " . ($cr["linea_nombre"] ?? "Línea")); ?>',<?= $persona_id_cruce; ?>,<?= $persona_id_cruce > 0 ? "'" . $js_quote($persona_nombre) . "'" : "0"; ?>)">
                        <img alt="Miniatura del vídeo del cruce"
                             src="../video.php?id=<?= $video_id_cruce; ?>&poster=1"
                             onerror="this.onerror=null;this.outerHTML='<span class=\'text-theme-1 font-medium text-xs underline cursor-pointer\'>▶ Ver</span>';"
                             class="video-thumb cursor-pointer">
                    </a>
                    <?php else: ?>
                    <span class="text-xs text-gray-500 dark:text-gray-600">—</span>
                    <?php endif; ?>
                </td>
                <td class="text-center border-b">
                    <div class="flex sm:justify-center">
                        <img alt="Foto del cruce en <?= htmlspecialchars($cr["linea_nombre"] ?? "línea"); ?>" onclick="verFoto('<?= $js_quote($imagen); ?>','Cruce · <?= $js_quote($cr["linea_nombre"] ?? "Línea"); ?>')" onerror="this.style.display='none'" class="img-thumb cursor-pointer" src="<?= htmlspecialchars($imagen); ?>">
                    </div>
                </td>
            </tr>
        <?php
            $par = ($par === "odd") ? "pair" : "odd";
        }
        } ?>
    </table>
</div>
