<?php
if (session_status() !== PHP_SESSION_ACTIVE) @session_start();

/* 
 * Visitantes — AJAX (REFACTOR Fase 4b): PDO (B9).
 */

require_once __DIR__ . "/../../../config/rutas.php";
require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/avatars.php";
require_once __DIR__ . "/../../../libs/security.php";
$local_id = rf_require_local_session();

switch ($_GET["a"]) {
    case "1": // guarda el nombre de la persona
        rf_require_csrf();
        DB::execute("UPDATE personas SET nombre = ? WHERE id = ? AND local_id = ?", [(string)($_POST["valor"] ?? ""), (int)($_POST["persona_id"] ?? 0), $local_id]);
        echo "ok";
        break;

    case "2": // es trabajador
        rf_require_csrf();
        DB::execute("UPDATE personas SET trabajador = ? WHERE id = ? AND local_id = ?", [min(1, max(0, (int)($_POST["valor"] ?? 0))), (int)($_POST["persona_id"] ?? 0), $local_id]);
        echo "ok";
        break;

    case "3": // avatar: estado y (si falta) lanzar generación (GET: ?a=3&persona=N)
        header("Content-Type: application/json; charset=utf-8");
        $persona_id = (int)($_GET["persona"] ?? 0);
        if (!DB::selectOne("SELECT id FROM personas WHERE id = ? AND local_id = ?", [$persona_id, $local_id])) { http_response_code(404); echo json_encode(["ok" => false]); break; }
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
