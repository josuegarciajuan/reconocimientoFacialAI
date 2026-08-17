<?php

/* 
 * Listado de visitantes (REFACTOR Fase 4b): PDO (B9), fechas correctas (B13), fix alias c.id (B14).
 */

require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/fechas.php";

$local_id = (int)$_SESSION["local_id"];

// filtros
$desde_sql = rango_a_sql($_GET["desde"] ?? "", date("Y-m-d 00:00:00"));
$hasta_sql = rango_a_sql($_GET["hasta"] ?? "", date("Y-m-d 23:59:59"));
$desde = $_GET["desde"] ?? (date("n/d") . " 12:01 AM");
$hasta = $_GET["hasta"] ?? (date("n/d") . " 12:59 PM");

$camara_filtro = (isset($_GET["camara"]) && $_GET["camara"] !== "" && $_GET["camara"] !== "-") ? (int)$_GET["camara"] : 0;
$trabajador_filtro = (isset($_GET["trabajador"]) && $_GET["trabajador"] == 1);
$buscador = trim($_GET["buscador"] ?? "");

// cámaras del local (para el select y para el contador "todas")
$camaras = DB::select("SELECT id, descripcion FROM camaras WHERE local_id = ?", [$local_id]);
$camaras_ids = array_column($camaras, "id");
?>

<div class="intro-y flex flex-col sm:flex-row items-center mt-8">
    <h2 class="text-lg font-medium mr-auto">Listado Visitantes</h2>
    <div class="w-full sm:w-auto flex mt-4 sm:mt-0">

        Trabajadores&nbsp;<input type="checkbox" name="trabajador" id="trabajador" value="1" <?php if ($trabajador_filtro) { echo "checked='checked'"; } ?>>&nbsp;&nbsp;&nbsp;

    Cámara:&nbsp;
    <select class="input border mr-2" id="camara">
        <option value="-" <?php if (!$camara_filtro) { echo "selected='selected'"; } ?>>Todas</option>
        <?php foreach ($camaras as $c): ?>
            <option value="<?= $c["id"]; ?>" <?php if ($camara_filtro === (int)$c["id"]) { echo "selected='selected'"; } ?>><?= htmlspecialchars($c["descripcion"]); ?></option>
        <?php endforeach; ?>
    </select>

    Desde:&nbsp;<input data-timepicker="true" class="datepicker input w-56 border mx-auto" id="desde" value="<?= $desde; ?>">
    Hasta:&nbsp;<input data-timepicker="true" class="datepicker input w-56 border mx-auto" id="hasta" value="<?= $hasta; ?>">
    <button class="button text-white bg-theme-1 shadow-md mr-2" onclick="buscar1()">Buscar</button>
    <button class="button text-white bg-theme-1 shadow-md mr-2" onclick="location.href='?page=visitantes&mode=registrar'">Registrar</button>

    </div>
</div>

<div class="intro-y datatable-wrapper box p-5 mt-5">
    <table class="table table-report table-report--bordered display datatable w-full">
        <thead>
            <tr>
                <th class="border-b-2 text-center">IMAGEN</th>
                <th class="border-b-2 text-center">COD_INTERNO</th>
                <th class="border-b-2 text-center">NOMBRE</th>
                <th class="border-b-2 text-center">ESTANCIAS</th>
                <th class="border-b-2 text-center">ACCIONES</th>
            </tr>
        </thead>
        <tbody>
        <?php
        // consulta principal (ids de persona)
        $where = ["u.local_id = ?"];
        $params = [$local_id];
        $where[] = "a.fecha_ini >= ?"; $params[] = $desde_sql;
        $where[] = "a.fecha_ini <= ?"; $params[] = $hasta_sql;
        if ($camara_filtro) { $where[] = "a.camara_id = ?"; $params[] = $camara_filtro; }
        if ($trabajador_filtro) { $where[] = "u.trabajador = 1"; }
        if ($buscador !== "") {
            $where[] = "(u.nombre LIKE ? OR u.cod_interno LIKE ?)";
            $params[] = "%" . $buscador . "%";
            $params[] = "%" . $buscador . "%";
        }
        $sql_main = "SELECT DISTINCT a.persona_id FROM estancias a JOIN personas u ON u.id = a.persona_id WHERE " . implode(" AND ", $where) . " ORDER BY a.persona_id DESC";
        $persona_ids = DB::select($sql_main, $params);

        $par = "odd";
        foreach ($persona_ids as $prow) {
            $pid = (int)$prow["persona_id"];

            $pers = DB::selectOne("SELECT cod_interno, nombre FROM personas WHERE id = ?", [$pid]);
            $cod_interno = $pers ? $pers["cod_interno"] : $pid;
            $nombre = $pers ? $pers["nombre"] : "";

            // imagen (primera foto de la persona)
            $img_row = DB::selectOne(
                "SELECT f.id AS fid FROM fotos f JOIN estancias e ON e.id = f.estancia_id WHERE e.persona_id = ? ORDER BY f.id ASC LIMIT 1",
                [$pid]
            );
            $imagen = "./caras_procesadas/" . ($img_row ? $img_row["fid"] : 0) . ".jpg";

            // nº de estancias (con/sin filtro de cámara)
            if ($camara_filtro) {
                $cnt = DB::selectOne("SELECT COUNT(*) AS veces FROM estancias WHERE persona_id = ? AND camara_id = ?", [$pid, $camara_filtro]);
            } elseif ($camaras_ids) {
                $in = implode(",", array_fill(0, count($camaras_ids), "?"));
                $cnt = DB::selectOne("SELECT COUNT(*) AS veces FROM estancias WHERE persona_id = ? AND camara_id IN ($in)", array_merge([$pid], $camaras_ids));
            } else {
                $cnt = ["veces" => 0];
            }
            $veces = $cnt ? (int)$cnt["veces"] : 0;
        ?>
            <tr role="row" class="<?= $par; ?>" <?php if (isset($_GET["unir"]) && $_GET["unir"] == $pid) { echo "style='background-color:yellow'"; } ?>>
                <td class="text-center border-b">
                    <div class="flex sm:justify-center">
                        <div class="intro-x w-10 h-10 image-fit">
                            <img alt="" onclick="scale(this,this.id,1)" src="<?= htmlspecialchars($imagen); ?>">
                        </div>
                    </div>
                </td>
                <td class="border-b" align="center"><?= htmlspecialchars($cod_interno); ?></td>
                <td class="border-b" align="center">
                    <input type="text" value="<?= htmlspecialchars($nombre); ?>" onblur="cambiar_nombre(this.value,<?= $pid; ?>)" style="width:75%">
                </td>
                <td class="text-center border-b" align="center"><?= $veces; ?></td>
                <td class="border-b w-5">
                    <div class="flex sm:justify-center items-center">
                        <a class="flex items-center mr-3" href="?page=visitantes&mode=editar&id=<?= $pid; ?>">Ver</a>
                        <a class="flex items-center mr-3" href="?page=accesos&persona_id=<?= $pid; ?>">Movimientos</a>
                        <a class="flex items-center mr-3" href="?page=rutas&persona_id=<?= $pid; ?>">Rutas</a>
                        <?php if (!isset($_GET["unir"])): ?>
                            <a class="flex items-center mr-3" href="?page=visitantes&unir=<?= $pid; ?>&camara=<?= $camara_filtro; ?>&desde=<?= urlencode($desde); ?>&hasta=<?= urlencode($hasta); ?>&trabajador=<?= $trabajador_filtro ? 1 : 0; ?>">Unir</a>
                        <?php else: ?>
                            <a class="flex items-center mr-3" href="?page=visitantes&este=<?= (int)$_GET["unir"]; ?>&coneste=<?= $pid; ?>">Con este</a>
                        <?php endif; ?>
                    </div>
                </td>
            </tr>
        <?php
            $par = ($par === "odd") ? "pair" : "odd";
        }
        ?>
        </tbody>
    </table>
</div>

<?php if (isset($_GET["unir"]) && $_GET["unir"] !== ""): ?>
<?php
$u = DB::selectOne("SELECT cod_interno, nombre FROM personas WHERE id = ?", [(int)$_GET["unir"]]);
$img_row = DB::selectOne(
    "SELECT f.id AS fid FROM fotos f JOIN estancias e ON e.id = f.estancia_id WHERE e.persona_id = ? ORDER BY f.id ASC LIMIT 1",
    [(int)$_GET["unir"]]
);
$imagen_unir = "./caras_procesadas/" . ($img_row ? $img_row["fid"] : 0) . ".jpg";
?>
<div style="width:500px;height:220px;background-color:white;position:fixed;left:50%;margin-left:-250px;top:10px;z-index:999;border-radius:20px;padding:20px">
    <table style="width:100%;height:100%">
        <tr style="background-color:cyan"><td colspan="2" align="center"><b>Unir usuario</b> <i>(Selecciona con quien)</i></td></tr>
        <tr>
            <td style="width:60%"><img src="<?= htmlspecialchars($imagen_unir); ?>" style="height:100%"></td>
            <td style="width:40%" valign="top"><?= htmlspecialchars($u["cod_interno"] ?? ""); ?><br /><?= htmlspecialchars($u["nombre"] ?? ""); ?></td>
        </tr>
    </table>
</div>
<?php endif; ?>
