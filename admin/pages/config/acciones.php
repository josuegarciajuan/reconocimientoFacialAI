<?php

/* 
 * Config — acciones (REFACTOR Fase 4b): PDO (B9).
 * Crear/editar cámaras, plano, fortalezas (locales) y líneas.
 *
 * 2026-08-19: se retiran "Alias IPCamlive" y "Origen de vídeo" del alta/edición
 * de cámara (sistema=0, ipcamlive_alias='-'). Se añaden local_crear/local_guardar
 * (fortalezas inline dentro de La Forja).
 */

require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/planos.php";
require_once __DIR__ . "/../../../libs/calibracion.php";

$extensiones = plano_extensiones();

/* Local de la sesión (con fallback defensivo). */
$local_id = (int)($_SESSION["local_id"] ?? 0);

switch ($_GET["accion"] ?? "") {
    case "crear":
        $url_conexion = str_replace("--jos--", "&", $_GET["url_conexion"] ?? "");
        $id = DB::insert(
            "INSERT INTO camaras (local_id, descripcion, url_conexion, sistema, puerta, salida, encendida, ipcamlive_alias, segundos_analizar, porcentaje_mov, dontCare, fps, maximo_videos, redimesionframe, sensibilidad, alarma_heredar, alarma_24h)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)",
            [
                (int)$_SESSION["local_id"], $_GET["nombre_nueva"], $url_conexion, 0,
                (int)($_GET["puerta"] ?? 0), (int)($_GET["salida"] ?? 0), (int)($_GET["encendida_nueva"] ?? 0),
                "-",
                CONFIG_segundos_analizar, CONFIG_porcentaje_mov, CONFIG_dontCare, CONFIG_fps,
                CONFIG_maximo_videos, CONFIG_redimesionframe, CONFIG_sensibilidad,
                (int)($_GET["alarma_24h"] ?? 0),
            ]
        );

        $cmds = [
            "mkdir -p " . URL_FTP_BASE . "motor/videos/" . $_SESSION["local_id"] . "/" . $id,
            "mkdir -p " . URL_FTP_BASE . "motor/videos_lineas/" . $_SESSION["local_id"] . "/" . $id,
            "mkdir -p " . RUTA_PROYECTO . "motor/caras/" . $_SESSION["local_id"] . "/" . $id,
            "mkdir -p " . RUTA_PROYECTO . "motor/caras/sinclasificar/" . $_SESSION["local_id"] . "/" . $id,
        ];

        foreach ($cmds as $cmd) {
            exec($cmd);
        }
        break;

    case "guardar":
        $url_conexion = str_replace("--jos--", "&", $_GET["url_conexion"] ?? "");
        $url_desdeserver = str_replace("--jos--", "&", $_GET["url_desdeserver"] ?? "");
        // Vigilancia (alarmas de inactividad): por defecto se hereda del local
        $alarma_heredar = (int)($_GET["alarma_heredar"] ?? 1);
        $alarma_24h = (int)($_GET["alarma_24h"] ?? 0);
        $alarma_hora_inicio = ($_GET["alarma_hora_inicio"] ?? "") !== "" ? $_GET["alarma_hora_inicio"] : null;
        $alarma_hora_fin    = ($_GET["alarma_hora_fin"] ?? "") !== "" ? $_GET["alarma_hora_fin"] : null;
        DB::execute(
            "UPDATE camaras SET local_id=?, descripcion=?, url_conexion=?, sistema=?, puerta=?, salida=?, encendida=?, ipcamlive_alias=?, url_desdeserver=?, segundos_analizar=?, porcentaje_mov=?, dontCare=?, fps=?, maximo_videos=?, redimesionframe=?, sensibilidad=?, alarma_heredar=?, alarma_hora_inicio=?, alarma_hora_fin=?, alarma_24h=? WHERE id=?",
            [
                (int)$_SESSION["local_id"], $_GET["nombre"], $url_conexion, 0,
                (int)($_GET["puerta"] ?? 0), (int)($_GET["salida"] ?? 0), (int)($_GET["encendida"] ?? 0),
                "-", $url_desdeserver,
                (int)($_GET["segundos_analizar"] ?? 0), (int)($_GET["porcentaje_mov"] ?? 0), (int)($_GET["dontCare"] ?? 0),
                (int)($_GET["fps"] ?? 0), (int)($_GET["maximo_videos"] ?? 0), (int)($_GET["redimesionframe"] ?? 0),
                (int)($_GET["sensibilidad"] ?? 0),
                $alarma_heredar, $alarma_hora_inicio, $alarma_hora_fin, $alarma_24h,
                (int)$_GET["camara"],
            ]
        );
        break;

    case "plano":
        foreach ($extensiones as $ext) {
            $p = "pages/config/planos/plano_" . $local_id . "." . $ext;
            if (file_exists($p)) {
                unlink($p);
            }
        }
        $fileName = $_FILES['plano']['name'];
        $fileNameCmps = explode(".", $fileName);
        $fileExtension = strtolower(end($fileNameCmps));
        if (!is_dir("pages/config/planos")) {
            @mkdir("pages/config/planos", 0777, true);
        }
        if (move_uploaded_file($_FILES['plano']['tmp_name'], "pages/config/planos/plano_" . $local_id . "." . $fileExtension)) {
            DB::execute("UPDATE locales SET plano_activo = 'subida' WHERE id = ?", [$local_id]);
        }
        header("Location: ?page=config&tab=plano");
        exit;
        break;

    /* Croquis dibujado a mano alzada: recibe un dataURL PNG (canvas.toDataURL). */
    case "plano_dibujo":
        $data = $_POST["plano_dibujo"] ?? "";
        if (preg_match('#^data:image/png;base64,(.+)$#s', $data, $m)) {
            $bin = base64_decode($m[1]);
            if ($bin !== false && strlen($bin) > 100) {
                $dibujo = "pages/config/planos/plano_dibujo_" . $local_id . ".png";
                if (!is_dir("pages/config/planos")) {
                    @mkdir("pages/config/planos", 0777, true);
                }
                if (file_exists($dibujo)) {
                    $hist = "pages/config/planos/historial";
                    if (!is_dir($hist)) {
                        @mkdir($hist, 0777, true);
                    }
                    @copy($dibujo, $hist . "/plano_dibujo_" . $local_id . "_" . date("Ymd_His") . ".png");
                }
                if (file_put_contents($dibujo, $bin) !== false) {
                    DB::execute("UPDATE locales SET plano_activo = 'dibujo' WHERE id = ?", [$local_id]);
                    header("Location: ?page=config&tab=plano");
                    exit;
                }
            }
        }
        echo "Error: no se pudo guardar el croquis dibujado.";
        break;

    /* Cambiar qué plano se usa como fondo (imagen subida o croquis dibujado). */
    case "plano_activo":
        $tipo = ($_GET["tipo"] ?? "") === "dibujo" ? "dibujo" : "subida";
        $existe = ($tipo === "dibujo")
            ? plano_dibujo_existe($local_id)
            : (bool)plano_subida_existe($local_id);
        if ($existe) {
            DB::execute("UPDATE locales SET plano_activo = ? WHERE id = ?", [$tipo, $local_id]);
        }
        header("Location: ?page=config&tab=plano");
        exit;
        break;

    /* ---------- Fortalezas (locales) inline ---------- */

    case "local_crear":
        $nombre = trim($_POST["nombre"] ?? "");
        $url_logo = trim($_POST["url_logo"] ?? "");
        $usuario = trim($_POST["usuario"] ?? "");
        $aforo_max = (int)($_POST["aforo_max"] ?? 0);
        $passw = (string)($_POST["passw"] ?? "");

        $jornada_partida = (isset($_POST["jornada_partida"]) && (int)$_POST["jornada_partida"] === 1) ? 1 : 0;
        $hora_entrada1 = ($_POST["hora_entrada1"] ?? "") !== "" ? $_POST["hora_entrada1"] : null;
        $hora_salida1  = ($_POST["hora_salida1"] ?? "") !== "" ? $_POST["hora_salida1"] : null;
        $hora_entrada2 = ($_POST["hora_entrada2"] ?? "") !== "" ? $_POST["hora_entrada2"] : null;
        $hora_salida2  = ($_POST["hora_salida2"] ?? "") !== "" ? $_POST["hora_salida2"] : null;
        $margen_fichaje_min = max(0, (int)($_POST["margen_fichaje_min"] ?? 30));

        // Vigilancia (alarmas de inactividad)
        $alarma_activa = (isset($_POST["alarma_activa"]) && (int)$_POST["alarma_activa"] === 1) ? 1 : 0;
        $alarma_24h = (isset($_POST["alarma_24h"]) && (int)$_POST["alarma_24h"] === 1) ? 1 : 0;
        $alarma_hora_inicio = ($_POST["alarma_hora_inicio"] ?? "") !== "" ? $_POST["alarma_hora_inicio"] : null;
        $alarma_hora_fin    = ($_POST["alarma_hora_fin"] ?? "") !== "" ? $_POST["alarma_hora_fin"] : null;
        $alarma_margen_min  = max(0, (int)($_POST["alarma_margen_min"] ?? 0));

        $id = DB::insert(
            "INSERT INTO locales (nombre, url_logo, usuario, aforo_max, aforo_actual, jornada_partida, hora_entrada1, hora_salida1, hora_entrada2, hora_salida2, margen_fichaje_min,
                    alarma_activa, alarma_hora_inicio, alarma_hora_fin, alarma_24h, alarma_margen_min)
             VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [$nombre, $url_logo, $usuario, $aforo_max, $jornada_partida, $hora_entrada1, $hora_salida1, $hora_entrada2, $hora_salida2, $margen_fichaje_min,
             $alarma_activa, $alarma_hora_inicio, $alarma_hora_fin, $alarma_24h, $alarma_margen_min]
        );
        if ($passw !== "") {
            DB::execute("UPDATE locales SET passw = ? WHERE id = ?", [password_hash($passw, PASSWORD_DEFAULT), $id]);
        }

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

        header("Location: ?page=config&tab=locales&sub=listar");
        exit;
        break;

    case "local_guardar":
        $id = (int)($_GET["id"] ?? 0);
        if ($id <= 0) {
            header("Location: ?page=config&tab=locales&sub=listar");
            exit;
        }
        $nombre = trim($_POST["nombre"] ?? "");
        $url_logo = trim($_POST["url_logo"] ?? "");
        $usuario = trim($_POST["usuario"] ?? "");
        $aforo_max = (int)($_POST["aforo_max"] ?? 0);
        $passw = (string)($_POST["passw"] ?? "");

        $jornada_partida = (isset($_POST["jornada_partida"]) && (int)$_POST["jornada_partida"] === 1) ? 1 : 0;
        $hora_entrada1 = ($_POST["hora_entrada1"] ?? "") !== "" ? $_POST["hora_entrada1"] : null;
        $hora_salida1  = ($_POST["hora_salida1"] ?? "") !== "" ? $_POST["hora_salida1"] : null;
        $hora_entrada2 = ($_POST["hora_entrada2"] ?? "") !== "" ? $_POST["hora_entrada2"] : null;
        $hora_salida2  = ($_POST["hora_salida2"] ?? "") !== "" ? $_POST["hora_salida2"] : null;
        $margen_fichaje_min = max(0, (int)($_POST["margen_fichaje_min"] ?? 30));

        // Vigilancia (alarmas de inactividad)
        $alarma_activa = (isset($_POST["alarma_activa"]) && (int)$_POST["alarma_activa"] === 1) ? 1 : 0;
        $alarma_24h = (isset($_POST["alarma_24h"]) && (int)$_POST["alarma_24h"] === 1) ? 1 : 0;
        $alarma_hora_inicio = ($_POST["alarma_hora_inicio"] ?? "") !== "" ? $_POST["alarma_hora_inicio"] : null;
        $alarma_hora_fin    = ($_POST["alarma_hora_fin"] ?? "") !== "" ? $_POST["alarma_hora_fin"] : null;
        $alarma_margen_min  = max(0, (int)($_POST["alarma_margen_min"] ?? 0));

        DB::execute(
            "UPDATE locales SET nombre=?, url_logo=?, usuario=?, aforo_max=?,
                    jornada_partida=?, hora_entrada1=?, hora_salida1=?, hora_entrada2=?, hora_salida2=?, margen_fichaje_min=?,
                    alarma_activa=?, alarma_hora_inicio=?, alarma_hora_fin=?, alarma_24h=?, alarma_margen_min=?
             WHERE id=?",
            [$nombre, $url_logo, $usuario, $aforo_max, $jornada_partida, $hora_entrada1, $hora_salida1, $hora_entrada2, $hora_salida2, $margen_fichaje_min,
             $alarma_activa, $alarma_hora_inicio, $alarma_hora_fin, $alarma_24h, $alarma_margen_min, $id]
        );
        if ($passw !== "") {
            DB::execute("UPDATE locales SET passw = ? WHERE id = ?", [password_hash($passw, PASSWORD_DEFAULT), $id]);
        }

        header("Location: ?page=config&tab=locales&sub=listar");
        exit;
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

    /* ================= La Forja · Templar — calibrador ================= */

    /* Aplica las recomendaciones pendientes de una cámara (por_camara del JSON del probe).
     * GET: camara, parametro (opcional: solo ese). El resto queda pendiente. */
    case "calibrar_aplicar":
        $camara_id = (int)($_GET["camara"] ?? 0);
        $parametro = (string)($_GET["parametro"] ?? "");
        $camara = DB::selectOne("SELECT id, local_id FROM camaras WHERE id = ? AND local_id = ?", [$camara_id, $local_id]);
        if (!$camara) {
            echo "Cámara no encontrada.";
            break;
        }
        $reco = calib_recomendaciones_camara($camara_id);
        if (!$reco) {
            echo "No hay recomendaciones pendientes para esta cámara.";
            break;
        }
        $params = [];
        foreach ($reco as $k => $v) {
            if ($parametro !== "" && $k !== $parametro) {
                continue;
            }
            if (array_key_exists("recomendado", $v)) {
                $params[$k] = $v["recomendado"];
            }
        }
        calib_aplicar_parametros($local_id, $camara_id, $params);
        header("Location: ?page=config&tab=camaras&sub=editar&camara=" . $camara_id);
        exit;

    /* Restaura los 7 parámetros de una cámara a los valores de fábrica (CONFIG_*). */
    case "calibrar_restaurar_camara":
        $camara_id = (int)($_GET["camara"] ?? 0);
        $camara = DB::selectOne("SELECT id, local_id FROM camaras WHERE id = ? AND local_id = ?", [$camara_id, $local_id]);
        if ($camara) {
            calib_restaurar_camara($local_id, $camara_id);
        }
        header("Location: ?page=config&tab=camaras&sub=editar&camara=" . $camara_id);
        exit;

    /* Restaura un único parámetro de una cámara a su valor de fábrica. */
    case "calibrar_restaurar_parametro":
        $camara_id = (int)($_GET["camara"] ?? 0);
        $parametro = (string)($_GET["parametro"] ?? "");
        $camara = DB::selectOne("SELECT id, local_id FROM camaras WHERE id = ? AND local_id = ?", [$camara_id, $local_id]);
        if ($camara) {
            $factory = [];
            foreach (calib_parametros() as $k => $meta) {
                if ($k === $parametro) {
                    $factory[$k] = $meta["factory"];
                }
            }
            if ($factory) {
                calib_aplicar_parametros($local_id, $camara_id, $factory);
            }
        }
        header("Location: ?page=config&tab=camaras&sub=editar&camara=" . $camara_id);
        exit;

    /* Restaura las variables globales RF_* del .env a sus valores de fábrica
     * (borra la línea para que aplique el default del código). Con copia de seguridad. */
    case "calibrar_restaurar_globales":
        $tocadas = calib_restaurar_globales($local_id);
        header("Location: ?page=config&tab=camaras&sub=calibrar&modo=general");
        exit;

    /* Restaura UNA variable global del .env a fábrica (borra solo esa línea). */
    case "calibrar_restaurar_global":
        $k = (string)($_GET["parametro"] ?? "");
        if (preg_match('/^RF_[A-Z0-9_]+$/', $k)) {
            $env = RUTA_PROYECTO . ".env";
            if (is_file($env)) {
                $lineas = file($env, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
                $resto = [];
                $antes = null;
                foreach ($lineas as $l) {
                    $l = rtrim($l);
                    if (preg_match('/^' . preg_quote($k, "/") . '\s*=/', $l)) {
                        $antes = trim(explode("=", $l, 2)[1] ?? "", "\"'");
                    } else {
                        $resto[] = $l;
                    }
                }
                if ($antes !== null) {
                    @copy($env, $env . ".bak." . date("Ymd_His"));
                    @file_put_contents($env, implode("\n", $resto) . "\n");
                    calib_journal($local_id, 0, "global", $k, $antes, "(default)");
                }
            }
        }
        header("Location: ?page=config&tab=camaras&sub=calibrar&modo=general");
        exit;

    /* Aplica al .env las recomendaciones globales (RF_*) pendientes de la cámara. */
    case "calibrar_aplicar_global":
        $camara_id = (int)($_GET["camara"] ?? 0);
        if ($camara_id > 0) {
            calib_aplicar_globales($local_id, $camara_id);
        }
        header("Location: ?page=config&tab=camaras&sub=calibrar&modo=general");
        exit;
}
