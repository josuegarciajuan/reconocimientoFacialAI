<?php

/* 
 * Clasificador V2 — p3: ingesta a BD (REFACTOR Fase 5: PDO).
 * Recorre `motor/caras/<local>/<cam>/<persona>/` y crea personas/estancias/fotos.
 * (El motor Python clasificador.py escribe las fotos clasificadas + face_enc_v2;
 * este daemon es el puente hacia la BD del panel.)
 */

require_once("config/rutas.php");
require_once("libs/db.php");
require_once("libs/fechas.php");
require_once("libs/vinculos.php");
require_once("libs/photo_audit.php");

$path = "motor/caras/";

while (true) {
    recorre_dir($path, 1);
    sleep(1);
}

function recorre_dir($path, $nivel) {
    if (!is_dir($path)) {
        return;
    }
    $dir = opendir($path);
    if (!$dir) {
        return;
    }
    while (($elemento = readdir($dir)) !== false) {
        if ($elemento === "." || $elemento === "..") {
            continue;
        }
        $ruta = rtrim($path, "/") . "/" . $elemento;
        if (is_dir($ruta)) {
            switch ($nivel) {
                case 1:
                    $local_id = $elemento;
                    if ($local_id !== "aux" && $local_id !== "sinclasificar" && $local_id !== "inicial"
                        && $local_id !== "sinclasificar_videos" && $local_id !== "sinclasificar_bck_haycarasde2022") {
                        recorre_dir($ruta . "/", 2);
                    }
                    break;
                case 2:
                    recorre_dir($ruta . "/", 3);
                    break;
                case 3:
                    recorre_dir($ruta . "/", 4);
                    break;
                default:
                    break;
            }
        } else {
            procesa_foto($ruta, $elemento);
        }
    }
    closedir($dir);
}

function procesa_foto_hq($ruta, $elemento) {
    // $elemento = "<nombre>.jpg.hq". El "<nombre>.jpg" es el
    // `nombre_real_antesconversion` de la foto rápida ya publicada.
    $base = substr($elemento, 0, -3);   // quita ".hq"
    $foto = DB::selectOne(
        "SELECT id FROM fotos WHERE nombre_real_antesconversion = ? LIMIT 1",
        [$base]
    );
    if (!$foto) {
        // la foto rápida aún no se ha ingerido: reintentar en la siguiente pasada
        return;
    }
    $dest = "admin/caras_procesadas/" . (int)$foto["id"] . ".jpg";
    if (is_file($ruta) && filesize($ruta) > 0) {
        @rename($ruta, $dest);
        DB::execute("UPDATE fotos SET generada_hq = 1 WHERE id = ?", [(int)$foto["id"]]);
    }
}

function procesa_foto($ruta, $elemento) {
    // Fase HQ: "<nombre>.jpg.hq" es la versión mejorada (x4plus) de una foto
    // rápida ya publicada. Se aplica SOBREESCRIBIENDO la rápida (sin duplicar)
    // y marca generada_hq=1 para que el panel la "autonitida" sin recargar.
    if (substr($elemento, -3) === ".hq") {
        procesa_foto_hq($ruta, $elemento);
        return;
    }

    $aux = explode("/", $ruta);
    // motor/caras/<local>/<cam>/<persona>/<foto>
    $n = count($aux);
    if ($n < 5) {
        return;
    }
    $local_id = $aux[$n - 4];
    $camara_id = $aux[$n - 3];
    $persona = $aux[$n - 2];
    if ($camara_id === "C0") {
        $camara_id = "0";
    }

    $kk = explode("_", $elemento);
    $identificador_unico = str_replace(".jpg", "", $kk[count($kk) - 1]);

    // entrada/salida (nombres unidos con ----)
    $entrada = $elemento;
    $salida = $elemento;
    if (strpos($elemento, "----") !== false) {
        $aux2 = explode("----", $elemento);
        $entrada = $aux2[0] !== "" ? $aux2[0] : $aux2[1];
        $salida = $aux2[1];
    }

    $datos["entrada"] = extrae_datos($entrada);
    $datos["salida"] = extrae_datos($salida);
    if ($camara_id === "0") {
        $datos["entrada"]["fecha_completa_consegs"] = $datos["entrada"]["fecha_completa"];
        $datos["salida"]["fecha_completa_consegs"] = $datos["salida"]["fecha_completa"];
    }

    $persona = str_replace("'", "", $persona);

    $p = DB::selectOne("SELECT id FROM personas WHERE cod_interno = ?", [$persona]);
    if (!$p) {
        // persona nueva
        $persona_id = DB::insert("INSERT INTO personas (local_id, cod_interno) VALUES (?, ?)", [$local_id, $persona]);
        $estancia_id = DB::insert(
            "INSERT INTO estancias (persona_id, camara_id, fecha_ini, fecha_fin) VALUES (?, ?, ?, ?)",
            [$persona_id, $camara_id, $datos["entrada"]["fecha_completa_consegs"], $datos["salida"]["fecha_completa_consegs"]]
        );
        if ($camara_id !== "0") {
            control_aforo($camara_id, $local_id);
        }
    } else {
        $persona_id = $p["id"];

        $fecha_ultima = date("Y-m-d H:i:s", strtotime("-" . CONFIG_UMBRAL_ESTANCIA . " second", strtotime($datos["entrada"]["fecha_completa_consegs"])));

        $est = DB::selectOne(
            "SELECT id, fecha_fin FROM estancias
             WHERE camara_id = ? AND fecha_fin >= ? AND fecha_fin <= ?
             ORDER BY id ASC LIMIT 1",
            [$camara_id, $fecha_ultima, $datos["entrada"]["fecha_completa_consegs"]]
        );
        if ($est) {
            // ampliar estancia existente y descartar fotos duplicadas (conserva la 1ª)
            DB::execute("UPDATE estancias SET fecha_fin = ? WHERE id = ?", [$datos["salida"]["fecha_completa_consegs"], $est["id"]]);
            $estancia_id = $est["id"];

            $fotos = DB::select("SELECT id FROM fotos WHERE estancia_id = ? ORDER BY id ASC", [$estancia_id]);
            foreach ($fotos as $i => $f) {
                if ($i > 0) {
                    @unlink("admin/caras_procesadas/" . $f["id"] . ".jpg");
                    DB::execute("DELETE FROM fotos WHERE id = ?", [$f["id"]]);
                }
            }
        } else {
            $estancia_id = DB::insert(
                "INSERT INTO estancias (persona_id, camara_id, fecha_ini, fecha_fin) VALUES (?, ?, ?, ?)",
                [$persona_id, $camara_id, $datos["entrada"]["fecha_completa_consegs"], $datos["salida"]["fecha_completa_consegs"]]
            );
            if ($camara_id !== "0") {
                control_aforo($camara_id, $local_id);
            }
        }
    }

    // Enlace inmediato de la estancia con su vídeo de movimiento (misma cámara + solape).
    // El daemon vinculador.php (libs/vinculos.php) es la red de seguridad/backfill.
    vinculos_vincular_estancia(
        ["id" => $estancia_id, "camara_id" => $camara_id,
         "fecha_ini" => $datos["entrada"]["fecha_completa_consegs"],
         "fecha_fin" => $datos["salida"]["fecha_completa_consegs"]],
        (int)CONFIG_VINCULO_MARGEN_SEGS
    );

    $foto_id = DB::insert(
        "INSERT INTO fotos (estancia_id, nombre_real_antesconversion, identificador_unico) VALUES (?, ?, ?)",
        [$estancia_id, $elemento, $identificador_unico]
    );
    // identificador_unico is the classifier-generated correlation id. The audit
    // sidecar was produced before this INSERT; consume it only after fotos.id exists.
    ingest_photo_audit((int)$foto_id, $identificador_unico, (string)$local_id, (string)$camara_id);
    @rename($ruta, "admin/caras_procesadas/" . $foto_id . ".jpg");
}

function extrae_datos($file) {
    $return = [];
    $file = str_replace(".jpg", "", $file);
    $file = str_replace(".avi", "", $file);

    $aux = explode("_", $file);
    if (count($aux) < 4) {
        return ["fecha_completa" => date("Y-m-d H:i:s"), "fecha_completa_consegs" => date("Y-m-d H:i:s")];
    }
    $return["camara_id"] = $aux[0];
    $return["fecha"] = $aux[1];

    $aux2 = explode(".", $aux[2]);
    $return["hora"] = $aux2[0];

    $aux2 = explode(".", $aux[3]);
    $return["segundos"] = $aux2[0];

    $return["fecha_completa"] = $return["fecha"] . " " . $return["hora"];
    $fecha_foto = strtotime("+" . $return["segundos"] . " second", strtotime($return["fecha_completa"]));
    $return["fecha_completa_consegs"] = date("Y-m-d H:i:s", $fecha_foto);

    return $return;
}

function control_aforo($camara_id, $local_id) {
    $c = DB::selectOne("SELECT puerta, salida FROM camaras WHERE id = ?", [$camara_id]);
    if (!$c) {
        return;
    }
    $loc = DB::selectOne("SELECT aforo_actual FROM locales WHERE id = ?", [$local_id]);
    if (!$loc) {
        return;
    }
    $aforo = (int)$loc["aforo_actual"];
    if ((int)$c["puerta"] === 1) {
        $aforo++;
    }
    if ((int)$c["salida"] === 1) {
        $aforo--;
    }
    DB::execute("UPDATE locales SET aforo_actual = ? WHERE id = ?", [$aforo, $local_id]);
}
