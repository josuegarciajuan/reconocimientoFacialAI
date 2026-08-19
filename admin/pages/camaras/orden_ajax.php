<?php

/* 
 * Cámaras en directo — persistir el orden de la rejilla (arrastrar y soltar).
 * Recibe `ids` (lista separada por comas de camara_id en el orden nuevo) y
 * reescribe `camaras.orden` para esas cámaras. Solo se tocan cámaras del
 * local de la sesión; el resto se ignora (defensa en profundidad).
 *
 * Devolución JSON: { "ok": true, "orden": N } o { "ok": false, "error": "..." }.
 */

@session_start();
require_once __DIR__ . "/../../../config/rutas.php";
require_once __DIR__ . "/../../../libs/db.php";

header("Content-Type: application/json; charset=utf-8");

$local_id = (int)($_SESSION["local_id"] ?? 0);

$raw = $_POST["ids"] ?? ($_GET["ids"] ?? "");
$ids = array_values(array_filter(array_map("intval", explode(",", (string)$raw))));

if ($local_id <= 0 || empty($ids)) {
    echo json_encode(["ok" => false, "error" => "petición inválida"]);
    exit;
}

/* Delimitar a un número razonable y descartar duplicados conservando el orden. */
$ids = array_slice(array_values(array_unique($ids)), 0, 500);

/* Comprobar qué ids pertenecen realmente al local de la sesión. */
$marcadores = rtrim(str_repeat("?,", count($ids)), ",");
$validas = DB::select(
    "SELECT id FROM camaras WHERE local_id = ? AND id IN ($marcadores)",
    array_merge([$local_id], $ids)
);
$permitidas = [];
foreach ($validas as $v) {
    $permitidas[(int)$v["id"]] = true;
}

$orden = 0;
foreach ($ids as $id) {
    if (!isset($permitidas[$id])) {
        continue;
    }
    $orden++;
    DB::execute("UPDATE camaras SET orden = ? WHERE id = ?", [$orden, $id]);
}

echo json_encode(["ok" => true, "orden" => $orden], JSON_UNESCAPED_UNICODE);
