<?php
/* 
 * Rutas — listado (REFACTOR Fase 3).
 * Lógica en libs/rutas.php; aquí solo filtros + render.
 */

require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/fechas.php";
require_once __DIR__ . "/../../../libs/rutas.php";

// --- filtros (fechas corregidas) ---
$desde_sql = rango_a_sql($_GET["desde"] ?? "", date("Y-m-d 00:00:00"));
$hasta_sql = rango_a_sql($_GET["hasta"] ?? "", date("Y-m-d 23:59:59"));
$desde = $_GET["desde"] ?? (date("n/d") . " 12:01 AM");
$hasta = $_GET["hasta"] ?? (date("n/d") . " 12:59 PM");

$persona_filtro = "";
if (isset($_GET["persona_id"]) && $_GET["persona_id"] !== "" && $_GET["persona_id"] !== "-") {
    $persona_filtro = " and persona_id=" . intval($_GET["persona_id"]);
}

$local_id = intval($_SESSION["local_id"]);
list($rutas_data, $num_puerta) = obtener_rutas($local_id, $desde_sql, $hasta_sql, $persona_filtro);
$rutas_json = json_encode($rutas_data, JSON_UNESCAPED_UNICODE);

// --- plano de fondo ---
$plano_url = "";
foreach (["jpg", "jpeg", "png", "bmp"] as $ext) {
    $p = "pages/config/planos/plano_" . $local_id . "." . $ext;
    if (file_exists($p)) {
        $plano_url = $p;
        break;
    }
}

// --- cámaras para pintar ---
$camaras_data = DB::select("SELECT id, descripcion, x, y FROM camaras WHERE local_id = ? ORDER BY id ASC", [$local_id]);
$camaras_json = json_encode($camaras_data, JSON_UNESCAPED_UNICODE);

// --- personas para el filtro ---
$personas_opciones = DB::select(
    "SELECT p.id, p.cod_interno, p.nombre FROM personas p
     WHERE p.id IN (SELECT persona_id FROM estancias WHERE camara_id IN (SELECT id FROM camaras WHERE local_id = ?))
     ORDER BY p.nombre ASC, p.cod_interno ASC",
    [$local_id]
);
?>

<div class="intro-y flex flex-col sm:flex-row items-center mt-8">
    <h2 class="text-lg font-medium mr-auto">Rutas</h2>
    <div class="w-full sm:w-auto flex mt-4 sm:mt-0">

    Persona:&nbsp;
    <select class="input border mr-2" id="persona_id">
        <option value="-" <?php if (!isset($_GET["persona_id"]) || $_GET["persona_id"] === "-") { echo "selected='selected'"; } ?>>Todos</option>
        <?php foreach ($personas_opciones as $p): ?>
            <option value="<?= $p["id"]; ?>" <?php if (isset($_GET["persona_id"]) && $_GET["persona_id"] == $p["id"]) { echo "selected='selected'"; } ?>>
                <?= htmlspecialchars($p["cod_interno"] . " - " . $p["nombre"]); ?>
            </option>
        <?php endforeach; ?>
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
                <th class="border-b-2 text-center">INICIO</th>
                <th class="border-b-2 text-center">FIN</th>
                <th class="border-b-2 text-center">PERSONA</th>
                <th class="border-b-2 text-center">NUM CÁMARAS</th>
                <th class="border-b-2 text-center">TIEMPO</th>
                <th class="border-b-2 text-center">ACCIONES</th>
            </tr>
        </thead>
        <tbody>
        <?php if ($num_puerta === 0): ?>
            <tr><td colspan="6" align="center">No hay cámaras de entrada (puerta) configuradas en este local.</td></tr>
        <?php elseif (count($rutas_data) === 0): ?>
            <tr><td colspan="6" align="center">No hay rutas para el filtro seleccionado.</td></tr>
        <?php else: ?>
            <?php $par = "odd"; foreach ($rutas_data as $i => $r): ?>
                <tr class="<?= $par; ?>">
                    <td class="border-b" align="center"><?= htmlspecialchars($r["inicio"]); ?></td>
                    <td class="border-b" align="center"><?= htmlspecialchars($r["fin"]); ?></td>
                    <td class="border-b" align="center">
                        <?= htmlspecialchars($r["nombre"]); ?>
                        <div class="flex sm:justify-center">
                            <div class="intro-x w-10 h-10 image-fit">
                                <img alt="" class="rounded-full" src="<?= htmlspecialchars($r["imagen"]); ?>">
                            </div>
                        </div>
                    </td>
                    <td class="border-b" align="center"><?= $r["num_camaras"]; ?></td>
                    <td class="border-b" align="center"><?= htmlspecialchars($r["tiempo"]); ?></td>
                    <td class="border-b w-5">
                        <div class="flex sm:justify-center items-center">
                            <a href="javascript:;" data-toggle="modal" data-target="#basic-modal-preview" onclick="ver_ruta(<?= $i; ?>)" class="button inline-block bg-theme-1 text-white">Ver Ruta</a>
                            <a target="_blank" href="?page=visitantes&mode=editar&id=<?= $r["persona_id"]; ?>" class="button inline-block bg-theme-1 text-white">Ver Persona</a>
                        </div>
                    </td>
                </tr>
                <?php $par = ($par === "odd") ? "pair" : "odd"; ?>
            <?php endforeach; ?>
        <?php endif; ?>
        </tbody>
    </table>
</div>

<div class="modal" id="basic-modal-preview">
    <canvas id="canvasID" width="<?= CANVAS_WIDTH; ?>" height="<?= CANVAS_HEIGHT; ?>" style="position:relative;left:0px;border-style:solid;border-width:1px;border-color:black;z-index:999999"></canvas>
</div>
