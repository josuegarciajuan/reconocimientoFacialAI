<?php

/* 
 * Listado de cruces de línea (REFACTOR Fase 4b): PDO (B9) + fechas correctas (B13).
 */

require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/fechas.php";

$local_id = (int)$_SESSION["local_id"];

$camara_filtro = (isset($_GET["camara"]) && $_GET["camara"] !== "" && $_GET["camara"] !== "-") ? (int)$_GET["camara"] : 0;
$linea_filtro = (isset($_GET["linea"]) && $_GET["linea"] !== "" && $_GET["linea"] !== "-") ? (int)$_GET["linea"] : 0;
$trayectoria = (isset($_GET["trayectoria"]) && $_GET["trayectoria"] !== "" && $_GET["trayectoria"] !== "-") ? (int)$_GET["trayectoria"] : 0;

$desde_sql = rango_a_sql($_GET["desde"] ?? "", date("Y-m-d 00:00:00"));
$hasta_sql = rango_a_sql($_GET["hasta"] ?? "", date("Y-m-d 23:59:59"));
$desde = $_GET["desde"] ?? (date("n/d") . " 12:01 AM");
$hasta = $_GET["hasta"] ?? (date("n/d") . " 12:59 PM");

$camaras = DB::select("SELECT id, descripcion FROM camaras WHERE local_id = ?", [$local_id]);

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
    <div class="w-full sm:w-auto flex mt-4 sm:mt-0">

    Cámara:&nbsp;
    <select class="input border mr-2" id="camara">
        <option value="-" <?php if (!$camara_filtro) { echo "selected='selected'"; } ?>>Todas</option>
        <?php foreach ($camaras as $c): ?>
            <option value="<?= $c["id"]; ?>" <?php if ($camara_filtro === (int)$c["id"]) { echo "selected='selected'"; } ?>><?= htmlspecialchars($c["descripcion"]); ?></option>
        <?php endforeach; ?>
    </select>

    Linea:&nbsp;
    <select class="input border mr-2" id="linea">
        <option value="-" <?php if (!$linea_filtro) { echo "selected='selected'"; } ?>>Todas</option>
        <?php foreach ($lineas as $l): ?>
            <option value="<?= $l["id"]; ?>" <?php if ($linea_filtro === (int)$l["id"]) { echo "selected='selected'"; } ?>><?= htmlspecialchars($l["nombre"]); ?></option>
        <?php endforeach; ?>
    </select>

    Trayectoria:&nbsp;
    <select class="input border mr-2" id="trayectoria">
        <option value="-" <?php if (!$trayectoria) { echo "selected='selected'"; } ?>>Todas</option>
        <option value="2" <?php if ($trayectoria === 2) { echo "selected='selected'"; } ?>>-></option>
        <option value="1" <?php if ($trayectoria === 1) { echo "selected='selected'"; } ?>><-</option>
    </select>

    Desde:&nbsp;<input data-timepicker="true" class="datepicker input border mx-auto" id="desde" value="<?= $desde; ?>" style="width:120px">
    Hasta:&nbsp;<input data-timepicker="true" class="datepicker input border mx-auto" id="hasta" value="<?= $hasta; ?>" style="width:120px">
    <button class="button text-white bg-theme-1 shadow-md mr-2" onclick="buscar()">Buscar</button>

    </div>
</div>

<div class="intro-y datatable-wrapper box p-5 mt-5">
    <table class="table table-report table-report--bordered display datatable w-full">
        <thead>
            <tr>
                <th class="border-b-2 text-center">HORA</th>
                <th class="border-b-2 text-center">CÁMARA</th>
                <th class="border-b-2 text-center">LINEA</th>
                <th class="border-b-2 text-center">DIRECCION</th>
                <th class="border-b-2 text-center">FOTOS</th>
                <th class="border-b-2 text-center">ACCIONES</th>
            </tr>
        </thead>
        <tbody>
        <?php
        $where = ["cl.fecha >= ?", "cl.fecha <= ?"];
        $params = [$desde_sql, $hasta_sql];

        if ($camara_filtro) { $where[] = "cl.linea_id IN (SELECT id FROM lineas WHERE camara_id = ?)"; $params[] = $camara_filtro; }
        if ($linea_filtro) { $where[] = "cl.linea_id = ?"; $params[] = $linea_filtro; }
        if ($trayectoria) { $where[] = "cl.direccion = ?"; $params[] = $trayectoria; }
        if (!$camara_filtro && !$linea_filtro && !$trayectoria) {
            $where[] = "cl.linea_id IN (SELECT id FROM lineas WHERE camara_id IN (SELECT id FROM camaras WHERE local_id = ?))";
            $params[] = $local_id;
        }

        $cruces = DB::select(
            "SELECT cl.id, cl.linea_id, cl.direccion, cl.identificador, cl.fecha, l.nombre AS linea_nombre, c.descripcion AS camara_nombre
             FROM cruces_lineas cl
             LEFT JOIN lineas l ON l.id = cl.linea_id
             LEFT JOIN camaras c ON c.id = l.camara_id
             WHERE " . implode(" AND ", $where) . " ORDER BY cl.created DESC",
            $params
        );

        $par = "odd";
        foreach ($cruces as $cr) {
            $direccion = ((int)$cr["direccion"] === 1) ? "<-" : "->";
            $imagen = URL_BASE_SERVER . "motor/fotos_lineas/" . $cr["linea_id"] . "/" . $cr["identificador"] . ".jpg";
        ?>
            <tr class="<?= $par; ?>">
                <td class="border-b" align="center"><?= date("Y-m-d H:i:s", strtotime($cr["fecha"])); ?></td>
                <td class="border-b" align="center"><?= htmlspecialchars($cr["camara_nombre"] ?? ""); ?></td>
                <td class="border-b" align="center"><?= htmlspecialchars($cr["linea_nombre"] ?? ""); ?></td>
                <td class="border-b" align="center"><?= $direccion; ?></td>
                <td class="text-center border-b">
                    <div class="flex sm:justify-center">
                        <div class="intro-x w-10 h-10 image-fit">
                            <img alt="" onclick="scale(this,this.id,1)" src="<?= htmlspecialchars($imagen); ?>" style="position:relative;left:-10px">
                        </div>
                    </div>
                </td>
                <td class="border-b w-5"></td>
            </tr>
        <?php
            $par = ($par === "odd") ? "pair" : "odd";
        }
        ?>
        </tbody>
    </table>
</div>
