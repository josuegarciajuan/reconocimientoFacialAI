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

            foreach ($subidos as $video) {
                // marker: ya se está procesando
                if (file_exists(RUTA_PROYECTO . "aux/" . $video . ".txt")) {
                    continue;
                }

                // nº de vídeos en procesamiento
                $numero_videos = 0;
                if (is_dir(RUTA_PROYECTO . "aux")) {
                    $dir = opendir(RUTA_PROYECTO . "aux");
                    while (($el = readdir($dir)) !== false) {
                        if ($el !== "." && $el !== ".." && strpos($el, "procesar") === false) {
                            $numero_videos++;
                        }
                    }
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

                $cmd = RUTA_PYTHON . " " . RUTA_PROYECTO . "motor/procesa_video.py " . $local_id . " " . $cam_id . " '" . $video . "' --ruta " . RUTA_PROYECTO . " > /dev/null 2>/dev/null &";
                echo $cmd . "\n";
                exec($cmd);
            }
        }
    }

    sleep(1);
}
