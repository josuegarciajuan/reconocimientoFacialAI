<?php

/* 
 * Cámaras en directo (REFACTOR Fase 4c + live MJPEG).
 * - Rejilla: snapshots `fotos_camara/<id>.png` refrescados en segundo plano
 *   (dofoto.py async, con caché de 15s). Antes cada carga bloqueaba ~60s
 *   (exec + sleep(2) síncrono por cámara) -> la sección "no cargaba".
 * - Detalle (clic en cámara): streaming local RTSP->MJPEG vía
 *   live/mjpeg-stream.js y proxy Apache /reconocimientoFacial/live,
 *   en lugar del iframe de ipcamlive.com (alias sin configurar -> no cargaba).
 */

require_once __DIR__ . "/../../../libs/db.php";

$local_id = (int)($_SESSION["local_id"] ?? 0);
$camaras = DB::select("SELECT * FROM camaras WHERE local_id = ? AND sistema = 0 AND encendida = 1 ORDER BY descripcion ASC", [$local_id]);

/**
 * Lanza dofoto.py en segundo plano si el snapshot es antiguo o no existe.
 * Máximo 1 refresco por cámara cada 15s (evita golpear el RTSP en cada F5).
 */
function refrescar_snapshot(int $camara_id, string $url_conexion): void
{
    $foto = RUTA_PROYECTO . "admin/fotos_camara/" . $camara_id . ".png";
    if (is_file($foto) && (time() - filemtime($foto)) < 15) {
        return;
    }
    $url_limpia = str_replace("'", "", $url_conexion);
    $cmd = RUTA_PYTHON . " " . RUTA_PROYECTO . "motor/dofoto.py " . $camara_id
         . " '" . $url_limpia . "' '" . RUTA_PROYECTO . "'";
    exec($cmd . " > /dev/null 2>&1 &");
}

/* Token HMAC de corta validez para el stream MJPEG (valida el servicio rf-live). */
$live_token = "";
$live_secret = getenv("RF_LIVE_TOKEN");
if ($live_secret !== false && $live_secret !== "") {
    $ventana = (int)floor(time() / 300);
    $live_token = hash_hmac("sha256", "live:" . (int)($_GET["id"] ?? 0) . ":" . $ventana, $live_secret);
}
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
        $camara_id = (int)$c["id"];
        $url_conexion = (string)($c["url_conexion"] ?? "");

        refrescar_snapshot($camara_id, $url_conexion);

        $foto = RUTA_PROYECTO . "admin/fotos_camara/" . $camara_id . ".png";
        $ts = is_file($foto) ? (int)filemtime($foto) : 0;

        echo "<td><img style='cursor:pointer' onclick=\"location.href='?page=camaras&id=" . $camara_id . "'\" src='fotos_camara/" . $camara_id . ".png?t=" . $ts . "'><br />" . htmlspecialchars((string)$c["descripcion"]) . "</td>";
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
    $camara_id = (int)$c["id"];
    $stream_url = "../live?id=" . $camara_id;
    if ($live_token !== "") {
        $stream_url .= "&token=" . urlencode($live_token);
    }
    $snapshot_url = "fotos_camara/" . $camara_id . ".png";
?>
    <br /><br /><hr /><h1>Viendo cámara: <?= htmlspecialchars((string)$c["descripcion"]); ?></h1><br />
    <img src="<?= $stream_url; ?>" alt="<?= htmlspecialchars((string)$c["descripcion"]); ?>"
         style="max-width:100%; border:1px solid #ddd;"
         onerror="this.onerror=null; this.src='<?= $snapshot_url; ?>';">
<?php endif; ?>
<?php endif; ?>
