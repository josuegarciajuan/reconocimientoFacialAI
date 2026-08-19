<?php

/* 
 * Detector — orquestador del motor (REFACTOR Fase 4c).
 * 
 * Por cada local con cámaras encendidas:
 *   - lanza un proceso largo `clasificador.py` por cámara (asigna caras a personas).
 *   - vigila `motor/videos/<local>/<cam>/`, y cuando un vídeo está completo lo envía
 *     a `procesa_video.py` (cruces de línea + extracción de caras) con control de RAM
 *     y de nº de vídeos simultáneos (marker-files en aux/).
 */

require_once("config/rutas.php");
require_once("libs/Jos_thread.class.php");
require_once("libs/db.php");

$threads = [];
$ram = new Jos_Thread(0, "", true);

/**
 * Limpieza global de marcadores de archivado `aux/archiva_*.txt` huérfanos.
 *
 * Un marcador es huérfano cuando su proceso archiva_video.py ya no está vivo y
 * (a) el vídeo fuente ya no existe o (b) el marcador es más antiguo que
 * CONFIG_MARCADOR_HUERFANO_SEGS. Se barre TODOS los marcadores de las cámaras
 * del local, no solo los de los vídeos del listado actual `$subidos`: un marcador
 * cuyo origen ya fue borrado por procesa_video.py nunca volvería a aparecer en
 * `$subidos`, y sin esta limpieza satura CONFIG_LIMITE_ARCHIVA permanentemente
 * (los slots de archivado se cuentan precisamente con estos marcadores).
 */
function limpiar_marcadores_archiva_huerfanos(int $local_id, array $cams_local): void {
    $cams = [];
    foreach ($cams_local as $c) {
        $cams[(int)$c["id"]] = true;
    }
    $dir_aux = RUTA_PROYECTO . "aux";
    if (!is_dir($dir_aux)) {
        return;
    }
    $d = opendir($dir_aux);
    while (($el = readdir($d)) !== false) {
        if ($el === "." || $el === "..") { continue; }
        if (strpos($el, "archiva_") !== 0 || substr($el, -4) !== ".txt") { continue; }
        $video = substr($el, strlen("archiva_"), -4);
        if ($video === "") { continue; }
        $cam_id = (int) explode("_", $video)[0];
        if ($cam_id <= 0 || !isset($cams[$cam_id])) { continue; }
        $marker = $dir_aux . "/" . $el;
        $rc = [];
        exec("pgrep -f \"[a]rchiva_video.py " . $local_id . " " . $cam_id . " '" . $video . "'\" > /dev/null 2>&1; echo $?", $rc);
        $vivo = (isset($rc[0]) && trim($rc[0]) === "0");
        if ($vivo) { continue; }
        $fuente = RUTA_PROYECTO . "motor/videos/" . $local_id . "/" . $cam_id . "/" . $video;
        $sin_fuente = !file_exists($fuente);
        $viejo = (time() - @filemtime($marker)) > CONFIG_MARCADOR_HUERFANO_SEGS;
        if ($sin_fuente || $viejo) {
            @unlink($marker);
            echo "Marker archiva huérfano limpiado (global): " . $el . "\n";
        }
    }
    closedir($d);
}

while (true) {

    $locales = DB::select("SELECT id FROM locales WHERE id > 0 ORDER BY id ASC");
    foreach ($locales as $loc) {
        $local_id = (int)$loc["id"];

        $cams = DB::select("SELECT id FROM camaras WHERE local_id = ? AND encendida = 1 ORDER BY id ASC", [$local_id]);
        // limpia marcadores de archivado huérfanos ANTES de contar slots disponibles
        limpiar_marcadores_archiva_huerfanos($local_id, $cams);
        foreach ($cams as $cam) {
            $cam_id = (int)$cam["id"];

            // --- clasificador de caras (proceso largo por cámara) ---
            $nombre_clasif = "clasif_" . $local_id . "_" . $cam_id;
            $running = isset($threads[$nombre_clasif]) && $threads[$nombre_clasif]->isrunning();
            if (!$running) {
                if (isset($threads[$nombre_clasif])) {
                    $threads[$nombre_clasif]->stop();
                }
                $cmd = RUTA_PYTHON . " " . RUTA_PROYECTO . "motor/clasificador.py " . $local_id . " " . $cam_id . " --ruta " . RUTA_PROYECTO;
                echo "Lanzando clasificador: " . $cmd . "\n";
                $threads[$nombre_clasif] = new Jos_Thread($nombre_clasif, $cmd, true);
                $threads[$nombre_clasif]->start();
            }

            // --- vídeos completos a procesar ---
            $dir_videos = RUTA_PROYECTO . "motor/videos/" . $local_id . "/" . $cam_id . "/";
            $subidos = [];
            if (is_dir($dir_videos)) {
                $pesos = [];
                $dir = opendir($dir_videos);
                while (($el = readdir($dir)) !== false) {
                    if ($el !== "." && $el !== "..") {
                        // publicación atómica (moov-race): los .tmp los escribe
                        // guarda_movimientosV3.py y se renombran a .mp4 al cerrar;
                        // un .tmp huérfano (> 10 min) se limpia aquí.
                        if (substr($el, -4) === ".tmp") {
                            if (time() - @filemtime($dir_videos . $el) > CONFIG_MARCADOR_HUERFANO_SEGS) {
                                @unlink($dir_videos . $el);
                            }
                            continue;
                        }
                        $pesos[$el] = filesize($dir_videos . $el);
                    }
                }
                sleep(6);  // espera a que termine la subida/grabación
                $dir = opendir($dir_videos);
                while (($el = readdir($dir)) !== false) {
                    if ($el !== "." && $el !== ".." && substr($el, -4) !== ".tmp"
                        && isset($pesos[$el]) && $pesos[$el] === filesize($dir_videos . $el)) {
                        $subidos[] = $el;
                    }
                }
            }

            // nº de procesos en curso (análisis de caras + archivado comprimido)
            $numero_videos = 0;
            $numero_archiva = 0;
            if (is_dir(RUTA_PROYECTO . "aux")) {
                $dir = opendir(RUTA_PROYECTO . "aux");
                while (($el = readdir($dir)) !== false) {
                    if ($el === "." || $el === "..") { continue; }
                    if (strpos($el, "procesar") !== false) { continue; }
                    if (strpos($el, "archiva_") === 0) { $numero_archiva++; }
                    elseif (preg_match('/\.(avi|mp4)\.txt$/', $el)) { $numero_videos++; }
                }
            }

            foreach ($subidos as $video) {
                // ---- archivo comprimido: AVI -> MP4 H.264 (motor/archiva_video.py) ----
                // Si el MP4 ya está archivado (existe en videos_archivo) no relanzamos archiva:
                // el origen lo eliminará procesa_video al terminar su análisis. Sin esta guarda,
                // el vídeo se re-archivaría en cada pasada mientras el origen siga en disco.
                $destino_mp4 = RUTA_PROYECTO . "motor/videos_archivo/" . $local_id . "/" . $cam_id . "/"
                    . preg_replace('/\.(avi|mp4)$/i', '.mp4', $video);
                if (!file_exists($destino_mp4)) {
                    $marker_arch = RUTA_PROYECTO . "aux/archiva_" . $video . ".txt";
                    if (file_exists($marker_arch)) {
                        // marker huérfano: proceso muerto y marker viejo -> limpiar para reintentar
                        $rc_arch = [];
                        exec("pgrep -f \"[a]rchiva_video.py " . $local_id . " " . $cam_id . " '" . $video . "'\" > /dev/null 2>&1; echo $?", $rc_arch);
                        $vivo_arch = (isset($rc_arch[0]) && trim($rc_arch[0]) === "0");
                        $video_arch_ya_no_existe = !file_exists($dir_videos . $video);
                        if (!$vivo_arch && $video_arch_ya_no_existe) {
                            // archiva terminó (el AVI ya lo borró procesa_video) o murió con el origen borrado
                            @unlink($marker_arch);
                            echo "Marker archiva limpiado (vídeo ya no existe): " . $video . "\n";
                        } elseif (!$vivo_arch && (time() - @filemtime($marker_arch)) > CONFIG_MARCADOR_HUERFANO_SEGS) {
                            @unlink($marker_arch);
                            echo "Marker archiva huérfano limpiado: " . $video . "\n";
                        }
                    } elseif ($numero_archiva < (int)CONFIG_LIMITE_ARCHIVA) {
                        exec("echo '" . date("Y-m-d H:i:s") . "' > " . $marker_arch);
                        $log_arch = RUTA_PROYECTO . "motor/logs/archiva_video_" . $cam_id . ".log";
                        $cmd_arch = RUTA_PYTHON . " " . RUTA_PROYECTO . "motor/archiva_video.py " . $local_id . " " . $cam_id
                            . " '" . $video . "' --ruta " . RUTA_PROYECTO
                            . " --crf " . CONFIG_VIDEO_CRF . " --fps " . CONFIG_VIDEO_FPS_ARCHIVO
                            . " --preset " . CONFIG_VIDEO_PRESET
                            . " >> " . $log_arch . " 2>&1 &";
                        echo $cmd_arch . "\n";
                        exec($cmd_arch);
                        $numero_archiva++;
                    }
                } // fin if !file_exists($destino_mp4)

                $marker = RUTA_PROYECTO . "aux/" . $video . ".txt";

                // marker existente: ¿sigue vivo el procesa_video.py que lo creó?
                if (file_exists($marker)) {
                    $vivo = false;
                    // [p]rocesa: el corchete evita que pgrep se auto-matchee con el shell
                    // que lanza este comando (contenía el patrón literal -> siempre "vivo").
                    $rc_out = [];
                    exec("pgrep -f \"[p]rocesa_video.py " . $local_id . " " . $cam_id . " '" . $video . "'\" > /dev/null 2>&1; echo $?", $rc_out);
                    $vivo = (isset($rc_out[0]) && trim($rc_out[0]) === "0");
                    $antiguedad = time() - @filemtime($marker);
                    $video_ya_no_existe = !file_exists($dir_videos . $video);

                    if (!$vivo && $video_ya_no_existe) {
                        // procesa_video terminó pero no limpió el marker (muerte abrupta): limpiar
                        @unlink($marker);
                        echo "Marker huérfano limpiado (vídeo ya procesado): " . $video . "\n";
                        continue;
                    }
                    if (!$vivo && $antiguedad > CONFIG_MARCADOR_HUERFANO_SEGS) {
                        // proceso muerto y marker viejo: reintentar (hasta CONFIG_REINTENTOS_VIDEO)
                        $intentos = 0;
                        $f_int = RUTA_PROYECTO . "aux/" . $video . ".intentos";
                        if (file_exists($f_int)) { $intentos = (int)trim(file_get_contents($f_int)); }
                        $intentos++;
                        file_put_contents($f_int, (string)$intentos);
                        @unlink($marker);
                        if ($intentos >= CONFIG_REINTENTOS_VIDEO) {
                            @unlink($f_int);
                            echo "Vídeo descartado tras " . $intentos . " intentos: " . $video . "\n";
                        } else {
                            echo "Reintento " . $intentos . "/" . CONFIG_REINTENTOS_VIDEO . " de " . $video . "\n";
                        }
                        continue;
                    }
                    // vivo o marker reciente: en proceso, no tocar
                    continue;
                }

                if ($numero_videos >= CONFIG_LIMITE_VIDEOS) {
                    continue;
                }

                // RAM disponible
                if (!$ram->queda_ram(CONFIG_LIMITE_RAM)) {
                    echo "No queda RAM, espero...\n";
                    sleep(5);
                    continue;
                }

                exec("echo '" . date("Y-m-d H:i:s") . "' > " . RUTA_PROYECTO . "aux/" . $video . ".txt");
                exec("echo '" . date("Y-m-d H:i:s") . " - " . $video . "' >> " . RUTA_PROYECTO . "aux/procesar_" . $local_id . "_" . $cam_id . ".txt");

                // F6: log de procesa_video.py (antes /dev/null -> errores invisibles)
                $log = RUTA_PROYECTO . "motor/logs/procesa_video_" . $cam_id . ".log";
                $cmd = RUTA_PYTHON . " " . RUTA_PROYECTO . "motor/procesa_video.py " . $local_id . " " . $cam_id . " '" . $video . "' --ruta " . RUTA_PROYECTO . " >> " . $log . " 2>&1 &";
                echo $cmd . "\n";
                exec($cmd);
                $numero_videos++;
            }
        }
    }

    // Purga de vídeos antiguos (retención): cada CONFIG_VIDEO_PURGA_LOOP iteraciones
    static $loop_purga = 0;
    $loop_purga++;
    if ($loop_purga % (int)CONFIG_VIDEO_PURGA_LOOP === 0) {
        $out = [];
        exec("php " . RUTA_PROYECTO . "ws.php listado_videos_antiguos " . CONFIG_VIDEO_RETENCION_DIAS, $out);
        $rows = json_decode(implode("", $out), true);
        if (is_array($rows) && count($rows) > 0) {
            $archivo_root = realpath(RUTA_PROYECTO . "motor/videos_archivo");
            $ids = [];
            foreach ($rows as $row) {
                $file = rtrim(RUTA_PROYECTO, "/") . "/" . $row["ruta"];
                if (is_file($file)) {
                    $real = realpath($file);
                    if ($archivo_root !== false && $real !== false && strpos($real, $archivo_root) === 0) {
                        @unlink($file);
                    }
                }
                // la miniatura JPG (poster) se purga junto con el vídeo
                if (!empty($row["poster"])) {
                    $poster_file = rtrim(RUTA_PROYECTO, "/") . "/" . $row["poster"];
                    if (is_file($poster_file)) {
                        $real_p = realpath($poster_file);
                        if ($archivo_root !== false && $real_p !== false && strpos($real_p, $archivo_root) === 0) {
                            @unlink($poster_file);
                        }
                    }
                }
                $ids[] = (int)$row["id"];
            }
            if ($ids) {
                exec("php " . RUTA_PROYECTO . "ws.php borrar_videos " . implode(",", $ids));
                echo "Purga de vídeos: " . count($ids) . " registros eliminados\n";
            }
        }
    }

    sleep(1);
}
