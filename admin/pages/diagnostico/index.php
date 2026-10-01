<?php

declare(strict_types=1);

/*
 * Diagnóstico de encuadre de caras — controlador.
 *
 * Página READ-ONLY: solo LEE el informe cacheado que genera el CLI
 * motor/diagnostico_caras.py. La única acción de escritura es lanzar ese CLI
 * en segundo plano cuando el operador pulsa "Actualizar" (?actualizar=1), y el
 * propio CLI escribe el JSON + el log (append). El panel nunca toca la BD.
 *
 * El CLI es PESADO (carga InsightFace y decodifica vídeos), por eso se lanza
 * SIEMPRE en background y la vista únicamente lee el JSON cacheado.
 */

$diagBase     = rtrim(RUTA_PROYECTO, "/");
$diagJsonPath = $diagBase . "/motor/diagnostics/caras.json";
$diagScript   = $diagBase . "/motor/diagnostico_caras.py";
$diagLogPath  = $diagBase . "/motor/logs/diagnostico_caras.log";
$diagLocalId  = (int)($_SESSION["local_id"] ?? 0);

/** mtime seguro (0 si no existe). */
$diag_mtime = static function (string $path): int {
    $m = @filemtime($path);
    return $m === false ? 0 : (int)$m;
};

$diagError    = "";
$diagLanzado  = false;

/* ------------------------------------------------------------------ *
 * Acción: lanzar el informe en segundo plano (un clic = un lanzamiento).
 * ------------------------------------------------------------------ */
if ((string)($_GET["actualizar"] ?? "") === "1") {
    if (!isset($_SESSION["user"])) {
        $diagError = "Sesión no válida: vuelve a iniciar sesión.";
    } elseif ($diagLocalId <= 0) {
        $diagError = "No se ha podido identificar el local de la sesión.";
    } else {
        // No relanzar si ya hay un informe en curso (evita duplicar el proceso pesado).
        $diagEnCurso = isset($_SESSION["diag_launch_ts"])
            && (time() - (int)$_SESSION["diag_launch_ts"]) < 600
            && $diag_mtime($diagJsonPath) <= (int)($_SESSION["diag_json_mtime_pre"] ?? 0);

        if (!$diagEnCurso) {
            // El CLI crea el directorio del JSON; el log necesita el suyo antes del redirect.
            @mkdir(dirname($diagLogPath), 0777, true);
            @mkdir(dirname($diagJsonPath), 0777, true);

            // Todas las rutas/argumentos escapados. Lanzamiento en background.
            $cmd = escapeshellarg(RUTA_PYTHON)
                 . " " . escapeshellarg($diagScript)
                 . " --ruta " . escapeshellarg($diagBase . "/")
                 . " --local " . escapeshellarg((string)$diagLocalId)
                 . " --json " . escapeshellarg($diagJsonPath)
                 . " >> " . escapeshellarg($diagLogPath) . " 2>&1 &";

            @exec($cmd);

            $_SESSION["diag_launch_ts"]        = time();
            $_SESSION["diag_json_mtime_pre"]   = $diag_mtime($diagJsonPath);
        }
        $diagLanzado = true;
    }
}

/* ------------------------------------------------------------------ *
 * Estado "generando": lanzado y el JSON todavía no se ha reescrito.
 * ------------------------------------------------------------------ */
$diagGenerando = isset($_SESSION["diag_launch_ts"])
    && (time() - (int)$_SESSION["diag_launch_ts"]) < 600
    && $diag_mtime($diagJsonPath) <= (int)($_SESSION["diag_json_mtime_pre"] ?? 0);

if (!$diagGenerando && isset($_SESSION["diag_launch_ts"])) {
    unset($_SESSION["diag_launch_ts"], $_SESSION["diag_json_mtime_pre"]);
}

/* ------------------------------------------------------------------ *
 * Leer el informe cacheado. Nunca fatal: si falta o está corrupto -> null.
 * ------------------------------------------------------------------ */
$diagInforme = null;
if (is_readable($diagJsonPath)) {
    $diagRaw = @file_get_contents($diagJsonPath);
    if ($diagRaw !== false) {
        $diagDecoded = json_decode($diagRaw, true);
        if (is_array($diagDecoded)
            && isset($diagDecoded["filas"])
            && is_array($diagDecoded["filas"])) {
            $diagInforme = $diagDecoded;
        }
    }
}

require __DIR__ . "/list.php";
