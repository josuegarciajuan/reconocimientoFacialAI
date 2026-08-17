<?php

/*
 * Locales — acciones (REFACTOR Fase 4b): PDO (B9) + password hash (B10).
 * Crear/editar local + scaffolding de carpetas.
 */

require_once __DIR__ . "/../../../libs/db.php";

if (isset($_GET["submit"]) and $_GET["submit"] !== "") {
    $nombre = $_POST["nombre"] ?? "";
    $url_logo = $_POST["url_logo"] ?? "";
    $usuario = $_POST["usuario"] ?? "";
    $aforo_max = (int)($_POST["aforo_max"] ?? 0);

    if (isset($_GET["id"]) and $_GET["id"] !== "") {
        $id = (int)$_GET["id"];
        DB::execute("UPDATE locales SET nombre=?, url_logo=?, usuario=?, aforo_max=? WHERE id=?", [$nombre, $url_logo, $usuario, $aforo_max, $id]);
    } else {
        $id = DB::insert("INSERT INTO locales (nombre, url_logo, usuario, aforo_max) VALUES (?, ?, ?, ?)", [$nombre, $url_logo, $usuario, $aforo_max]);

        // scaffolding de carpetas (Fase 5: sustituir chmod 777 por permisos correctos)
        $cmds = [
            "mkdir -p " . URL_FTP_BASE . "motor/videos/" . $id,
            "mkdir -p " . URL_FTP_BASE . "motor/videos_lineas/" . $id,
            "mkdir -p " . RUTA_PROYECTO . "motor/caras/" . $id . "/C0",
            "mkdir -p " . RUTA_PROYECTO . "motor/caras/sinclasificar/" . $id,
            "mkdir -p " . RUTA_PROYECTO . "motor/bbdd_reconocimiento/" . $id,
            "mkdir -p " . RUTA_PROYECTO . "motor/videos/" . $id,
            "mkdir -p " . RUTA_PROYECTO . "motor/fotos_lineas/" . $id,
        ];
        foreach ($cmds as $cmd) {
            exec($cmd);
        }
        // diccionario inicial vacío (face_enc_v2)
        @copy(RUTA_PROYECTO . "motor/inicial/face_enc_v2", RUTA_PROYECTO . "motor/bbdd_reconocimiento/" . $id . "/face_enc_v2");
    }

    if (!empty($_POST["passw"])) {
        DB::execute("UPDATE locales SET passw = ? WHERE id = ?", [password_hash($_POST["passw"], PASSWORD_DEFAULT), $id]);
    }
}
