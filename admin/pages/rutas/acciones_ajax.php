<?php

/* 
 * Rutas — AJAX (REFACTOR Fase 4b): PDO.
 * a=2 devuelve nodos entre dos cámaras.
 */

require_once __DIR__ . "/../../../config/rutas.php";
require_once __DIR__ . "/../../../libs/db.php";

switch ($_GET["a"]) {
    case "2":
        $camara_id1 = (int)$_GET["camara_id1"];
        $camara_id2 = (int)$_GET["camara_id2"];
        $rows = DB::select(
            "SELECT x, y FROM nodos WHERE (camara_id1 = ? AND camara_id2 = ?) OR (camara_id1 = ? AND camara_id2 = ?) ORDER BY orden ASC",
            [$camara_id1, $camara_id2, $camara_id2, $camara_id1]
        );
        $return = [];
        foreach ($rows as $r) {
            $return[] = $r["x"] . "," . $r["y"];
        }
        echo implode(";;;", $return);
        break;

    default:
        break;
}
