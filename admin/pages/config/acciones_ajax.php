<?php

/* 
 * Config — AJAX (REFACTOR Fase 4b): PDO (B9).
 */

require_once __DIR__ . "/../../../config/rutas.php";
require_once __DIR__ . "/../../../libs/db.php";

switch ($_GET["a"]) {
    case "1": // datos de una cámara
        $camara = (int)$_GET["camara"];
        $c = DB::selectOne("SELECT * FROM camaras WHERE id = ?", [$camara]);
        if ($c) {
            echo implode(";;;", [
                $c["descripcion"], $c["directorio"], $c["x"], $c["y"], $c["puerta"], $c["salida"],
                $c["encendida"], $c["url_conexion"], $c["sistema"], $c["ipcamlive_alias"], $c["url_desdeserver"],
                $c["segundos_analizar"], $c["porcentaje_mov"], $c["dontCare"], $c["fps"],
                $c["maximo_videos"], $c["redimesionframe"], $c["sensibilidad"],
            ]);
        }
        break;

    case "2": // insertar nodo
        DB::insert(
            "INSERT INTO nodos (camara_id1, camara_id2, x, y, orden) VALUES (?, ?, ?, ?, ?)",
            [(int)$_GET["camara1"], (int)$_GET["camara2"], (int)$_GET["x"], (int)$_GET["y"], (int)$_GET["actual"] + 1]
        );
        break;

    default:
        break;
}
