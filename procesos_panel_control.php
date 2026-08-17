<?php

/* 
 * Panel de control — p1 (REFACTOR Fase 5).
 * Mantiene en marcha `motor/pose.py` (validador de pose de cara para el registro webcam),
 * sustituyendo al legacy `devuelve_posicion_cara.py`.
 */

$debug = 0;
if (isset($argv[1]) and $argv[1] !== "") {
    $debug = $argv[1];
}

require_once("config/rutas.php");
require_once("libs/Jos_thread.class.php");

$cmd = RUTA_PYTHON . " motor/pose.py '" . RUTA_PROYECTO . "'" . ($debug ? " --debug" : "");

$threads = [];
$proc = "procesos_panel_control";

$tiempo_inicial = microtime(true);
while (true) {

    if (!isset($threads[$proc]) or $threads[$proc] == NULL) {
        echo "No existia el proceso..\n";
        $threads[$proc] = new Jos_Thread($proc, $cmd, true);
        $threads[$proc]->start();
        $tiempo_inicial = microtime(true);
    }

    if ((microtime(true) - $tiempo_inicial) > CONFIG_VALIDACION_PROCESOENMARCHA) {
        echo "Tiempo de comprobar..\n";
        if (!$threads[$proc]->isrunning()) {
            echo "Estaba apagado, reiniciando!\n";
            $threads[$proc] = new Jos_Thread($proc, $cmd, true);
            $threads[$proc]->start();
        }
        $tiempo_inicial = microtime(true);
    }

    sleep(1);
}
