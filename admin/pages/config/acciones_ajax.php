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

    case "3": // refrescar snapshot de cámara (dofoto.py en segundo plano si está viejo)
        $cam_id = (int)($_GET["camara"] ?? 0);
        $cam = DB::selectOne("SELECT id, url_conexion FROM camaras WHERE id = ?", [$cam_id]);
        if ($cam) {
            $foto = RUTA_PROYECTO . "admin/fotos_camara/" . $cam_id . ".png";
            if (!is_file($foto) || (time() - filemtime($foto)) > 15) {
                $url = str_replace("'", "", (string)$cam["url_conexion"]);
                $cmd = RUTA_PYTHON . " " . RUTA_PROYECTO . "motor/dofoto.py " . $cam_id
                     . " '" . $url . "' '" . RUTA_PROYECTO . "'";
                exec($cmd . " > /dev/null 2>&1 &");
            }
        }
        echo "ok";
        break;

    case "4": // líneas de una cámara (para el lienzo en modo foto, sin recargar)
        $cam_id = (int)($_GET["camara"] ?? 0);
        $lineas = DB::select(
            "SELECT id, nombre, x1, y1, x2, y2 FROM lineas WHERE camara_id = ? AND eliminada = 0 ORDER BY id ASC",
            [$cam_id]
        );
        echo json_encode($lineas, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        break;

    default:
        break;
}
