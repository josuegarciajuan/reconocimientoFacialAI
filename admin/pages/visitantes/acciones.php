<?php

/* 
 * Visitantes — acciones (REFACTOR Fase 4b).
 * Mutaciones migradas a PDO (B9). Unir/mover personas.
 */

require_once __DIR__ . "/../../../libs/db.php";

function generar_codigo_persona() {
    $alfabeto = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    do {
        $codigo = "";
        for ($i = 0; $i < 25; $i++) {
            $codigo .= $alfabeto[random_int(0, 61)];
        }
    } while (DB::selectOne("SELECT 1 FROM personas WHERE cod_interno = ? LIMIT 1", [$codigo]) !== null);
    return $codigo;
}

// --- unir dos personas ---
if (isset($_GET["este"]) and $_GET["este"] !== "") {
    $original = (int)$_GET["este"];
    $copia = (int)$_GET["coneste"];

    $o = DB::selectOne("SELECT cod_interno FROM personas WHERE id = ?", [$original]);
    $c = DB::selectOne("SELECT cod_interno FROM personas WHERE id = ?", [$copia]);
    if ($o && $c && $original !== $copia) {
        DB::execute("UPDATE estancias SET persona_id = ? WHERE persona_id = ?", [$original, $copia]);

        $cmd = RUTA_PYTHON . " ../motor/juntar_personas.py " . intval($_SESSION["local_id"])
             . " " . escapeshellarg($o["cod_interno"]) . " " . escapeshellarg($c["cod_interno"]);
        exec($cmd);

        DB::execute("DELETE FROM personas WHERE id = ?", [$copia]);
    }
}

// --- mover una foto a otra persona (o crear nueva) ---
if (isset($_GET["mover"]) and $_GET["mover"] !== "") {
    $foto_id = (int)$_GET["mover"];
    $persona_destino = (int)$_GET["aeste"];

    $foto = DB::selectOne("SELECT estancia_id FROM fotos WHERE id = ?", [$foto_id]);
    if ($foto) {
        $estancia = DB::selectOne("SELECT persona_id, camara_id, fecha_ini, fecha_fin, notificacion_vista FROM estancias WHERE id = ?", [$foto["estancia_id"]]);
        if ($estancia) {
            $cod_origen = "";
            $pers_origen = DB::selectOne("SELECT cod_interno FROM personas WHERE id = ?", [(int)$estancia["persona_id"]]);
            if ($pers_origen) {
                $cod_origen = $pers_origen["cod_interno"];
            }

            if ($persona_destino === 0) {
                $cam = DB::selectOne("SELECT local_id FROM camaras WHERE id = ?", [$estancia["camara_id"]]);
                $local = $cam ? (int)$cam["local_id"] : (int)$_SESSION["local_id"];
                $persona_destino = DB::insert("INSERT INTO personas (local_id, cod_interno) VALUES (?, ?)", [$local, generar_codigo_persona()]);
            }

            $pers_destino = DB::selectOne("SELECT cod_interno FROM personas WHERE id = ?", [$persona_destino]);
            $cod_destino = $pers_destino ? $pers_destino["cod_interno"] : "";

            $nueva_estancia = DB::insert(
                "INSERT INTO estancias (persona_id, camara_id, fecha_ini, fecha_fin, notificacion_vista) VALUES (?, ?, ?, ?, ?)",
                [$persona_destino, $estancia["camara_id"], $estancia["fecha_ini"], $estancia["fecha_fin"], $estancia["notificacion_vista"]]
            );
            DB::execute("UPDATE fotos SET estancia_id = ? WHERE id = ?", [$nueva_estancia, $foto_id]);

            $restantes = DB::selectOne("SELECT COUNT(*) AS n FROM fotos WHERE estancia_id = ?", [$foto["estancia_id"]]);
            if ($restantes && (int)$restantes["n"] === 0) {
                DB::execute("DELETE FROM estancias WHERE id = ?", [$foto["estancia_id"]]);
            }

            // B4: re-encodear la foto movida y actualizar face_enc_v2 (motor/cambiar_foto.py)
            if ($cod_origen !== "" && $cod_destino !== "") {
                $cmd = RUTA_PYTHON . " " . RUTA_PROYECTO . "motor/cambiar_foto.py " . intval($_SESSION["local_id"]) . " " . $foto_id
                     . " " . escapeshellarg($cod_origen) . " " . escapeshellarg($cod_destino) . " --ruta " . RUTA_PROYECTO . " > /dev/null 2>/dev/null &";
                exec($cmd);
            }
        }
    }
}

// --- subir vídeo (multipart) ---
if (isset($_GET["info"]) and $_GET["info"] === "subir_video") {
    $uploads_dir = "files/videos_registro";
    $tmp_name = $_FILES["video"]["tmp_name"];
    $name = $_GET["nombre"];
    if (move_uploaded_file($tmp_name, "$uploads_dir/$name.avi")) {
        echo "Subido correctamente";
        // 4c: disparar enrolamiento (motor/enrolamiento.py)
    } else {
        echo "NO subido";
    }
    exit;
}

// --- subir vídeo (blob) ---
if (isset($_GET["info"]) and $_GET["info"] === "subir_video2") {
    $uploads_dir = "files/videos_registro_videos";
    $name_persona = str_replace("_", "-", $_GET["nombre"]);
    $name_video = $_SESSION["local_id"] . "_" . $name_persona;
    $video_rel = $uploads_dir . "/" . $name_video . ".avi";

    $test = file_get_contents('php://input');
    file_put_contents($video_rel, $test);
    echo "Subido a:" . $video_rel . "<br />";

    // B18: enrolamiento multi-pose con el motor nuevo
    $cod_interno = generar_codigo_persona();
    DB::insert("INSERT INTO personas (local_id, cod_interno, nombre) VALUES (?, ?, ?)",
        [(int)$_SESSION["local_id"], $cod_interno, $name_persona]);
    $video_abs = RUTA_PROYECTO . "admin/" . $video_rel;
    $cmd = RUTA_PYTHON . " " . RUTA_PROYECTO . "motor/enrolamiento.py " . intval($_SESSION["local_id"])
         . " " . escapeshellarg($video_abs) . " " . escapeshellarg($cod_interno) . " --ruta " . RUTA_PROYECTO . " > /dev/null 2>/dev/null &";
    exec($cmd);
    exit;
}

// --- checkear posición de cara (test) ---
if (isset($_GET["info"]) and $_GET["info"] === "checkearPosicionCara_test") {
    $uploads_dir = "files/videos_registro";
    echo "checkearPosicionCara_test<br />";
    $terminado = false;
    $fichero_respuesta = $uploads_dir . "/" . $_SESSION["local_id"] . ".txt";
    while (!$terminado) {
        if (file_exists($fichero_respuesta)) {
            $terminado = true;
            exec("rm " . $fichero_respuesta);
        } else {
            sleep(1);
        }
    }
    echo "llego al final<br />";
    exit;
}

// --- checkear posición de cara (multipart) ---
if (isset($_GET["info"]) and $_GET["info"] === "checkearPosicionCara") {
    $uploads_dir = "files/videos_registro";
    $pos_dir = "files/videos_registro_posiciones";
    $res_dir = "files/videos_registro_resultados";

    $tmp_name = $_FILES["imagen"]["tmp_name"];
    $name = $_SESSION["local_id"];
    $posicion = $_GET["posicion"];

    if (isset($_FILES["imagen"])) {
        $file_posicion = $pos_dir . "/" . $_SESSION["local_id"] . ".txt";
        file_put_contents($file_posicion, $posicion);

        $imagen = "$uploads_dir/$name.png";
        $imagen_jpg = "$uploads_dir/$name.jpg";

        if (move_uploaded_file($tmp_name, $imagen)) {
            $image = imagecreatefrompng($imagen);
            imagejpeg($image, $imagen_jpg, 80);
            imagedestroy($image);
            exec("rm " . $imagen);

            $respuesta = 0;
            $fichero_respuesta = $res_dir . "/" . $_SESSION["local_id"] . ".txt";
            $terminado = false;
            while (!$terminado) {
                if (file_exists($fichero_respuesta)) {
                    $respuesta = file_get_contents($fichero_respuesta);
                    $terminado = true;
                    exec("rm " . $fichero_respuesta);
                } else {
                    sleep(1);
                }
            }
            echo "---resp>" . $respuesta . "<---";
        } else {
            echo "---resp>NOOK<---";
        }
    } else {
        echo "---resp>NOOK<---";
    }
    exit;
}

// --- checkear posición de cara (blob) ---
if (isset($_GET["info"]) and $_GET["info"] === "checkearPosicionCara2") {
    $uploads_dir = "files/videos_registro";
    $pos_dir = "files/videos_registro_posiciones";
    $res_dir = "files/videos_registro_resultados";

    $name = $_SESSION["local_id"];
    $posicion = $_GET["posicion"];

    $file_posicion = $pos_dir . "/" . $_SESSION["local_id"] . ".txt";
    file_put_contents($file_posicion, $posicion);

    $imagen = "$uploads_dir/$name.png";
    $imagen_jpg = "$uploads_dir/$name.jpg";

    $test = file_get_contents('php://input');
    file_put_contents($uploads_dir . "/" . $name . ".png", $test);

    $image = imagecreatefrompng($imagen);
    imagejpeg($image, $imagen_jpg, 80);
    imagedestroy($image);
    exec("rm " . $imagen);

    $respuesta = "---resp>NOOK<---";
    $fichero_respuesta = $res_dir . "/" . $_SESSION["local_id"] . ".txt";
    $espera = 30;
    $e = 0;
    $terminado = false;
    while (!$terminado) {
        if (file_exists($fichero_respuesta)) {
            $respuesta = file_get_contents($fichero_respuesta);
            $terminado = true;
            exec("rm " . $fichero_respuesta);
        } else {
            sleep(1);
            $e++;
            if ($e > $espera) {
                $terminado = true;
            }
        }
    }
    echo "---resp>" . $respuesta . "<---";
    exit;
}

if (isset($_GET["info"]) and $_GET["info"] === "pruebaAjax") {
    echo "larespuesta";
    exit;
}
