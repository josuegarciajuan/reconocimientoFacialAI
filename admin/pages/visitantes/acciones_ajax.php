<?php

/* 
 * Visitantes — AJAX (REFACTOR Fase 4b): PDO (B9).
 */

require_once __DIR__ . "/../../../config/rutas.php";
require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/avatars.php";

switch ($_GET["a"]) {
    case "1": // guarda el nombre de la persona
        DB::execute("UPDATE personas SET nombre = ? WHERE id = ?", [$_GET["valor"], (int)$_GET["persona_id"]]);
        echo "ok";
        break;

    case "2": // es trabajador
        DB::execute("UPDATE personas SET trabajador = ? WHERE id = ?", [(int)$_GET["valor"], (int)$_GET["persona_id"]]);
        echo "ok";
        break;

    case "3": // avatar: estado y (si falta) lanzar generación (GET: ?a=3&persona=N)
        header("Content-Type: application/json; charset=utf-8");
        $persona_id = (int)($_GET["persona"] ?? 0);
        if ($persona_id <= 0) {
            http_response_code(400);
            echo json_encode(["ok" => false, "error" => "persona inválida"]);
            break;
        }
        $fotos = avatar_fotos_candidatas($persona_id);
        $res = avatar_generar($persona_id, $fotos);
        echo json_encode([
            "ok"       => $res["ok"],
            "estado"   => $res["estado"],
            "foto_id"  => $res["foto_id"],
            "png"      => avatar_url($persona_id),
        ], JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
        break;

    default:
        break;
}
