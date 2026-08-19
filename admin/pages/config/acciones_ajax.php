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

    case "5": // guardar cadena de nodos en lote (JSON POST): {camara1, camara2, camino, nodos:[{x,y},...]}
        $body = json_decode((string)file_get_contents("php://input"), true);
        $camara1 = (int)($body["camara1"] ?? 0);
        $camara2 = (int)($body["camara2"] ?? 0);
        $camino  = (int)($body["camino"] ?? 0);
        $nodos   = $body["nodos"] ?? [];

        if ($camara1 <= 0 || $camara2 <= 0 || $camara1 === $camara2 || !is_array($nodos) || count($nodos) === 0) {
            http_response_code(400);
            echo "error: datos inválidos";
            break;
        }

        DB::beginTransaction();
        try {
            // Reemplazo idempotente de la cadena de este par+camino (evita nodos duplicados).
            DB::execute(
                "DELETE FROM nodos WHERE camara_id1 = ? AND camara_id2 = ? AND camino = ?",
                [$camara1, $camara2, $camino]
            );
            $orden = 1;
            foreach ($nodos as $n) {
                DB::execute(
                    "INSERT INTO nodos (camara_id1, camara_id2, x, y, orden, camino) VALUES (?, ?, ?, ?, ?, ?)",
                    [$camara1, $camara2, (int)$n["x"], (int)$n["y"], $orden++, $camino]
                );
            }
            DB::commit();
        } catch (Throwable $e) {
            DB::rollBack();
            http_response_code(500);
            echo "error: " . $e->getMessage();
            break;
        }
        echo "ok";
        break;

    case "6": // mover un nodo individual (JSON POST): {id, x, y}
        $body = json_decode((string)file_get_contents("php://input"), true);
        $id = (int)($body["id"] ?? 0);
        $x = (int)($body["x"] ?? 0);
        $y = (int)($body["y"] ?? 0);
        if ($id <= 0) {
            http_response_code(400);
            echo "error: id de nodo inválido";
            break;
        }
        DB::execute("UPDATE nodos SET x = ?, y = ? WHERE id = ?", [$x, $y, $id]);
        echo "ok";
        break;

    case "7": // eliminar un nodo individual (JSON POST): {id}
        $body = json_decode((string)file_get_contents("php://input"), true);
        $id = (int)($body["id"] ?? 0);
        if ($id <= 0) {
            http_response_code(400);
            echo "error: id de nodo inválido";
            break;
        }
        DB::execute("DELETE FROM nodos WHERE id = ?", [$id]);
        echo "ok";
        break;

    case "8": // mover una cámara en el plano (JSON POST): {id, x, y}
        $body = json_decode((string)file_get_contents("php://input"), true);
        $id = (int)($body["id"] ?? 0);
        $x = (int)($body["x"] ?? 0);
        $y = (int)($body["y"] ?? 0);
        $local = (int)($_SESSION["local_id"] ?? 0);
        if ($id <= 0 || $local <= 0) {
            http_response_code(400);
            echo "error: id de cámara inválido";
            break;
        }
        DB::execute(
            "UPDATE camaras SET x = ?, y = ? WHERE id = ? AND local_id = ?",
            [$x, $y, $id, $local]
        );
        echo "ok";
        break;

    case "9": // crear línea del plano (JSON POST): {camara_id, nombre, x1,y1,x2,y2}
        $body = json_decode((string)file_get_contents("php://input"), true);
        $camara_id = (int)($body["camara_id"] ?? 0);
        $nombre = trim((string)($body["nombre"] ?? ""));
        $x1 = (int)($body["x1"] ?? 0);
        $y1 = (int)($body["y1"] ?? 0);
        $x2 = (int)($body["x2"] ?? 0);
        $y2 = (int)($body["y2"] ?? 0);
        $local = (int)($_SESSION["local_id"] ?? 0);
        if ($local <= 0 || $camara_id <= 0 || $nombre === "" || $x1 <= 0 || $y1 <= 0 || $x2 <= 0 || $y2 <= 0) {
            http_response_code(400);
            echo "error: datos inválidos (cámara, nombre y dos clics en el plano)";
            break;
        }
        $id = DB::insert(
            "INSERT INTO lineas_plano (camara_id, nombre, x1, y1, x2, y2) VALUES (?, ?, ?, ?, ?, ?)",
            [$camara_id, $nombre, $x1, $y1, $x2, $y2]
        );
        echo "ok:" . $id;
        break;

    case "10": // mover extremos de una línea del plano (JSON POST): {id, x1,y1,x2,y2}
        $body = json_decode((string)file_get_contents("php://input"), true);
        $id = (int)($body["id"] ?? 0);
        $x1 = (int)($body["x1"] ?? 0);
        $y1 = (int)($body["y1"] ?? 0);
        $x2 = (int)($body["x2"] ?? 0);
        $y2 = (int)($body["y2"] ?? 0);
        if ($id <= 0) {
            http_response_code(400);
            echo "error: id de línea del plano inválido";
            break;
        }
        DB::execute(
            "UPDATE lineas_plano SET x1 = ?, y1 = ?, x2 = ?, y2 = ? WHERE id = ? AND eliminada = 0",
            [$x1, $y1, $x2, $y2, $id]
        );
        echo "ok";
        break;

    case "11": // borrar una línea del plano (JSON POST): {id} (soft delete)
        $body = json_decode((string)file_get_contents("php://input"), true);
        $id = (int)($body["id"] ?? 0);
        if ($id <= 0) {
            http_response_code(400);
            echo "error: id de línea del plano inválido";
            break;
        }
        DB::execute("UPDATE lineas_plano SET eliminada = 1 WHERE id = ?", [$id]);
        echo "ok";
        break;

    default:
        break;
}
