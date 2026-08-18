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

    // Horario de fichajes (vacio => NULL => detección simple en el conciliador)
    $jornada_partida = (isset($_POST["jornada_partida"]) && (int)$_POST["jornada_partida"] === 1) ? 1 : 0;
    $hora_entrada1 = ($_POST["hora_entrada1"] ?? "") !== "" ? $_POST["hora_entrada1"] : null;
    $hora_salida1  = ($_POST["hora_salida1"] ?? "") !== "" ? $_POST["hora_salida1"] : null;
    $hora_entrada2 = ($_POST["hora_entrada2"] ?? "") !== "" ? $_POST["hora_entrada2"] : null;
    $hora_salida2  = ($_POST["hora_salida2"] ?? "") !== "" ? $_POST["hora_salida2"] : null;
    $margen_fichaje_min = max(0, (int)($_POST["margen_fichaje_min"] ?? 30));

    if (isset($_GET["id"]) and $_GET["id"] !== "") {
        $id = (int)$_GET["id"];
        DB::execute(
            "UPDATE locales SET nombre=?, url_logo=?, usuario=?, aforo_max=?,
                    jornada_partida=?, hora_entrada1=?, hora_salida1=?, hora_entrada2=?, hora_salida2=?, margen_fichaje_min=?
             WHERE id=?",
            [$nombre, $url_logo, $usuario, $aforo_max, $jornada_partida, $hora_entrada1, $hora_salida1, $hora_entrada2, $hora_salida2, $margen_fichaje_min, $id]
        );
    } else {
        $id = DB::insert(
            "INSERT INTO locales (nombre, url_logo, usuario, aforo_max, jornada_partida, hora_entrada1, hora_salida1, hora_entrada2, hora_salida2, margen_fichaje_min)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [$nombre, $url_logo, $usuario, $aforo_max, $jornada_partida, $hora_entrada1, $hora_salida1, $hora_entrada2, $hora_salida2, $margen_fichaje_min]
        );

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
        // face_enc_v2 se crea solo en el primer uso (FaceStore) — no hace falta sembrarlo
    }

    if (!empty($_POST["passw"])) {
        DB::execute("UPDATE locales SET passw = ? WHERE id = ?", [password_hash($_POST["passw"], PASSWORD_DEFAULT), $id]);
    }
}
