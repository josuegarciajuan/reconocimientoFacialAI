<?php
if (session_status() !== PHP_SESSION_ACTIVE) @session_start();

/*
 * Revisión — stream seguro de la imagen pendiente.
 *
 * Solo sesión de panel con local asignado; el `local_id` SIEMPRE sale de la
 * sesión (nunca de la query). `cam`/`f` se validan y se confinan a
 * `motor/revision/<local>/` mediante libs/revision.php. 404 si no existe.
 */

require_once __DIR__ . "/../../../config/rutas.php";
require_once __DIR__ . "/../../../libs/security.php";
require_once __DIR__ . "/../../../libs/revision.php";

$local_id = rf_require_local_session();

$cam = (string)($_GET["cam"] ?? "");
$file = (string)($_GET["f"] ?? "");

$ruta = rf_revision_ruta_segura(RUTA_PROYECTO, (string)$local_id, $cam, $file);
if ($ruta === null || !is_file($ruta)) {
    http_response_code(404);
    exit;
}

$tipos = [
    "jpg"  => "image/jpeg",
    "jpeg" => "image/jpeg",
    "png"  => "image/png",
];
$ext = strtolower(pathinfo($ruta, PATHINFO_EXTENSION));
$tipo = $tipos[$ext] ?? "application/octet-stream";

header("Content-Type: " . $tipo);
header("Content-Length: " . (string)filesize($ruta));
header("Cache-Control: private, max-age=30");
header("X-Content-Type-Options: nosniff");
readfile($ruta);
exit;
