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

// --- unir dos personas (P5: atómico BD+galería en Python, síncrono con carga) ---
if (isset($_GET["este"]) and $_GET["este"] !== "") {
    $original = (int)$_GET["este"];
    $copia = (int)$_GET["coneste"];

    $o = DB::selectOne("SELECT cod_interno FROM personas WHERE id = ?", [$original]);
    $c = DB::selectOne("SELECT cod_interno FROM personas WHERE id = ?", [$copia]);
    if ($o && $c && $original !== $copia) {
        // juntar_personas_v2.py hace TODO en una transacción: snapshot F6 (store+BD),
        // merge de galería conservando `sources`, UPDATE estancias y DELETE personas.
        $cmd = RUTA_PYTHON . " " . RUTA_PROYECTO . "motor/juntar_personas_v2.py " . intval($_SESSION["local_id"])
             . " " . escapeshellarg($o["cod_interno"]) . " " . escapeshellarg($c["cod_interno"])
             . " --ruta " . RUTA_PROYECTO . " 2>&1";
        $salida = shell_exec($cmd);
        error_log("[unir] " . trim((string)$salida));
    }
}

// --- mover UNA foto a otra persona (o crear nueva) — DB + galería con proveniencia ---
function mover_foto_db($foto_id, $persona_destino) {
    $foto = DB::selectOne("SELECT estancia_id FROM fotos WHERE id = ?", [$foto_id]);
    if (!$foto) {
        return null;
    }
    $estancia = DB::selectOne("SELECT persona_id, camara_id, fecha_ini, fecha_fin, notificacion_vista FROM estancias WHERE id = ?", [$foto["estancia_id"]]);
    if (!$estancia) {
        return null;
    }
    $pers_origen = DB::selectOne("SELECT cod_interno FROM personas WHERE id = ?", [(int)$estancia["persona_id"]]);
    $cod_origen = $pers_origen ? $pers_origen["cod_interno"] : "";

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

    // Movement is append-only evidence. Never rewrite/delete the original
    // classification audit; future classifier runs use the marker to label
    // their own audit as post_move.
    DB::insert(
        "INSERT INTO foto_audit_events (foto_id, event_type, from_person_code, to_person_code) VALUES (?, ?, ?, ?)",
        [(int)$foto_id, "move", $cod_origen !== "" ? $cod_origen : null, $cod_destino !== "" ? $cod_destino : null]
    );
    $marker_dir = RUTA_PROYECTO . "motor/audit_queue/" . (string)$_SESSION["local_id"];
    if (!is_dir($marker_dir)) {
        @mkdir($marker_dir, 0770, true);
    }
    @file_put_contents($marker_dir . "/.last_move", date("c"), LOCK_EX);

    $restantes = DB::selectOne("SELECT COUNT(*) AS n FROM fotos WHERE estancia_id = ?", [$foto["estancia_id"]]);
    if ($restantes && (int)$restantes["n"] === 0) {
        DB::execute("DELETE FROM estancias WHERE id = ?", [$foto["estancia_id"]]);
    }

    return ["cod_origen" => $cod_origen, "cod_destino" => $cod_destino];
}

if (isset($_GET["mover"]) and $_GET["mover"] !== "") {
    $foto_id = (int)$_GET["mover"];
    $persona_destino = (int)$_GET["aeste"];
    $cod = mover_foto_db($foto_id, $persona_destino);

    // B4/P4: re-encodear la foto movida y actualizar face_enc_v2 con PROVENIENCIA
    // (motor/cambiar_foto.py usa move_by_source: quita de origen EXACTAMENTE lo
    // que aportó esa foto y lo añade al destino).
    if ($cod && $cod["cod_origen"] !== "" && $cod["cod_destino"] !== "") {
        $cmd = RUTA_PYTHON . " " . RUTA_PROYECTO . "motor/cambiar_foto.py " . intval($_SESSION["local_id"]) . " " . $foto_id
             . " " . escapeshellarg($cod["cod_origen"]) . " " . escapeshellarg($cod["cod_destino"])
             . " --ruta " . RUTA_PROYECTO . " 2>&1";
        $salida = shell_exec($cmd);
        error_log("[mover] " . trim((string)$salida));
    }
}

// --- separar VARIAS fotos (bulk) y llevarlas a otra persona (o nueva) — P4 ---
if (isset($_GET["separar"]) and $_GET["separar"] !== "") {
    $foto_ids = array_values(array_filter(array_map("intval", explode(",", $_GET["separar"])), fn($v) => $v > 0));
    $persona_destino = (int)$_GET["aeste"];

    if ($foto_ids) {
        // agrupar por persona de origen (la UI las selecciona dentro de un mismo perfil).
        // mover_foto_db ya crea la persona nueva si `aeste=0` y devuelve los cod_interno.
        $grupos = [];   // cod_origen -> ["fotos" => [...], "destino" => cod_destino]
        foreach ($foto_ids as $fid) {
            $cod = mover_foto_db($fid, $persona_destino);
            if ($cod && $cod["cod_origen"] !== "" && $cod["cod_destino"] !== "") {
                $grupos[$cod["cod_origen"]]["fotos"][] = $fid;
                $grupos[$cod["cod_origen"]]["destino"] = $cod["cod_destino"];
            }
        }
        // por cada persona de origen: una sola pasada de galería con proveniencia
        foreach ($grupos as $cod_origen => $g) {
            $cmd = RUTA_PYTHON . " " . RUTA_PROYECTO . "motor/separar_personas.py " . intval($_SESSION["local_id"])
                 . " " . escapeshellarg($cod_origen) . " " . escapeshellarg($g["destino"])
                 . " --fotos " . implode(",", $g["fotos"]) . " --ruta " . RUTA_PROYECTO . " 2>&1";
            $salida = shell_exec($cmd);
            error_log("[separar] " . trim((string)$salida));
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
