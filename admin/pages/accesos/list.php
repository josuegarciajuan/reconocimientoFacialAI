<?php

/* 
 * Listado de movimientos/accesos (REFACTOR Fase 4b): PDO (B9) + fechas correctas (B13).
 */

require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/fechas.php";
require_once __DIR__ . "/../../../libs/etiquetas.php";

$local_id = (int)$_SESSION["local_id"];
$camara_filtro = (isset($_GET["camara"]) && $_GET["camara"] !== "" && $_GET["camara"] !== "-") ? (int)$_GET["camara"] : 0;
$persona_filtro = (isset($_GET["persona_id"]) && $_GET["persona_id"] !== "" && $_GET["persona_id"] !== "-") ? (int)$_GET["persona_id"] : 0;

// Rango por defecto: últimas 24h (desde hace 24h hasta ahora) para que el listado nunca arranque vacío.
$ahora = time();
$desde = $_GET["desde"] ?? date("n/d h:i A", $ahora - 86400);
$hasta = $_GET["hasta"] ?? date("n/d h:i A", $ahora);
$desde_sql = rango_a_sql($desde, date("Y-m-d H:i:s", $ahora - 86400));
$hasta_sql = rango_a_sql($hasta, date("Y-m-d H:i:s", $ahora));

$camaras = DB::select("SELECT id, descripcion FROM camaras WHERE local_id = ?", [$local_id]);
$personas = DB::select(
    "SELECT p.id, p.cod_interno, p.nombre FROM personas p
     WHERE p.id IN (SELECT persona_id FROM estancias WHERE camara_id IN (SELECT id FROM camaras WHERE local_id = ?))
     ORDER BY p.nombre ASC, p.cod_interno ASC",
    [$local_id]
);

// vídeos de movimiento del local en el rango (para enlazar "Ver vídeo" por estancia)
$videos = DB::select(
    "SELECT id, camara_id, fecha_ini, fecha_fin, poster FROM videos WHERE local_id = ? AND fecha_ini BETWEEN ? AND ? ORDER BY fecha_ini ASC",
    [$local_id, $desde_sql, $hasta_sql]
);
$videos_por_cam = [];
foreach ($videos as $v) {
    $videos_por_cam[(int)$v["camara_id"]][] = $v;
}
?>

<div class="intro-y flex flex-col sm:flex-row items-center mt-8">
    <h2 class="text-lg font-medium mr-auto">Listado Movimientos</h2>
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
            <label for="persona_id">Persona</label>
            <select class="input border" id="persona_id">
                <option value="-" <?php if (!$persona_filtro) { echo "selected='selected'"; } ?>>Todos</option>
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
        <button class="button text-white bg-theme-1 shadow-md" onclick="buscarHoy()">Hoy</button>
    </div>
</div>

<div class="intro-y datatable-wrapper box p-5 mt-5 table-wrap">
    <table class="table table-report table-report--bordered display datatable w-full">
        <thead>
            <tr>
                <th class="border-b-2 text-center">HORA</th>
                <th class="border-b-2 text-center">PERSONA</th>
                <th class="border-b-2 text-center">CÁMARA</th>
                <th class="border-b-2 text-center">FOTOS</th>
                <th class="border-b-2 text-center">VÍDEO</th>
                <th class="border-b-2 text-center">TIEMPO</th>
            </tr>
        </thead>
        <tbody>
        <?php
        $where = ["e.fecha_ini >= ?", "e.fecha_ini <= ?"];
        $params = [$desde_sql, $hasta_sql];
        if ($camara_filtro) { $where[] = "e.camara_id = ?"; $params[] = $camara_filtro; }
        else { $where[] = "e.camara_id IN (SELECT id FROM camaras WHERE local_id = ?)"; $params[] = $local_id; }
        if ($persona_filtro) { $where[] = "e.persona_id = ?"; $params[] = $persona_filtro; }

        $rows = DB::select(
            "SELECT e.id, e.fecha_ini, e.fecha_fin, e.persona_id, e.camara_id, p.cod_interno, p.nombre, c.descripcion AS camara_nombre
             FROM estancias e
             JOIN personas p ON p.id = e.persona_id
             JOIN camaras c ON c.id = e.camara_id
             WHERE " . implode(" AND ", $where) . " ORDER BY e.fecha_ini DESC",
            $params
        );

        $js_quote = function ($s) {
            return htmlspecialchars(str_replace(["\\", "'"], ["\\\\", "\\'"], (string)$s), ENT_QUOTES);
        };
        $par = "odd";
        foreach ($rows as $r) {
            $nombre = ($r["nombre"] !== "") ? $r["nombre"] : $r["cod_interno"];
            $tiempo = max(1, strtotime($r["fecha_fin"]) - strtotime($r["fecha_ini"]));
            $fotos = DB::select("SELECT id FROM fotos WHERE estancia_id = ? ORDER BY id ASC", [(int)$r["id"]]);
            $imagen1 = isset($fotos[0]) ? "./caras_procesadas/" . $fotos[0]["id"] . ".jpg" : "";
            $imagen2 = isset($fotos[1]) ? "./caras_procesadas/" . $fotos[1]["id"] . ".jpg" : "";
            // vídeo de movimiento más cercano en el tiempo (misma cámara, margen configurable).
            // Distancia entre intervalos [fecha_ini,fecha_fin]: 0 si solapan (lo normal,
            // el vídeo cubre el movimiento), si no la separación entre intervalos.
            $video_id = 0;
            $ts_ini = strtotime($r["fecha_ini"]);
            $ts_fin = strtotime($r["fecha_fin"]) ?: $ts_ini;
            if ($ts_ini && isset($videos_por_cam[(int)$r["camara_id"]])) {
                $mejor = null;
                $mejor_d = PHP_INT_MAX;
                foreach ($videos_por_cam[(int)$r["camara_id"]] as $v) {
                    $v_ini = strtotime($v["fecha_ini"]);
                    $v_fin = strtotime((string)($v["fecha_fin"] ?? "")) ?: $v_ini;
                    if ($v_ini === false) { continue; }
                    if ($ts_fin < $v_ini) { $d = $v_ini - $ts_fin; }
                    elseif ($v_fin < $ts_ini) { $d = $ts_ini - $v_fin; }
                    else { $d = 0; }
                    if ($d < $mejor_d) { $mejor_d = $d; $mejor = $v; }
                }
                if ($mejor !== null && $mejor_d <= (int)CONFIG_VIDEO_MARGEN_ESTANCIA) {
                    $video_id = (int)$mejor["id"];
                }
            }
            $ts = strtotime($r["fecha_ini"]);
            $fecha_fmt = $ts ? date("d/m/Y H:i:s", $ts) : $r["fecha_ini"];
        ?>
            <tr class="<?= $par; ?>">
                <td class="text-center border-b"><?= htmlspecialchars($fecha_fmt); ?></td>
                <td class="text-center border-b">
                    <a class="text-theme-1 font-medium hover:underline" href="?page=visitantes&mode=editar&id=<?= (int)$r["persona_id"]; ?>" title="Ver la ficha de la persona"><?= htmlspecialchars($nombre); ?></a>
                </td>
                <td class="text-center border-b"><?= camara_link((int)$r["camara_id"], $r["camara_nombre"]); ?></td>
                <td class="text-center border-b">
                    <div class="flex sm:justify-center">
                        <?php if ($imagen1 !== ""): ?>
                        <img alt="Foto 1 de <?= htmlspecialchars($nombre); ?>" onclick="verFoto('<?= $js_quote($imagen1); ?>','<?= $js_quote($nombre); ?>')" onerror="this.style.display='none'" class="img-thumb cursor-pointer -mr-2" src="<?= htmlspecialchars($imagen1); ?>">
                        <?php endif; ?>
                        <?php if ($imagen2 !== ""): ?>
                        <img alt="Foto 2 de <?= htmlspecialchars($nombre); ?>" onclick="verFoto('<?= $js_quote($imagen2); ?>','<?= $js_quote($nombre); ?>')" onerror="this.style.display='none'" class="img-thumb cursor-pointer border border-gray-700 dark:border-gray-700" src="<?= htmlspecialchars($imagen2); ?>">
                        <?php endif; ?>
                    </div>
                </td>
                <td class="text-center border-b">
                    <?php if ($video_id > 0): ?>
                    <a href="javascript:;" title="Ver el vídeo del movimiento"
                       onclick="rfVideoModal(<?= $video_id; ?>,'../video.php?id=<?= $video_id; ?>','<?= $js_quote("../video.php?id=" . $video_id . "&poster=1"); ?>','<?= $js_quote($nombre); ?> · <?= $js_quote(camara_label($r["camara_nombre"])); ?>',<?= (int)$r["persona_id"]; ?>,'<?= $js_quote($nombre); ?>')">
                        <img alt="Miniatura del vídeo de <?= htmlspecialchars($nombre); ?>"
                             src="../video.php?id=<?= $video_id; ?>&poster=1"
                             onerror="this.onerror=null;this.outerHTML='<span class=\'text-theme-1 font-medium text-xs underline cursor-pointer\'>▶ Ver</span>';"
                             class="video-thumb cursor-pointer">
                    </a>
                    <?php else: ?>
                    <span class="text-xs text-gray-500 dark:text-gray-600">—</span>
                    <?php endif; ?>
                </td>
                <td class="text-center border-b"><?= formato_duracion($tiempo); ?></td>
            </tr>
        <?php
            $par = ($par === "odd") ? "pair" : "odd";
        }
        ?>
        </tbody>
    </table>
</div>
