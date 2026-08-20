<?php

/*
 * La Almenara — AJAX (teléfonos de recepción + marcar leídas).
 * Patrón idéntico al resto de páginas: sesión + local_id + redirección.
 */

@session_start();
require_once __DIR__ . "/../../../config/rutas.php";
require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/alarmas.php";

$local_id = (int)($_SESSION["local_id"] ?? 0);

switch ($_GET["a"]) {
    case "1": // añadir teléfono de recepción
        $nombre = trim((string)($_POST["nombre"] ?? ""));
        $telefono = trim((string)($_POST["telefono"] ?? ""));
        if ($nombre !== "" && $telefono !== "") {
            DB::insert(
                "INSERT INTO alarmas_telefonos (local_id, nombre, telefono) VALUES (?, ?, ?)",
                [$local_id, $nombre, $telefono]
            );
        }
        header("Location: ?page=alarmas&mode=config");
        exit;

    case "2": // quitar teléfono de recepción
        DB::execute(
            "DELETE FROM alarmas_telefonos WHERE id = ? AND local_id = ?",
            [(int)($_GET["id"] ?? 0), $local_id]
        );
        header("Location: ?page=alarmas&mode=config");
        exit;

    case "3": // marcar todas las alarmas del local como leídas
        alarma_marcar_leidas($local_id);
        echo "ok";
        break;
}
