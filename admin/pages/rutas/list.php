<?php
/*
 * Caminos — listado + player (rediseño de Rutas).
 * Lista los recorridos de personas y reproduce el camino de cada una sobre el
 * plano con un monigote animado (cabeza = avatar recortado transparente).
 * Lógica en libs/rutas.php y libs/trayectoria.php; aquí solo filtros + render.
 */

require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/fechas.php";
require_once __DIR__ . "/../../../libs/rutas.php";
require_once __DIR__ . "/../../../libs/trayectoria.php";
require_once __DIR__ . "/../../../libs/planos.php";
require_once __DIR__ . "/../../../libs/lineas_plano.php";
require_once __DIR__ . "/../../../libs/etiquetas.php";

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
$rutas_data = [];
$num_puerta = count(camaras_puerta_salida($local_id)[0]);
$rutas_json = '[]';

// --- plano de fondo (activo: imagen subida o croquis dibujado) ---
$plano_url = plano_url($local_id);

// --- cámaras para pintar ---
$camaras_data = DB::select("SELECT id, descripcion, x, y FROM camaras WHERE local_id = ? ORDER BY id ASC", [$local_id]);
$camaras_json = json_encode($camaras_data, JSON_UNESCAPED_UNICODE);

// --- líneas del plano (con su línea de cámara vinculada) para el mapa ---
$lineas_plano_json = json_encode(lineas_plano_del_local($local_id), JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);

// --- personas para el filtro ---
$personas_opciones = DB::select(
    "SELECT p.id, p.cod_interno, p.nombre FROM personas p
     WHERE p.id IN (SELECT persona_id FROM estancias WHERE camara_id IN (SELECT id FROM camaras WHERE local_id = ?))
     ORDER BY p.nombre ASC, p.cod_interno ASC",
    [$local_id]
);
?>

<div class="intro-y flex flex-col sm:flex-row items-center mt-8">
    <h2 class="text-lg font-medium mr-auto">Caminos</h2>
    <div class="filter-bar mt-4 sm:mt-0">
        <div class="filter-item">
            <label for="persona_id">Persona</label>
            <select class="input border" id="persona_id">
                <option value="-" <?php if (!isset($_GET["persona_id"]) || $_GET["persona_id"] === "-") { echo "selected='selected'"; } ?>>Todos</option>
                <?php foreach ($personas_opciones as $p): ?>
                    <option value="<?= $p["id"]; ?>" <?php if (isset($_GET["persona_id"]) && $_GET["persona_id"] == $p["id"]) { echo "selected='selected'"; } ?>>
                        <?= htmlspecialchars(persona_label($p["nombre"], $p["cod_interno"])); ?>
                    </option>
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
    <table class="table table-report table-report--bordered display datatable w-full" data-ajax="rutas" data-filters="persona_id,desde,hasta">
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
        <tbody></tbody>
        <?php if (false) { ?>
        <?php if ($num_puerta === 0): ?>
            <tr><td colspan="6" class="text-center py-8 text-gray-500 dark:text-gray-500">No hay cámaras de entrada (puerta) configuradas en este local.</td></tr>
        <?php elseif (count($rutas_data) === 0): ?>
            <tr><td colspan="6" class="text-center py-8 text-gray-500 dark:text-gray-500">No hay caminos para el filtro seleccionado.</td></tr>
        <?php else: ?>
            <?php
            $js_quote = function ($s) {
                return htmlspecialchars(str_replace(["\\", "'"], ["\\\\", "\\'"], (string)$s), ENT_QUOTES);
            };
            $par = "odd";
            foreach ($rutas_data as $i => $r):
                $ts_ini = strtotime($r["inicio"]);
                $ts_fin = strtotime($r["fin"]);
                $inicio_fmt = $ts_ini ? date("d/m/Y H:i", $ts_ini) : $r["inicio"];
                $fin_fmt = $ts_fin ? date("d/m/Y H:i", $ts_fin) : $r["fin"];
                $num_videos = count(array_filter($r["puntos"], fn($p) => !empty($p["video_id"])));
            ?>
                <tr class="<?= $par; ?>">
                    <td class="text-center border-b"><?= htmlspecialchars($inicio_fmt); ?></td>
                    <td class="text-center border-b"><?= htmlspecialchars($fin_fmt); ?></td>
                    <td class="text-center border-b">
                        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-center gap-1 sm:gap-2">
                            <span><?= persona_link((int)$r["persona_id"], $r["nombre"]); ?></span>
                            <img alt="Foto de <?= htmlspecialchars($r["nombre"]); ?>" onclick="verFoto('<?= $js_quote($r["imagen"]); ?>','<?= $js_quote($r["nombre"]); ?>')" onerror="this.style.display='none'" class="img-thumb cursor-pointer mx-auto sm:mx-0" src="<?= htmlspecialchars($r["imagen"]); ?>">
                        </div>
                    </td>
                    <td class="text-center border-b"><?= $r["num_camaras"]; ?></td>
                    <td class="text-center border-b"><?= htmlspecialchars($r["tiempo"]); ?></td>
                    <td class="text-center border-b">
                        <div class="flex flex-col sm:flex-row sm:justify-center items-center gap-2">
                            <a href="javascript:;" data-toggle="modal" data-target="#basic-modal-preview" onclick="abrirCamino(<?= (int)$r["inicio_id"]; ?>)" class="button inline-block bg-theme-1 text-white">▶ Ver camino</a>
                            <a target="_blank" href="?page=visitantes&mode=editar&id=<?= $r["persona_id"]; ?>" class="button inline-block bg-theme-2 text-white">Ver Persona</a>
                        </div>
                    </td>
                </tr>
                <?php $par = ($par === "odd") ? "pair" : "odd"; ?>
            <?php endforeach; ?>
        <?php endif; ?>
        <?php } ?>
    </table>
</div>

<div class="modal" id="basic-modal-preview">
    <div class="modal__content box p-5 modal__content--xl">
        <div class="flex items-center mb-4">
            <h3 id="caminoTitulo" class="media-modal__title mr-auto truncate">Camino de la persona</h3>
            <a href="javascript:;" data-dismiss="modal" class="button button--sm text-white bg-theme-6 ml-3">Cerrar</a>
        </div>

        <div class="plan-wrap">
            <canvas id="canvasID" width="<?= CANVAS_WIDTH; ?>" height="<?= CANVAS_HEIGHT; ?>" style="border-style:solid;border-width:1px;border-color:var(--mordor-humo);"></canvas>
        </div>

        <!-- ============ Controles del player ============ -->
        <div class="mt-4 flex flex-wrap items-center gap-3">
            <button type="button" id="caminoPlay" class="button text-white bg-theme-1 shadow-md" onclick="PlayerToggle()">▶ Play</button>

            <div class="filter-item">
                <label for="caminoVelocidad">Velocidad</label>
                <select class="input border" id="caminoVelocidad" onchange="PlayerVelocidad(this.value)">
                    <?php foreach (trayectoria_velocidades() as $v): ?>
                        <option value="<?= $v; ?>" <?= $v === 10 ? "selected" : ""; ?>>×<?= $v; ?></option>
                    <?php endforeach; ?>
                </select>
            </div>

            <div class="filter-item">
                <label for="caminoObjetivo">Ver jornada en</label>
                <select class="input border" id="caminoObjetivo" onchange="PlayerObjetivo(this.value)">
                    <option value="60">1 minuto</option>
                    <option value="120" selected>2 minutos</option>
                    <option value="300">5 minutos</option>
                    <option value="0">Velocidad manual</option>
                </select>
            </div>

            <button type="button" id="caminoAvatar" class="button text-white bg-theme-2 shadow-md" onclick="PlayerRegenerarAvatar()">↻ Avatar</button>
        </div>

        <div class="mt-3 flex items-center gap-3">
            <span id="caminoHora" class="text-xs text-gray-500 dark:text-gray-600 whitespace-nowrap">—</span>
            <input type="range" id="caminoScrub" class="w-full" min="0" max="1000" value="0" oninput="PlayerScrub(this.value)">
        </div>

        <div id="caminoPasos" class="mt-3 flex flex-wrap gap-2"></div>
    </div>
</div>
