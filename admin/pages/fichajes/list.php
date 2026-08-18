<?php

/* 
 * Listado de fichajes (v2): lee la tabla `fichajes` generada por el daemon
 * conciliador.php (rf-conciliador) según el horario del local.
 * Muestra por trabajador y día hasta 2 bloques (jornada partida) con estado
 * provisional (día en curso) o conciliado (día cerrado).
 */

require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/fechas.php";

$local_id = (int)$_SESSION["local_id"];
$persona_filtro = (isset($_GET["persona_id"]) && $_GET["persona_id"] !== "" && $_GET["persona_id"] !== "-") ? (int)$_GET["persona_id"] : 0;

$desde_sql = rango_a_sql($_GET["desde"] ?? "", date("Y-m-d 00:00:00"));
$hasta_sql = rango_a_sql($_GET["hasta"] ?? "", date("Y-m-d 23:59:59"));
$desde_fecha = substr($desde_sql, 0, 10);
$hasta_fecha = substr($hasta_sql, 0, 10);
$desde = $_GET["desde"] ?? (date("n/d") . " 12:01 AM");
$hasta = $_GET["hasta"] ?? (date("n/d") . " 12:59 PM");

$trabajadores = DB::select(
    "SELECT p.id, p.cod_interno, p.nombre FROM personas p
     WHERE p.trabajador = 1 AND p.local_id = ?
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
    <p class="text-xs text-gray-500 dark:text-gray-500 mb-3">
        Generados automáticamente por el conciliador según el horario del local (entrada = primera captura
        del día por cámara de puerta; salida = última por cámara de salida). <strong>Provisional</strong> = día en
        curso (la salida aún puede cambiar); <strong>Conciliado</strong> = día cerrado con salida definitiva.
    </p>
    <table class="table table-report table-report--bordered display datatable w-full">
        <thead>
            <tr>
                <th class="border-b-2 text-center">TRABAJADOR</th>
                <th class="border-b-2 text-center">DÍA</th>
                <th class="border-b-2 text-center">BLOQUE</th>
                <th class="border-b-2 text-center">ENTRADA</th>
                <th class="border-b-2 text-center">CÁMARA</th>
                <th class="border-b-2 text-center">FOTO</th>
                <th class="border-b-2 text-center">SALIDA</th>
                <th class="border-b-2 text-center">CÁMARA</th>
                <th class="border-b-2 text-center">FOTO</th>
                <th class="border-b-2 text-center">DURACIÓN</th>
                <th class="border-b-2 text-center">ESTADO</th>
            </tr>
        </thead>
        <tbody>
        <?php
        $where = ["f.local_id = ?", "f.fecha >= ?", "f.fecha <= ?"];
        $params = [$local_id, $desde_fecha, $hasta_fecha];
        if ($persona_filtro) { $where[] = "f.persona_id = ?"; $params[] = $persona_filtro; }

        $rows = DB::select(
            "SELECT f.id AS fid, f.fecha, f.bloque, f.estado,
                    f.entrada_hora, f.entrada_camara_id, f.entrada_estancia_id,
                    f.salida_hora, f.salida_camara_id, f.salida_estancia_id,
                    p.cod_interno, p.nombre,
                    ce.descripcion AS cam_entrada, cs.descripcion AS cam_salida
             FROM fichajes f
             JOIN personas p ON p.id = f.persona_id
             LEFT JOIN camaras ce ON ce.id = f.entrada_camara_id
             LEFT JOIN camaras cs ON cs.id = f.salida_camara_id
             WHERE " . implode(" AND ", $where) . "
             ORDER BY f.fecha DESC, p.nombre ASC, f.bloque ASC",
            $params
        );

        $js_quote = function ($s) {
            return htmlspecialchars(str_replace(["\\", "'"], ["\\\\", "\\'"], (string)$s), ENT_QUOTES);
        };
        $par = "odd";
        foreach ($rows as $r) {
            $nombre = ($r["nombre"] !== "") ? $r["nombre"] : $r["cod_interno"];

            $foto_entrada = "";
            if ($r["entrada_estancia_id"]) {
                $f = DB::selectOne("SELECT MIN(id) AS fid FROM fotos WHERE estancia_id = ?", [(int)$r["entrada_estancia_id"]]);
                if ($f && $f["fid"]) { $foto_entrada = "./caras_procesadas/" . $f["fid"] . ".jpg"; }
            }
            $foto_salida = "";
            if ($r["salida_estancia_id"]) {
                $f = DB::selectOne("SELECT MAX(id) AS fid FROM fotos WHERE estancia_id = ?", [(int)$r["salida_estancia_id"]]);
                if ($f && $f["fid"]) { $foto_salida = "./caras_procesadas/" . $f["fid"] . ".jpg"; }
            }

            $entrada_fmt = $r["entrada_hora"] ? date("d/m/Y H:i", strtotime($r["entrada_hora"])) : "—";
            $salida_fmt  = $r["salida_hora"] ? date("d/m/Y H:i", strtotime($r["salida_hora"])) : "—";

            $duracion = "—";
            if ($r["entrada_hora"] && $r["salida_hora"]) {
                $duracion = formato_duracion(strtotime($r["salida_hora"]) - strtotime($r["entrada_hora"]));
            }

            $estado_html = ($r["estado"] === "conciliado")
                ? '<span class="px-2 py-1 rounded text-xs bg-green-100 text-green-800 dark:bg-green-800 dark:text-green-100">Conciliado</span>'
                : '<span class="px-2 py-1 rounded text-xs bg-amber-100 text-amber-800 dark:bg-amber-800 dark:text-amber-100">Provisional</span>';
        ?>
            <tr class="<?= $par; ?>">
                <td class="text-center border-b"><?= htmlspecialchars($r["cod_interno"] . " - " . $nombre); ?></td>
                <td class="text-center border-b"><?= htmlspecialchars(date("d/m/Y", strtotime($r["fecha"]))); ?></td>
                <td class="text-center border-b"><?= (int)$r["bloque"]; ?></td>
                <td class="text-center border-b"><?= htmlspecialchars($entrada_fmt); ?></td>
                <td class="text-center border-b"><?= htmlspecialchars($r["cam_entrada"] ?? "—"); ?></td>
                <td class="text-center border-b">
                    <?php if ($foto_entrada !== ""): ?>
                    <img alt="Foto de entrada de <?= htmlspecialchars($nombre); ?>" onclick="verFoto('<?= $js_quote($foto_entrada); ?>','Entrada · <?= $js_quote($nombre); ?>')" onerror="this.style.display='none'" class="img-thumb cursor-pointer" src="<?= htmlspecialchars($foto_entrada); ?>">
                    <?php else: ?>
                    <span class="text-gray-500 dark:text-gray-500">—</span>
                    <?php endif; ?>
                </td>
                <td class="text-center border-b"><?= htmlspecialchars($salida_fmt); ?></td>
                <td class="text-center border-b"><?= htmlspecialchars($r["cam_salida"] ?? "—"); ?></td>
                <td class="text-center border-b">
                    <?php if ($foto_salida !== ""): ?>
                    <img alt="Foto de salida de <?= htmlspecialchars($nombre); ?>" onclick="verFoto('<?= $js_quote($foto_salida); ?>','Salida · <?= $js_quote($nombre); ?>')" onerror="this.style.display='none'" class="img-thumb cursor-pointer" src="<?= htmlspecialchars($foto_salida); ?>">
                    <?php else: ?>
                    <span class="text-gray-500 dark:text-gray-500">—</span>
                    <?php endif; ?>
                </td>
                <td class="text-center border-b"><?= htmlspecialchars($duracion); ?></td>
                <td class="text-center border-b"><?= $estado_html; ?></td>
            </tr>
        <?php
            $par = ($par === "odd") ? "pair" : "odd";
        }
        if (!$rows) {
            echo '<tr class="odd"><td class="text-center border-b py-4 text-gray-500 dark:text-gray-500" colspan="11">Sin fichajes en el rango. El conciliador los genera automáticamente (provisionales durante el día).</td></tr>';
        }
        ?>
        </tbody>
    </table>
</div>
