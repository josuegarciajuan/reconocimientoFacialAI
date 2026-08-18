<?php

/* 
 * Listado de fichajes (REFACTOR Fase 4b): PDO (B9) + fechas correctas (B13) + fix B17 (agregación).
 * Agrupa por trabajador y día: entrada = primera cámara puerta; salida = última cámara salida.
 */

require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/fechas.php";

$local_id = (int)$_SESSION["local_id"];
$camara_filtro = (isset($_GET["camara"]) && $_GET["camara"] !== "" && $_GET["camara"] !== "-") ? (int)$_GET["camara"] : 0;
$persona_filtro = (isset($_GET["persona_id"]) && $_GET["persona_id"] !== "" && $_GET["persona_id"] !== "-") ? (int)$_GET["persona_id"] : 0;

$desde_sql = rango_a_sql($_GET["desde"] ?? "", date("Y-m-d 00:00:00"));
$hasta_sql = rango_a_sql($_GET["hasta"] ?? "", date("Y-m-d 23:59:59"));
$desde = $_GET["desde"] ?? (date("n/d") . " 12:01 AM");
$hasta = $_GET["hasta"] ?? (date("n/d") . " 12:59 PM");

$trabajadores = DB::select(
    "SELECT p.id, p.cod_interno, p.nombre FROM personas p
     WHERE p.trabajador = 1 AND p.id IN (SELECT persona_id FROM estancias WHERE camara_id IN (SELECT id FROM camaras WHERE local_id = ?))
     ORDER BY p.nombre ASC, p.cod_interno ASC",
    [$local_id]
);
?>

<div class="intro-y flex flex-col sm:flex-row items-center mt-8">
    <h2 class="text-lg font-medium mr-auto">Listado Fichajes</h2>
    <div class="filter-bar mt-4 sm:mt-0">
        <div class="filter-item">
            <label for="persona_id">Trabajador</label>
            <select class="input border" id="persona_id">
                <option value="-" <?php if (!$persona_filtro) { echo "selected='selected'"; } ?>>Todos</option>
                <?php foreach ($trabajadores as $t): ?>
                    <option value="<?= $t["id"]; ?>" <?php if ($persona_filtro === (int)$t["id"]) { echo "selected='selected'"; } ?>><?= htmlspecialchars($t["cod_interno"] . " - " . $t["nombre"]); ?></option>
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
    <table class="table table-report table-report--bordered display datatable w-full">
        <thead>
            <tr>
                <th class="border-b-2 text-center">TRABAJADOR</th>
                <th class="border-b-2 text-center">ENTRADA</th>
                <th class="border-b-2 text-center">CÁMARA</th>
                <th class="border-b-2 text-center">FOTO</th>
                <th class="border-b-2 text-center">SALIDA</th>
                <th class="border-b-2 text-center">CÁMARA</th>
                <th class="border-b-2 text-center">FOTO</th>
            </tr>
        </thead>
        <tbody>
        <?php
        $where = ["p.trabajador = 1", "(c.puerta = 1 OR c.salida = 1)", "c.local_id = ?", "e.fecha_ini >= ?", "e.fecha_ini <= ?"];
        $params = [$local_id, $desde_sql, $hasta_sql];
        if ($camara_filtro) { $where[] = "e.camara_id = ?"; $params[] = $camara_filtro; }
        if ($persona_filtro) { $where[] = "e.persona_id = ?"; $params[] = $persona_filtro; }

        $rows = DB::select(
            "SELECT e.id AS eid, e.persona_id, e.fecha_ini, p.cod_interno, p.nombre, c.descripcion, c.puerta, c.salida
             FROM estancias e
             JOIN personas p ON p.id = e.persona_id
             JOIN camaras c ON c.id = e.camara_id
             WHERE " . implode(" AND ", $where) . " ORDER BY e.fecha_ini ASC",
            $params
        );

        // agrupar por persona + día (fecha corta)
        $data = [];
        foreach ($rows as $r) {
            $key = $r["persona_id"] . "|" . substr($r["fecha_ini"], 0, 10);
            if (!isset($data[$key])) {
                $data[$key] = [
                    "cod_interno" => $r["cod_interno"],
                    "nombre" => $r["nombre"],
                    "entrada" => "",
                    "camara_entrada" => "",
                    "foto_entrada" => "",
                    "salida" => "",
                    "camara_salida" => "",
                    "foto_salida" => "",
                ];
            }
            $foto = DB::selectOne("SELECT " . (((int)$r["puerta"] === 1) ? "MIN" : "MAX") . "(id) AS fid FROM fotos WHERE estancia_id = ?", [(int)$r["eid"]]);
            $img = "./caras_procesadas/" . ($foto && $foto["fid"] ? $foto["fid"] : 0) . ".jpg";
            if ((int)$r["puerta"] === 1) {
                if ($data[$key]["entrada"] === "") {  // primera entrada (orden asc)
                    $data[$key]["entrada"] = $r["fecha_ini"];
                    $data[$key]["camara_entrada"] = $r["descripcion"];
                    $data[$key]["foto_entrada"] = $img;
                }
            } else {
                $data[$key]["salida"] = $r["fecha_ini"];        // última salida (sobrescribe)
                $data[$key]["camara_salida"] = $r["descripcion"];
                $data[$key]["foto_salida"] = $img;
            }
        }

        $js_quote = function ($s) {
            return htmlspecialchars(str_replace(["\\", "'"], ["\\\\", "\\'"], (string)$s), ENT_QUOTES);
        };
        $par = "odd";
        foreach ($data as $d) {
            $nombre = ($d["nombre"] !== "") ? $d["nombre"] : $d["cod_interno"];
            $entrada_fmt = ($d["entrada"] !== "") ? date("d/m/Y H:i", strtotime($d["entrada"])) : "—";
            $salida_fmt  = ($d["salida"] !== "") ? date("d/m/Y H:i", strtotime($d["salida"])) : "—";
        ?>
            <tr class="<?= $par; ?>">
                <td class="text-center border-b"><?= htmlspecialchars($d["cod_interno"] . " - " . $nombre); ?></td>
                <td class="text-center border-b"><?= htmlspecialchars($entrada_fmt); ?></td>
                <td class="text-center border-b"><?= htmlspecialchars($d["camara_entrada"]); ?></td>
                <td class="text-center border-b">
                    <?php if ($d["foto_entrada"] !== ""): ?>
                    <img alt="Foto de entrada de <?= htmlspecialchars($nombre); ?>" onclick="verFoto('<?= $js_quote($d["foto_entrada"]); ?>','Entrada · <?= $js_quote($nombre); ?>')" onerror="this.style.display='none'" class="img-thumb cursor-pointer" src="<?= htmlspecialchars($d["foto_entrada"]); ?>">
                    <?php else: ?>
                    <span class="text-gray-500 dark:text-gray-500">—</span>
                    <?php endif; ?>
                </td>
                <td class="text-center border-b"><?= htmlspecialchars($salida_fmt); ?></td>
                <td class="text-center border-b"><?= htmlspecialchars($d["camara_salida"]); ?></td>
                <td class="text-center border-b">
                    <?php if ($d["foto_salida"] !== ""): ?>
                    <img alt="Foto de salida de <?= htmlspecialchars($nombre); ?>" onclick="verFoto('<?= $js_quote($d["foto_salida"]); ?>','Salida · <?= $js_quote($nombre); ?>')" onerror="this.style.display='none'" class="img-thumb cursor-pointer" src="<?= htmlspecialchars($d["foto_salida"]); ?>">
                    <?php else: ?>
                    <span class="text-gray-500 dark:text-gray-500">—</span>
                    <?php endif; ?>
                </td>
            </tr>
        <?php
            $par = ($par === "odd") ? "pair" : "odd";
        }
        ?>
        </tbody>
    </table>
</div>
