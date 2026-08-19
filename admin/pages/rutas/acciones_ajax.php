<?php

/*
 * Caminos — AJAX del player.
 * a=2: nodos entre dos cámaras (legacy, se mantiene).
 * a=3: ruta completa resuelta para el player (puntos + segmentos + líneas del plano).
 * a=4: regenerar el avatar de una persona (JSON POST {persona_id}).
 */

require_once __DIR__ . "/../../../config/rutas.php";
require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/rutas.php";
require_once __DIR__ . "/../../../libs/trayectoria.php";
require_once __DIR__ . "/../../../libs/lineas_plano.php";
require_once __DIR__ . "/../../../libs/avatars.php";
require_once __DIR__ . "/../../../libs/planos.php";

@session_start();
$local_id = (int)($_SESSION["local_id"] ?? 0);

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

    case "3": // ruta completa para el player (GET: ?a=3&inicio_id=N)
        header("Content-Type: application/json; charset=utf-8");
        $inicio_id = (int)($_GET["inicio_id"] ?? 0);
        $ruta = $inicio_id > 0 ? obtener_ruta($local_id, $inicio_id) : null;
        if (!$ruta) {
            http_response_code(404);
            echo json_encode(["ok" => false, "error" => "ruta no encontrada"]);
            break;
        }
        // Avatar del monigote (URL o "" -> fallback a círculo).
        $ruta["avatar"] = rutas_avatar_url((int)$ruta["persona_id"]);
        // Líneas del plano (con su línea de cámara vinculada) para el mapa.
        $lineas_plano = lineas_plano_del_local($local_id);
        $json = [
            "ok"  => true,
            "ruta" => $ruta,
            "lineas_plano" => $lineas_plano,
        ];
        echo json_encode($json, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        break;

    case "4": // regenerar avatar (JSON POST {persona_id})
        header("Content-Type: application/json; charset=utf-8");
        $body = json_decode((string)file_get_contents("php://input"), true);
        $persona_id = (int)($body["persona_id"] ?? 0);
        if ($persona_id <= 0) {
            http_response_code(400);
            echo json_encode(["ok" => false, "error" => "persona inválida"]);
            break;
        }
        $fotos = avatar_fotos_candidatas($persona_id);
        $res = avatar_generar($persona_id, $fotos);
        echo json_encode([
            "ok"     => $res["ok"],
            "estado" => $res["estado"],
            "png"    => avatar_url($persona_id),
        ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        break;

    default:
        break;
}
