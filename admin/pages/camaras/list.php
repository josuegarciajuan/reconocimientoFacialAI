<?php

/* 
 * Cámaras en directo (REFACTOR Fase 4c): PDO (B9). Mantiene el snapshot con dofoto.py.
 */

require_once __DIR__ . "/../../../libs/db.php";

$local_id = (int)($_SESSION["local_id"] ?? 0);
$camaras = DB::select("SELECT * FROM camaras WHERE local_id = ? AND sistema = 0 AND encendida = 1 ORDER BY descripcion ASC", [$local_id]);
?>

<div class="intro-y flex flex-col sm:flex-row items-center mt-8">
    <h2 class="text-lg font-medium mr-auto">Cámaras en Directo</h2>
    <div class="w-full sm:w-auto flex mt-4 sm:mt-0"></div>
</div>

<table style="width:100%"><tr>
    <?php
    $limite_linea = 10;
    $i = 0;
    foreach ($camaras as $c) {
        $camara_id = $c["id"];
        $url_conexion = $c["url_conexion"];

        if (!isset($_GET["id"]) or $_GET["id"] == "") {
            $cmd = RUTA_PYTHON . " " . RUTA_PROYECTO . "motor/dofoto.py " . (int)$camara_id . " '" . $url_conexion . "' '" . RUTA_PROYECTO . "'";
            exec($cmd);
            sleep(2);
        }

        echo "<td><img style='cursor:pointer' onclick=\"location.href='?page=camaras&id=" . (int)$camara_id . "'\" src='fotos_camara/" . (int)$camara_id . ".png'><br />" . htmlspecialchars($c["descripcion"]) . "</td>";
        if ($i == $limite_linea) {
            echo "</tr><tr>";
        }
        $i++;
    }
    for ($j = $i; $j < $limite_linea; $j++) {
        echo "<td></td>";
    }
    ?>
</tr></table>

<?php if (isset($_GET["id"]) && $_GET["id"] !== ""): ?>
<?php
$c = DB::selectOne("SELECT * FROM camaras WHERE id = ?", [(int)$_GET["id"]]);
if ($c):
    $url = $c["url_conexion"];
    $ipcamlive_alias = $c["ipcamlive_alias"];
?>
    <br /><br /><hr /><h1>Viendo cámara: <?= htmlspecialchars($c["descripcion"]); ?></h1><br />
    <h1><?= htmlspecialchars($url); ?></h1><br /><br /><br />
    <iframe src="http://ipcamlive.com/player/player.php?alias=<?= htmlspecialchars($ipcamlive_alias); ?>" width="800px" height="600px"></iframe>
<?php endif; ?>
<?php endif; ?>
