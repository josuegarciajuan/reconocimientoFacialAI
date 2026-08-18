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

while (true) {

    $locales = DB::select("SELECT id FROM locales WHERE id > 0 ORDER BY id ASC");
    foreach ($locales as $loc) {
        $local_id = (int)$loc["id"];

        $cams = DB::select("SELECT id FROM camaras WHERE local_id = ? AND encendida = 1 ORDER BY id ASC", [$local_id]);
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
                        $pesos[$el] = filesize($dir_videos . $el);
                    }
                }
                sleep(6);  // espera a que termine la subida/grabación
                $dir = opendir($dir_videos);
                while (($el = readdir($dir)) !== false) {
                    if ($el !== "." && $el !== ".." && isset($pesos[$el]) && $pesos[$el] === filesize($dir_videos . $el)) {
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
