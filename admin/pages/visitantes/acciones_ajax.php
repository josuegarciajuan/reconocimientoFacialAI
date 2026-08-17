<?php

/* 
 * Visitantes — AJAX (REFACTOR Fase 4b): PDO (B9).
 */

require_once __DIR__ . "/../../../config/rutas.php";
require_once __DIR__ . "/../../../libs/db.php";

switch ($_GET["a"]) {
    case "1": // guarda el nombre de la persona
        DB::execute("UPDATE personas SET nombre = ? WHERE id = ?", [$_GET["valor"], (int)$_GET["persona_id"]]);
        echo "ok";
        break;

    case "2": // es trabajador
        DB::execute("UPDATE personas SET trabajador = ? WHERE id = ?", [(int)$_GET["valor"], (int)$_GET["persona_id"]]);
        echo "ok";
        break;

    default:
        break;
}
