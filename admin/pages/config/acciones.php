<?php

/* 
 * Config — acciones (REFACTOR Fase 4b): PDO (B9).
 * Crear/editar cámaras, plano, nodos y líneas.
 */

require_once __DIR__ . "/../../../libs/db.php";

$extensiones = ["jpg", "jpeg", "png", "bmp"];

switch ($_GET["accion"]) {
    case "crear":
        $url_conexion = str_replace("--jos--", "&", $_GET["url_conexion"] ?? "");
        $id = DB::insert(
            "INSERT INTO camaras (local_id, descripcion, url_conexion, sistema, puerta, salida, encendida, ipcamlive_alias, segundos_analizar, porcentaje_mov, dontCare, fps, maximo_videos, redimesionframe, sensibilidad)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (int)$_SESSION["local_id"], $_GET["nombre_nueva"], $url_conexion, (int)($_GET["sistema"] ?? 0),
                (int)($_GET["puerta"] ?? 0), (int)($_GET["salida"] ?? 0), (int)($_GET["encendida_nueva"] ?? 0),
                $_GET["ipcamlive_alias"] ?? "-",
                CONFIG_segundos_analizar, CONFIG_porcentaje_mov, CONFIG_dontCare, CONFIG_fps,
                CONFIG_maximo_videos, CONFIG_redimesionframe, CONFIG_sensibilidad,
            ]
        );

        $cmds = [];
        if (($_GET["sistema"] ?? 0) == 0) {
            $cmds[] = "mkdir -p " . URL_FTP_BASE . "motor/videos/" . $_SESSION["local_id"] . "/" . $id;
            $cmds[] = "mkdir -p " . URL_FTP_BASE . "motor/videos_lineas/" . $_SESSION["local_id"] . "/" . $id;
        }
        $cmds[] = "mkdir -p " . RUTA_PROYECTO . "motor/caras/" . $_SESSION["local_id"] . "/" . $id;
        $cmds[] = "mkdir -p " . RUTA_PROYECTO . "motor/caras/sinclasificar/" . $_SESSION["local_id"] . "/" . $id;

        foreach ($cmds as $cmd) {
            exec($cmd);
        }
        break;

    case "guardar":
        $url_conexion = str_replace("--jos--", "&", $_GET["url_conexion"] ?? "");
        $url_desdeserver = str_replace("--jos--", "&", $_GET["url_desdeserver"] ?? "");
        DB::execute(
            "UPDATE camaras SET local_id=?, descripcion=?, url_conexion=?, sistema=?, puerta=?, salida=?, encendida=?, x=?, y=?, ipcamlive_alias=?, url_desdeserver=?, segundos_analizar=?, porcentaje_mov=?, dontCare=?, fps=?, maximo_videos=?, redimesionframe=?, sensibilidad=? WHERE id=?",
            [
                (int)$_SESSION["local_id"], $_GET["nombre"], $url_conexion, (int)($_GET["sistema"] ?? 0),
                (int)($_GET["puerta"] ?? 0), (int)($_GET["salida"] ?? 0), (int)($_GET["encendida"] ?? 0),
                (int)($_GET["x"] ?? 0), (int)($_GET["y"] ?? 0), $_GET["ipcamlive_alias"] ?? "-", $url_desdeserver,
                (int)($_GET["segundos_analizar"] ?? 0), (int)($_GET["porcentaje_mov"] ?? 0), (int)($_GET["dontCare"] ?? 0),
                (int)($_GET["fps"] ?? 0), (int)($_GET["maximo_videos"] ?? 0), (int)($_GET["redimesionframe"] ?? 0),
                (int)($_GET["sensibilidad"] ?? 0), (int)$_GET["camara"],
            ]
        );
        break;

    case "plano":
        foreach ($extensiones as $ext) {
            $p = "pages/config/planos/plano_" . $_SESSION["local_id"] . "." . $ext;
            if (file_exists($p)) {
                unlink($p);
            }
        }
        $fileName = $_FILES['plano']['name'];
        $fileNameCmps = explode(".", $fileName);
        $fileExtension = strtolower(end($fileNameCmps));
        if (move_uploaded_file($_FILES['plano']['tmp_name'], "pages/config/planos/plano_" . $_SESSION["local_id"] . "." . $fileExtension)) {
            echo 'File is successfully uploaded.';
        } else {
            echo 'There was some error moving the file.';
        }
        break;

    case "eliminar_nodos":
        DB::execute("DELETE FROM nodos WHERE camara_id1 = ? AND camara_id2 = ?", [(int)$_GET["camara1"], (int)$_GET["camara2"]]);
        break;

    case "guardar_lineas":
        $v_lasx = explode(",,,", $_GET["lasx"]);
        $v_lasy = explode(",,,", $_GET["lasy"]);
        $v_losnombres = explode(",,,", $_GET["losnombres"]);
        $v_losids = explode(",,,", $_GET["losids"]);
        $camara_id = (int)$_GET["camara_id"];

        for ($i = 0; $i < count($v_losids); $i++) {
            if ($v_losids[$i] == 0) {
                $x1 = (int)$v_lasx[$i * 2];
                $y1 = (int)$v_lasy[$i * 2];
                $x2 = (int)$v_lasx[($i * 2) + 1];
                $y2 = (int)$v_lasy[($i * 2) + 1];

                $linea_id = DB::insert(
                    "INSERT INTO lineas (camara_id, nombre, x1, y1, x2, y2) VALUES (?, ?, ?, ?, ?, ?)",
                    [$camara_id, $v_losnombres[$i], $x1, $y1, $x2, $y2]
                );
                @mkdir(URL_FTP_BASE . "motor/videos_lineas/" . $_SESSION["local_id"] . "/" . $camara_id . "/" . $linea_id, 0777, true);
                @mkdir(RUTA_PROYECTO . "motor/fotos_lineas/" . $linea_id, 0777, true);
            } else {
                DB::execute("UPDATE lineas SET nombre = ? WHERE id = ?", [$v_losnombres[$i], (int)$v_losids[$i]]);
            }
        }
        break;

    case "eliminar_linea":
        DB::execute("UPDATE lineas SET eliminada = 1 WHERE id = ?", [(int)$_GET["id_linea"]]);
        break;

    case "editar_lineas":
        $v_lasx = explode(",,,", $_GET["lasx"]);
        $v_lasy = explode(",,,", $_GET["lasy"]);
        $v_losids = explode(",,,", $_GET["losids"]);
        $linea_id = (int)$_GET["linea_id"];

        for ($i = 0; $i < count($v_losids); $i++) {
            $x1 = (int)$v_lasx[$i * 2];
            $y1 = (int)$v_lasy[$i * 2];
            $x2 = (int)$v_lasx[($i * 2) + 1];
            $y2 = (int)$v_lasy[($i * 2) + 1];
            DB::execute("UPDATE lineas SET x1=?, y1=?, x2=?, y2=? WHERE id=?", [$x1, $y1, $x2, $y2, $linea_id]);
        }
        break;
}
