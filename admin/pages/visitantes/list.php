<?php

/* 
 * Listado de visitantes (REFACTOR Fase 4b): PDO (B9), fechas correctas (B13), fix alias c.id (B14).
 */

require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/fechas.php";
require_once __DIR__ . "/../../../libs/etiquetas.php";

$local_id = (int)$_SESSION["local_id"];

// filtros: las fechas son opcionales; sin ellas se muestran todas las estancias.
$desde = trim((string)($_GET["desde"] ?? ""));
$hasta = trim((string)($_GET["hasta"] ?? ""));
$desde_sql = $desde !== "" ? rango_a_sql($desde, date("Y-m-d 00:00:00")) : null;
$hasta_sql = $hasta !== "" ? rango_a_sql($hasta, date("Y-m-d 23:59:59")) : null;

$camara_filtro = (isset($_GET["camara"]) && $_GET["camara"] !== "" && $_GET["camara"] !== "-") ? (int)$_GET["camara"] : 0;
$trabajador_filtro = (isset($_GET["trabajador"]) && $_GET["trabajador"] == 1);
$buscador = trim($_GET["buscador"] ?? "");

// cámaras del local (para el select y para el contador "todas")
$camaras = DB::select("SELECT id, descripcion FROM camaras WHERE local_id = ?", [$local_id]);
$camaras_ids = array_column($camaras, "id");
$camaras_por_id = [];
foreach ($camaras as $camara) {
    $camaras_por_id[(int)$camara["id"]] = (string)$camara["descripcion"];
}

// escapado para atributos onclick (patrón ui-common: verFoto('url','titulo'))
$js_quote = function ($s) {
    return htmlspecialchars(str_replace(["\\", "'"], ["\\\\", "\\'"], (string)$s), ENT_QUOTES);
};
?>

<div class="intro-y flex flex-col sm:flex-row items-center mt-8">
    <h2 class="text-lg font-medium mr-auto">Listado Visitantes</h2>
    <div class="filter-bar mt-4 sm:mt-0">

        <span class="filter-item">
            <label for="trabajador">Trabajadores</label>
            <input type="checkbox" name="trabajador" id="trabajador" value="1" <?php if ($trabajador_filtro) { echo "checked='checked'"; } ?>>
        </span>

        <span class="filter-item">
            <label for="camara">Cámara</label>
            <select class="input border" id="camara">
                <option value="-" <?php if (!$camara_filtro) { echo "selected='selected'"; } ?>>Todas</option>
                <?php foreach ($camaras as $c): ?>
                    <option value="<?= $c["id"]; ?>" <?php if ($camara_filtro === (int)$c["id"]) { echo "selected='selected'"; } ?>><?= htmlspecialchars(camara_label($c["descripcion"])); ?></option>
                <?php endforeach; ?>
            </select>
        </span>

        <span class="filter-item">
            <label for="desde">Desde</label>
            <input data-timepicker="true" class="datepicker input w-56 border" id="desde" value="<?= $desde; ?>">
        </span>

        <span class="filter-item">
            <label for="hasta">Hasta</label>
            <input data-timepicker="true" class="datepicker input w-56 border" id="hasta" value="<?= $hasta; ?>">
        </span>

        <span class="filter-item">
            <button class="button text-white bg-theme-1 shadow-md" onclick="buscar1()">Buscar</button>
            <button class="button text-white bg-theme-1 shadow-md" onclick="location.href='?page=visitantes&mode=registrar'">Registrar</button>
        </span>

    </div>
</div>

<div class="intro-y datatable-wrapper box p-5 mt-5">
    <div class="table-wrap">
    <table class="table table-report table-report--bordered display datatable w-full" data-ajax="visitantes" data-filters="camara,desde,hasta,buscador">
        <thead>
            <tr>
                <th class="border-b-2 text-center">IMAGEN</th>
                <th class="border-b-2 text-center">PERSONA</th>
                <th class="border-b-2 text-center">ÚLTIMA VISTA</th>
                <th class="border-b-2 text-center">ESTANCIAS</th>
                <th class="border-b-2 text-center">ACCIONES</th>
            </tr>
        </thead>
        <tbody></tbody>
        <?php /* Las filas se sirven por AJAX; no se precargan registros. */ if (false) {
        // consulta principal (ids de persona)
        $where = ["u.local_id = ?"];
        $params = [$local_id];
        if ($desde !== "") { $where[] = "a.fecha_ini >= ?"; $params[] = $desde_sql; }
        if ($hasta !== "") { $where[] = "a.fecha_ini <= ?"; $params[] = $hasta_sql; }
        if ($camara_filtro) { $where[] = "a.camara_id = ?"; $params[] = $camara_filtro; }
        if ($trabajador_filtro) { $where[] = "u.trabajador = 1"; }
        if ($buscador !== "") {
            $where[] = "(u.nombre LIKE ? OR u.cod_interno LIKE ?)";
            $params[] = "%" . $buscador . "%";
            $params[] = "%" . $buscador . "%";
        }

        // La cámara se obtiene dentro de la misma consulta para conservar los filtros
        // activos y evitar una consulta adicional por cada persona.
        $ultima_where = ["a2.persona_id = a.persona_id", "c2.local_id = u.local_id"];
        $ultima_params = [];
        if ($desde !== "") { $ultima_where[] = "a2.fecha_ini >= ?"; $ultima_params[] = $desde_sql; }
        if ($hasta !== "") { $ultima_where[] = "a2.fecha_ini <= ?"; $ultima_params[] = $hasta_sql; }
        if ($camara_filtro) { $ultima_where[] = "a2.camara_id = ?"; $ultima_params[] = $camara_filtro; }
        if ($trabajador_filtro) { $ultima_where[] = "u.trabajador = 1"; }
        if ($buscador !== "") {
            $ultima_where[] = "(u.nombre LIKE ? OR u.cod_interno LIKE ?)";
            $ultima_params[] = "%" . $buscador . "%";
            $ultima_params[] = "%" . $buscador . "%";
        }
        $sql_main = "SELECT a.persona_id, MAX(a.fecha_ini) AS ultima_aparicion
                         , (SELECT a2.camara_id
                            FROM estancias a2
                            JOIN camaras c2 ON c2.id = a2.camara_id
                            WHERE " . implode(" AND ", $ultima_where) . "
                            ORDER BY a2.fecha_ini DESC, a2.id DESC
                            LIMIT 1) AS ultima_camara_id
                     FROM estancias a
                     JOIN personas u ON u.id = a.persona_id
                     JOIN camaras c ON c.id = a.camara_id AND c.local_id = u.local_id
                     WHERE " . implode(" AND ", $where) . "
                     GROUP BY a.persona_id
                     ORDER BY MAX(a.fecha_ini) DESC";
        $persona_ids = DB::select($sql_main, array_merge($ultima_params, $params));

        $par = "odd";
        foreach ($persona_ids as $prow) {
            $pid = (int)$prow["persona_id"];

            $pers = DB::selectOne("SELECT cod_interno, nombre, trabajador FROM personas WHERE id = ?", [$pid]);
            $cod_interno = $pers ? $pers["cod_interno"] : $pid;
            $nombre = $pers ? $pers["nombre"] : "";

            $ultima_camara_id = (int)($prow["ultima_camara_id"] ?? 0);
            $ultima_fecha = (string)($prow["ultima_aparicion"] ?? "");
            $ultima_ts = strtotime($ultima_fecha);
            $ultima_fecha_fmt = $ultima_ts ? date("d/m/Y H:i:s", $ultima_ts) : $ultima_fecha;

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
            <tr role="row" class="<?= $par; ?>" <?php if (isset($_GET["unir"]) && $_GET["unir"] == $pid) { echo "style='background-color:var(--mordor-oro-suave)'"; } ?>>
                <td class="text-center border-b">
                    <div class="flex sm:justify-center">
                        <div class="intro-x w-10 h-10 image-fit">
                            <img alt="Foto de <?= htmlspecialchars($nombre); ?>" onclick="verFoto('<?= $js_quote($imagen); ?>','<?= $js_quote($nombre); ?>')" class="cursor-pointer" src="<?= htmlspecialchars($imagen); ?>">
                        </div>
                    </div>
                </td>
                <td class="border-b" align="center">
                    <a class="text-theme-1 font-medium hover:underline" href="?page=visitantes&mode=editar&id=<?= $pid; ?>" title="Ver la ficha de la persona"><?= htmlspecialchars(persona_label($nombre, $cod_interno)); ?></a>
                </td>
                <td class="text-center border-b" data-order="<?= $ultima_ts ? (int)$ultima_ts : 0; ?>">
                    <?php if ($ultima_camara_id > 0): ?>
                        <?= camara_link($ultima_camara_id, $camaras_por_id[$ultima_camara_id] ?? null); ?><br>
                    <?php endif; ?>
                    <?= htmlspecialchars($ultima_fecha_fmt); ?>
                </td>
                <td class="text-center border-b" align="center"><?= $veces; ?></td>
                <td class="border-b">
                    <div class="acciones-stack">
                        <div class="accion-item">
                            <a href="?page=visitantes&mode=editar&id=<?= $pid; ?>" data-tip="Ver y editar los datos de la persona">Ver</a>
                        </div>
                        <div class="accion-item">
                            <a href="?page=accesos&persona_id=<?= $pid; ?>" data-tip="Ver los movimientos y accesos de la persona">Movimientos</a>
                        </div>
                        <div class="accion-item">
                            <a href="?page=visitantes&mode=editar&id=<?= $pid; ?>#videos" data-tip="Ver los vídeos vinculados a la persona">Vídeos</a>
                        </div>
                        <div class="accion-item">
                            <a href="?page=lineas&persona_id=<?= $pid; ?>" data-tip="Ver los cruces de línea de la persona">Cruces</a>
                        </div>
                        <div class="accion-item">
                            <a href="?page=rutas&persona_id=<?= $pid; ?>" data-tip="Ver las rutas de la persona">Rutas</a>
                        </div>
                        <?php if ((int)($pers["trabajador"] ?? 0) === 1): ?>
                        <div class="accion-item">
                            <a href="?page=fichajes&persona_id=<?= $pid; ?>" data-tip="Ver los fichajes del trabajador (entradas y salidas)">Fichajes</a>
                        </div>
                        <?php endif; ?>
                        <?php if (!isset($_GET["unir"])): ?>
                            <div class="accion-item">
                    <a href="?page=visitantes&unir=<?= $pid; ?>&camara=<?= $camara_filtro; ?>&desde=<?= urlencode($desde); ?>&hasta=<?= urlencode($hasta); ?>&trabajador=<?= $trabajador_filtro ? 1 : 0; ?>&buscador=<?= urlencode($buscador); ?>" data-tip="Unir esta persona con otra para fusionar identidades">Unir</a>
                            </div>
                        <?php else: ?>
                            <div class="accion-item">
                                <a href="?page=visitantes&este=<?= (int)$_GET["unir"]; ?>&coneste=<?= $pid; ?>"
                                   onclick="return rfConfirmarUnir(<?= (int)$_GET["unir"]; ?>,<?= $pid; ?>)"
                                   data-tip="Fusionar esta persona con la seleccionada">Con este</a>
                            </div>
                        <?php endif; ?>
                    </div>
                </td>
            </tr>
        <?php
            $par = ($par === "odd") ? "pair" : "odd";
        }
        } ?>
    </table>
    </div>
</div>

<?php if (isset($_GET["unir"]) && $_GET["unir"] !== ""): ?>
<?php
$u = DB::selectOne("SELECT cod_interno, nombre FROM personas WHERE id = ?", [(int)$_GET["unir"]]);
$u_label = persona_label($u["nombre"] ?? "", $u["cod_interno"] ?? "");
$img_row = DB::selectOne(
    "SELECT f.id AS fid FROM fotos f JOIN estancias e ON e.id = f.estancia_id WHERE e.persona_id = ? ORDER BY f.id ASC LIMIT 1",
    [(int)$_GET["unir"]]
);
$imagen_unir = "./caras_procesadas/" . ($img_row ? $img_row["fid"] : 0) . ".jpg";
$unir_id = (int)$_GET["unir"];
$candidatos = DB::select(
    "SELECT id, cod_interno, nombre FROM personas WHERE local_id = ? AND id <> ? ORDER BY nombre ASC, cod_interno ASC",
    [$local_id, $unir_id]
);
?>
<div class="modal" id="modal-unir" role="dialog" aria-modal="true" aria-labelledby="modal-unir-titulo">
    <div class="modal__content box p-5">
        <div class="flex items-center mb-4">
            <h3 id="modal-unir-titulo" class="media-modal__title mr-auto truncate">Unir usuario</h3>
            <a href="javascript:;" data-dismiss="modal" class="button button--sm text-white bg-theme-6 ml-3">Cerrar</a>
        </div>

        <div class="flex flex-col sm:flex-row items-center gap-4">
            <img class="w-24 h-24 object-cover rounded cursor-pointer flex-none"
                 alt="Foto de <?= htmlspecialchars($u_label); ?>"
                 onclick="verFoto('<?= $js_quote($imagen_unir); ?>','<?= $js_quote($u_label); ?>')"
                 src="<?= htmlspecialchars($imagen_unir); ?>">
            <div class="text-center sm:text-left text-gray-600 dark:text-gray-300">
                <div class="font-semibold"><?= htmlspecialchars($u_label); ?></div>
            </div>
        </div>

        <form method="get" action="?page=visitantes" class="mt-4 pt-4 border-t border-gray-200 dark:border-dark-5" onsubmit="return rfConfirmarUnirModal()">
            <input type="hidden" name="este" value="<?= $unir_id; ?>">
            <label class="field-label" for="coneste">Unir con</label>
            <div class="flex flex-col sm:flex-row gap-2">
                <select name="coneste" id="coneste" class="input border w-full">
                    <option value="">Selecciona un usuario</option>
                    <?php foreach ($candidatos as $cand): ?>
                        <option value="<?= (int)$cand["id"]; ?>"><?= htmlspecialchars(persona_label($cand["nombre"], $cand["cod_interno"])); ?></option>
                    <?php endforeach; ?>
                </select>
                <button type="submit" class="button text-white bg-theme-1 shadow-md flex-none">Unir</button>
            </div>
        </form>
    </div>
</div>
<script>
    $(function () {
        if (typeof window.rfAbrirModal === "function") {
            window.rfAbrirModal("modal-unir");
        }
    });

    // P5: confirmación ligera + overlay de carga (la operación es síncrona)
    function rfMostrarCargando(){
        if (document.getElementById("rf-cargando")) { return; }
        var d = document.createElement("div");
        d.id = "rf-cargando";
        d.style.cssText = "position:fixed;inset:0;background:rgba(0,0,0,.55);z-index:9999;" +
            "display:flex;align-items:center;justify-content:center;color:#fff;font-weight:600;font-size:1.05rem";
        d.textContent = "Aplicando corrección a la biblioteca…";
        document.body.appendChild(d);
    }
    function rfConfirmarUnir(a, b){
        if (!confirm("¿Unir ambas personas? Sus bibliotecas de caras se fusionarán.")) { return false; }
        rfMostrarCargando();
        return true;
    }
    function rfConfirmarUnirModal(){
        var sel = document.getElementById("coneste");
        if (!sel || sel.value === "") { alert("Selecciona un usuario"); return false; }
        if (!confirm("¿Unir ambas personas? Sus bibliotecas de caras se fusionarán.")) { return false; }
        rfMostrarCargando();
        return true;
    }
</script>
<?php endif; ?>
