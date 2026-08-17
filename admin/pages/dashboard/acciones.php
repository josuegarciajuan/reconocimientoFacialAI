<?php

/* 
 * Dashboard — acciones (REFACTOR Fase 4b): PDO (B9).
 */

require_once __DIR__ . "/../../../libs/db.php";

switch ($_GET["accion"]) {
    case "cambiar_aforo":
        DB::execute("UPDATE locales SET aforo_actual = ? WHERE id = ?", [(int)$_GET["nuevo_aforo"], (int)$_SESSION["local_id"]]);
        break;
}
