<?php

/* 
 * Perfil de persona + galería (REFACTOR Fase 4c): PDO (B9).
 */

require_once __DIR__ . "/../../../libs/db.php";

$local_id = (int)($_SESSION["local_id"] ?? 0);
$persona_id = (int)($_GET["id"] ?? 0);

$persona = DB::selectOne('SELECT * FROM personas WHERE id = ?', [$persona_id]);
if (!$persona) {
    echo "Persona no encontrada";
    return;
}

$foto = DB::selectOne(
    "SELECT f.id AS fid FROM fotos f JOIN estancias e ON e.id = f.estancia_id WHERE e.persona_id = ? ORDER BY f.id ASC LIMIT 1",
    [$persona_id]
);
$imagen_perfil = "./caras_procesadas/" . ($foto ? $foto["fid"] : 0) . ".jpg";

// cámaras del local + nº de estancias por cámara
$camaras = DB::select("SELECT * FROM camaras WHERE local_id = ?", [$local_id]);
$counts = [];
foreach ($camaras as $c) {
    $cnt = DB::selectOne("SELECT COUNT(*) AS n FROM estancias WHERE camara_id = ? AND persona_id = ?", [(int)$c["id"], $persona_id]);
    $counts[$c["id"]] = $cnt ? (int)$cnt["n"] : 0;
}

// listado de personas para "mover imagen"
$personas_list = DB::select("SELECT id, cod_interno, nombre FROM personas WHERE local_id = ? ORDER BY id ASC", [$local_id]);

// galería de fotos (estancias + fotos)
$galeria = [];  // [{fecha_ini, fecha_fin, fotos: [ids]}]
$estancias = DB::select("SELECT * FROM estancias WHERE persona_id = ? ORDER BY id ASC", [$persona_id]);
foreach ($estancias as $e) {
    $fotos = array_column(DB::select("SELECT id FROM fotos WHERE estancia_id = ? ORDER BY id ASC", [(int)$e["id"]]), "id");
    if ($fotos) {
        $galeria[] = ["fecha_ini" => $e["fecha_ini"], "fecha_fin" => $e["fecha_fin"], "fotos" => $fotos];
    }
}
?>

<div class="intro-y flex items-center mt-8">
    <h2 class="text-lg font-medium mr-auto">Usuario: <?= htmlspecialchars($persona["cod_interno"] . " - " . $persona["nombre"]); ?></h2>
</div>

<div class="intro-y box px-5 pt-5 mt-5">
    <div class="flex flex-col lg:flex-row border-b border-gray-200 dark:border-dark-5 pb-5 -mx-5">
        <div class="flex flex-1 px-5 items-center justify-center lg:justify-start">
            <center><img alt="" class="rounded-full" src="<?= htmlspecialchars($imagen_perfil); ?>"></center>
        </div>

        <div class="flex mt-6 lg:mt-0 items-center lg:items-start flex-1 flex-col justify-center text-gray-600 dark:text-gray-300 px-5 border-l border-r border-gray-200 dark:border-dark-5 border-t lg:border-t-0 pt-5 lg:pt-0">
            <div class="truncate sm:whitespace-normal flex items-center">
                &nbsp;ID:&nbsp;<b><?= $persona_id; ?></b>
            </div>
            <div class="truncate sm:whitespace-normal flex items-center">
                &nbsp;Código interno:&nbsp;<b><?= htmlspecialchars($persona["cod_interno"]); ?></b>
            </div>
            <br />
            <div class="truncate sm:whitespace-normal flex items-center">
                &nbsp;Nombre:&nbsp;<input type="text" value="<?= htmlspecialchars($persona["nombre"]); ?>" onblur="cambiar_nombre(this.value,<?= $persona_id; ?>)" style="width:100%;border-style:solid;border-width:1px;border-color:#EDF2F7">
            </div>
            <div class="truncate sm:whitespace-normal flex items-center">
                &nbsp;Es Trabajador:&nbsp;
                <input type="checkbox" name="trabajador_edit" id="trabajador_edit" value="1" <?php if ((int)$persona["trabajador"] === 1) { echo "checked='checked'"; } ?> onclick="cambiar_trabajador(<?= $persona_id; ?>)">
            </div>
        </div>

        <div class="flex mt-6 lg:mt-0 items-center lg:items-start flex-1 flex-col justify-center text-gray-600 px-5 pt-5">
            <?php foreach ($camaras as $c): ?>
                <div class="text-center rounded-md" style="padding:8px">
                    <div class="font-semibold text-theme-1 text-lg"><?= $counts[$c["id"]] ?? 0; ?></div>
                    <div class="text-gray-600"><?= htmlspecialchars($c["descripcion"]); ?></div>
                </div>
            <?php endforeach; ?>
        </div>
    </div>

    <div class="nav-tabs flex flex-col sm:flex-row justify-center lg:justify-start">
        <a href="?page=accesos&persona_id=<?= $persona_id; ?>" class="py-4 sm:mr-8 flex items-center active">Ver Movimientos</a>
        <a href="?page=rutas&persona_id=<?= $persona_id; ?>" class="py-4 sm:mr-8 flex items-center">Ver rutas</a>
    </div>
</div>

<div class="tab-content mt-5">
    <div class="tab-content__pane active" id="profile">
        <div class="grid grid-cols-12 gap-6">
            <div class="intro-y box col-span-12">
                <div class="flex items-center px-5 py-3 border-b border-gray-200 dark:border-dark-5">
                    <h2 class="font-medium text-base mr-auto">Listado Fotos</h2>
                </div>
                <div style="padding:10px">
                    <table cellpadding="0" cellspacing="0">
                    <?php
                    $count = 0;
                    foreach ($galeria as $g) {
                        $primera = true;
                        foreach ($g["fotos"] as $fid) {
                            $count++;
                            if ($count === 1) { echo "<tr>"; }
                            $fecha = $primera ? $g["fecha_ini"] : $g["fecha_fin"];
                            $primera = false;
                            $img = "./caras_procesadas/" . $fid . ".jpg";
                            echo '<td align="center">' . htmlspecialchars($fecha) . '<br />
                                <img src="' . htmlspecialchars($img) . '" style="width:150px">
                                <select style="width:150px" onchange="mover_img(' . (int)$fid . ',this.value)">
                                <option>Mover Imagen</option>
                                <option value="0">NUEVA PERSONA</option>';
                            foreach ($personas_list as $p) {
                                $pn = ($p["nombre"] !== "") ? $p["nombre"] : $p["cod_interno"];
                                echo '<option value="' . (int)$p["id"] . '">' . htmlspecialchars($pn) . '</option>';
                            }
                            echo '</select></td>';
                            if ($count === 7) { $count = 0; echo "</tr><tr><td colspan='7'><br /></td></tr>"; }
                        }
                    }
                    if ($count > 0) { echo "</tr>"; }
                    ?>
                    </table>
                </div>
            </div>
        </div>
    </div>
</div>
