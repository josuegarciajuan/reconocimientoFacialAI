<?php

/*
 * Cámaras en directo — estado de los snapshots de la rejilla.
 *
 * Devuelve, por cámara, el mtime del snapshot (`fotos_camara/<id>.jpg`). El
 * cliente lo sondea cada pocos segundos y SOLO recarga la imagen cuyo mtime
 * cambió; entre refrescos no viaja ni un byte de imagen.
 *
 * Entrada:  ?ids=1,2,3  (opcional; sin él devuelve las cámaras activas del local)
 * Salida:   { "ok": true, "mtime": { "<id>": <epoch>, ... } }
 *           { "ok": false, "error": "..." }
 *
 * Solo se consultan cámaras del local de la sesión (defensa en profundidad).
 */

@session_start();
require_once __DIR__ . "/../../../config/rutas.php";
require_once __DIR__ . "/../../../libs/db.php";

header("Content-Type: application/json; charset=utf-8");
header("Cache-Control: no-store, no-cache, must-revalidate");

$local_id = (int)($_SESSION["local_id"] ?? 0);
if ($local_id <= 0) {
    echo json_encode(["ok" => false, "error" => "no autenticado"]);
    exit;
}

$raw = $_GET["ids"] ?? "";
$ids = array_values(array_filter(array_map("intval", explode(",", (string)$raw))));
$ids = array_slice(array_values(array_unique($ids)), 0, 500);

if (empty($ids)) {
    $filas = DB::select(
        "SELECT id FROM camaras WHERE local_id = ? AND sistema = 0 AND encendida = 1",
        [$local_id]
    );
} else {
    $marcadores = rtrim(str_repeat("?,", count($ids)), ",");
    $filas = DB::select(
        "SELECT id FROM camaras WHERE local_id = ? AND id IN ($marcadores)",
        array_merge([$local_id], $ids)
    );
}

$mtime = [];
foreach ($filas as $fila) {
    $id = (int)$fila["id"];
    $foto = RUTA_PROYECTO . "admin/fotos_camara/" . $id . ".jpg";
    if (is_file($foto)) {
        $mtime[(string)$id] = (int)filemtime($foto);
    }
}

echo json_encode(["ok" => true, "mtime" => $mtime], JSON_UNESCAPED_UNICODE);
