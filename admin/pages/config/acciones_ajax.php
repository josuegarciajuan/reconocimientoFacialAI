<?php

/* 
 * Config — AJAX (REFACTOR Fase 4b): PDO (B9).
 */

require_once __DIR__ . "/../../../config/rutas.php";
require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/nodos.php";
require_once __DIR__ . "/../../../libs/lineas_plano.php";

/* La sesión debe estar iniciada para leer $_SESSION["local_id"] (caso 8: mover cámara).
 * Este fichero se llama por fetch directo (no pasa por index.php), así que hay que
 * iniciarla aquí. Patrón idéntico a admin/accionesAjax.php. */
@session_start();

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
                $c["alarma_heredar"] ?? 1, $c["alarma_24h"] ?? 0,
                $c["alarma_hora_inicio"] ?? "", $c["alarma_hora_fin"] ?? "",
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
            "UPDATE camaras SET x = ?, y = ?, colocada = 1 WHERE id = ? AND local_id = ?",
            [$x, $y, $id, $local]
        );
        echo "ok";
        break;

    case "9": // guardar cadena de nodos con camino automático (JSON POST): {camara1, camara2, nodos:[{x,y},...]}
        $body = json_decode((string)file_get_contents("php://input"), true);
        $camara1 = (int)($body["camara1"] ?? 0);
        $camara2 = (int)($body["camara2"] ?? 0);
        $nodos   = $body["nodos"] ?? [];

        if ($camara1 <= 0 || $camara2 <= 0 || $camara1 === $camara2 || !is_array($nodos) || count($nodos) === 0) {
            http_response_code(400);
            echo json_encode(["ok" => false, "error" => "datos inválidos"]);
            break;
        }
        foreach ($nodos as $n) {
            if (!is_array($n) || !isset($n["x"], $n["y"])) {
                http_response_code(400);
                echo json_encode(["ok" => false, "error" => "nodo inválido en el lote"]);
                break 2;
            }
        }

        // Camino automático: 0 si es el primero entre el par, si no MAX(camino)+1.
        // Consulta canónica del par en ambos sentidos (como nodos_caminos_entre()).
        $filas = DB::select(
            "SELECT camino FROM nodos
             WHERE (camara_id1 = ? AND camara_id2 = ?) OR (camara_id1 = ? AND camara_id2 = ?)",
            [$camara1, $camara2, $camara2, $camara1]
        );
        $camino = siguiente_camino($filas);

        DB::beginTransaction();
        try {
            $guardados = [];
            $orden = 1;
            foreach ($nodos as $n) {
                $id = DB::insert(
                    "INSERT INTO nodos (camara_id1, camara_id2, x, y, orden, camino) VALUES (?, ?, ?, ?, ?, ?)",
                    [$camara1, $camara2, (int)$n["x"], (int)$n["y"], $orden, $camino]
                );
                $guardados[] = [
                    "id"          => $id,
                    "camara_id1"  => $camara1,
                    "camara_id2"  => $camara2,
                    "camino"      => $camino,
                    "x"           => (int)$n["x"],
                    "y"           => (int)$n["y"],
                    "orden"       => $orden,
                ];
                $orden++;
            }
            DB::commit();
        } catch (Throwable $e) {
            DB::rollBack();
            http_response_code(500);
            echo json_encode(["ok" => false, "error" => $e->getMessage()]);
            break;
        }
        echo json_encode(["ok" => true, "camino" => $camino, "nodos" => $guardados]);
        break;

    case "10": // eliminar cadena completa por par+camino (JSON POST): {camara1, camara2, camino}
        $body = json_decode((string)file_get_contents("php://input"), true);
        $camara1 = (int)($body["camara1"] ?? 0);
        $camara2 = (int)($body["camara2"] ?? 0);
        $camino  = (int)($body["camino"] ?? 0);
        if ($camara1 <= 0 || $camara2 <= 0 || $camara1 === $camara2) {
            http_response_code(400);
            echo json_encode(["ok" => false, "error" => "datos inválidos"]);
            break;
        }
        DB::execute(
            "DELETE FROM nodos
             WHERE ((camara_id1 = ? AND camara_id2 = ?) OR (camara_id1 = ? AND camara_id2 = ?)) AND camino = ?",
            [$camara1, $camara2, $camara2, $camara1, $camino]
        );
        echo json_encode(["ok" => true]);
        break;

    case "11": // crear línea del plano (JSON POST): {camara_id, nombre, x1,y1,x2,y2, linea_id?}
        $body = json_decode((string)file_get_contents("php://input"), true);
        $camara_id = (int)($body["camara_id"] ?? 0);
        $nombre = trim((string)($body["nombre"] ?? ""));
        $x1 = (int)($body["x1"] ?? 0);
        $y1 = (int)($body["y1"] ?? 0);
        $x2 = (int)($body["x2"] ?? 0);
        $y2 = (int)($body["y2"] ?? 0);
        $linea_id = (int)($body["linea_id"] ?? 0);
        $local = (int)($_SESSION["local_id"] ?? 0);
        if ($local <= 0 || $camara_id <= 0 || $nombre === "") {
            http_response_code(400);
            echo "error: datos inválidos (cámara, nombre y dos clics en el plano)";
            break;
        }
        // Segmento válido: al menos una coordenada distinta (longitud no nula).
        if ($x1 === $x2 && $y1 === $y2) {
            http_response_code(400);
            echo "error: la línea necesita inicio y fin distintos";
            break;
        }
        DB::beginTransaction();
        try {
            // 1:1: si la línea de cámara ya estaba representada, se desvincula de la anterior.
            if ($linea_id > 0) {
                DB::execute("UPDATE lineas_plano SET linea_id = NULL WHERE linea_id = ?", [$linea_id]);
            }
            $id = DB::insert(
                "INSERT INTO lineas_plano (camara_id, linea_id, nombre, x1, y1, x2, y2) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [$camara_id, $linea_id > 0 ? $linea_id : null, $nombre, $x1, $y1, $x2, $y2]
            );
            DB::commit();
        } catch (Throwable $e) {
            DB::rollBack();
            http_response_code(500);
            echo "error: " . $e->getMessage();
            break;
        }
        echo "ok:" . $id;
        break;

    case "12": // mover extremos de una línea del plano (JSON POST): {id, x1,y1,x2,y2, linea_id?}
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
        $set = "x1 = ?, y1 = ?, x2 = ?, y2 = ?";
        $params = [$x1, $y1, $x2, $y2];
        if (array_key_exists("linea_id", $body)) {
            $linea_id = (int)($body["linea_id"] ?? 0);
            $set .= ", linea_id = ?";
            $params[] = $linea_id > 0 ? $linea_id : null;
        }
        $params[] = $id;
        DB::execute("UPDATE lineas_plano SET $set WHERE id = ? AND eliminada = 0", $params);
        echo "ok";
        break;

    case "13": // borrar una línea del plano (JSON POST): {id} (soft delete)
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

    case "14": // líneas de cámara de una cámara: sin plano + ya mapeadas (GET: ?a=14&camara=N)
        header("Content-Type: application/json; charset=utf-8");
        $cam_id = (int)($_GET["camara"] ?? 0);
        if ($cam_id <= 0) {
            http_response_code(400);
            echo json_encode(["ok" => false, "error" => "cámara inválida"]);
            break;
        }
        $sin_plano = array_map("lineas_plano_utf8", lineas_sin_plano($cam_id));
        $mapeadas = DB::select(
            "SELECT l.id AS linea_id, l.nombre AS linea_nombre, lp.id AS plano_id, lp.nombre AS plano_nombre
             FROM lineas l
             JOIN lineas_plano lp ON lp.linea_id = l.id
             WHERE l.camara_id = ? AND l.eliminada = 0 AND lp.eliminada = 0
             ORDER BY l.id ASC",
            [$cam_id]
        );
        echo json_encode([
            "ok"       => true,
            "sin_plano"=> array_map("lineas_plano_utf8", $sin_plano),
            "mapeadas" => array_map("lineas_plano_utf8", $mapeadas),
        ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        break;

    case "15": // vincular/desvincular línea del plano con línea de cámara (JSON POST): {plano_id, linea_id}
        $body = json_decode((string)file_get_contents("php://input"), true);
        $plano_id = (int)($body["plano_id"] ?? 0);
        $linea_id = (int)($body["linea_id"] ?? 0);
        if ($plano_id <= 0) {
            http_response_code(400);
            echo json_encode(["ok" => false, "error" => "línea del plano inválida"]);
            break;
        }
        $ok = ($linea_id > 0)
            ? lineas_plano_vincular($plano_id, $linea_id)
            : lineas_plano_desvincular($plano_id);
        echo json_encode(["ok" => $ok]);
        break;

    case "16": // crear sendero (JSON POST): {origen_tipo, origen_id, destino_tipo, destino_id, estilo, puntos:[[x,y],...]}
        $body = json_decode((string)file_get_contents("php://input"), true);
        $local = (int)($_SESSION["local_id"] ?? 0);
        $origen_tipo  = ($body["origen_tipo"] ?? "") === "linea_plano" ? "linea_plano" : "camara";
        $origen_id    = (int)($body["origen_id"] ?? 0);
        $destino_tipo = ($body["destino_tipo"] ?? "") === "linea_plano" ? "linea_plano" : "camara";
        $destino_id   = (int)($body["destino_id"] ?? 0);
        $estilo = in_array($body["estilo"] ?? "", ["recto", "ortogonal", "curvo"], true) ? $body["estilo"] : "recto";
        $puntos = is_array($body["puntos"] ?? null) ? $body["puntos"] : [];

        if ($local <= 0 || $origen_id <= 0 || $destino_id <= 0
            || ($origen_tipo === $destino_tipo && $origen_id === $destino_id)) {
            http_response_code(400);
            echo json_encode(["ok" => false, "error" => "datos inválidos"]);
            break;
        }

        DB::beginTransaction();
        try {
            $id = DB::insert(
                "INSERT INTO senderos (local_id, origen_tipo, origen_id, destino_tipo, destino_id, estilo) VALUES (?, ?, ?, ?, ?, ?)",
                [$local, $origen_tipo, $origen_id, $destino_tipo, $destino_id, $estilo]
            );
            $orden = 1;
            foreach ($puntos as $p) {
                if (!is_array($p) || !isset($p[0], $p[1])) continue;
                DB::execute(
                    "INSERT INTO senderos_puntos (sendero_id, x, y, orden) VALUES (?, ?, ?, ?)",
                    [$id, (int)$p[0], (int)$p[1], $orden++]
                );
            }
            DB::commit();
        } catch (Throwable $e) {
            DB::rollBack();
            http_response_code(500);
            echo json_encode(["ok" => false, "error" => $e->getMessage()]);
            break;
        }
        echo json_encode(["ok" => true, "id" => $id]);
        break;

    case "17": // actualizar sendero (JSON POST): {id, estilo, puntos:[[x,y],...]}
        $body = json_decode((string)file_get_contents("php://input"), true);
        $id = (int)($body["id"] ?? 0);
        $estilo = in_array($body["estilo"] ?? "", ["recto", "ortogonal", "curvo"], true) ? $body["estilo"] : "recto";
        $puntos = is_array($body["puntos"] ?? null) ? $body["puntos"] : [];
        if ($id <= 0) {
            http_response_code(400);
            echo json_encode(["ok" => false, "error" => "id de sendero inválido"]);
            break;
        }
        DB::beginTransaction();
        try {
            DB::execute("UPDATE senderos SET estilo = ? WHERE id = ?", [$estilo, $id]);
            DB::execute("DELETE FROM senderos_puntos WHERE sendero_id = ?", [$id]);
            $orden = 1;
            foreach ($puntos as $p) {
                if (!is_array($p) || !isset($p[0], $p[1])) continue;
                DB::execute(
                    "INSERT INTO senderos_puntos (sendero_id, x, y, orden) VALUES (?, ?, ?, ?)",
                    [$id, (int)$p[0], (int)$p[1], $orden++]
                );
            }
            DB::commit();
        } catch (Throwable $e) {
            DB::rollBack();
            http_response_code(500);
            echo json_encode(["ok" => false, "error" => $e->getMessage()]);
            break;
        }
        echo json_encode(["ok" => true]);
        break;

    case "18": // eliminar sendero (JSON POST): {id}
        $body = json_decode((string)file_get_contents("php://input"), true);
        $id = (int)($body["id"] ?? 0);
        if ($id <= 0) {
            http_response_code(400);
            echo json_encode(["ok" => false, "error" => "id de sendero inválido"]);
            break;
        }
        DB::beginTransaction();
        try {
            DB::execute("DELETE FROM senderos_puntos WHERE sendero_id = ?", [$id]);
            DB::execute("DELETE FROM senderos WHERE id = ?", [$id]);
            DB::commit();
        } catch (Throwable $e) {
            DB::rollBack();
            http_response_code(500);
            echo json_encode(["ok" => false, "error" => $e->getMessage()]);
            break;
        }
        echo json_encode(["ok" => true]);
        break;

    default:
        break;
}
