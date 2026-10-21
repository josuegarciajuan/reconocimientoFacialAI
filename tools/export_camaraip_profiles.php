<?php

/*
 * Exporta el perfil efectivo de las cámaras camaraip + los parámetros de
 * análisis de Ojos a `config/camaraip_ojos_profiles.json`.
 *
 * Uso (solo instancia ojos):
 *   php tools/export_camaraip_profiles.php
 *
 * El JSON es una copia versionada para que /ojos siga conociendo modelo,
 * resolución, fps, rotación y parámetros de análisis aunque el bridge no
 * responda. La fuente de verdad de los controles de hardware sigue siendo
 * camaraESP; este archivo es el fallback de RF/Ojos.
 */

require_once __DIR__ . "/../config/rutas.php";
require_once __DIR__ . "/../libs/db.php";
require_once __DIR__ . "/../libs/camara_perfil.php";

if (RF_INSTANCE !== "ojos") {
    fwrite(STDERR, "Este export es solo para la instancia ojos (RF_INSTANCE=" . RF_INSTANCE . ").\n");
    exit(2);
}

$profilesUrl = getenv("RF_CAMARA_PROFILES_URL");
if ($profilesUrl === false || $profilesUrl === "") {
    $profilesUrl = "http://127.0.0.1:8111/camaraip/profiles";
}

$ctx = stream_context_create([
    "http" => ["timeout" => 2.0, "ignore_errors" => true, "header" => "Accept: application/json\r\n"],
]);
$raw = @file_get_contents($profilesUrl, false, $ctx);
if ($raw === false || $raw === "") {
    fwrite(STDERR, "No se pudo leer el bridge en {$profilesUrl}\n");
    exit(3);
}
$bridge = json_decode($raw, true);
if (!is_array($bridge) || !is_array($bridge["cameras"] ?? null)) {
    fwrite(STDERR, "Respuesta inválida de {$profilesUrl}\n");
    exit(4);
}

$rows = DB::select(
    "SELECT id, descripcion, url_conexion, encendida,
            segundos_analizar, porcentaje_mov, dontCare, maximo_videos,
            redimesionframe, sensibilidad, threshold, blur, dilate,
            seg_antes, seg_despues, fps
       FROM camaras
      ORDER BY id"
);

$cameras = [];
foreach ($rows as $row) {
    $camId = rf_camaraip_id((string)($row["url_conexion"] ?? ""));
    if ($camId === null) {
        continue;
    }
    $bridgeCam = $bridge["cameras"][$camId] ?? null;
    if (!is_array($bridgeCam) || !is_array($bridgeCam["profile"] ?? null)) {
        continue;
    }
    $profile = $bridgeCam["profile"];
    $stream = is_array($profile["stream"] ?? null) ? $profile["stream"] : [];
    $measured = is_array($bridgeCam["measured"] ?? null) ? $bridgeCam["measured"] : [];
    $measuredFps = (float)($measured["fps"] ?? 0);
    $targetFps = (int)($stream["fps"] ?? $row["fps"]);
    $effectiveFps = $measuredFps >= 1.0 ? (int)round($measuredFps) : $targetFps;

    $cameras[$camId] = [
        "camera_id" => (int)$row["id"],
        "label" => (string)$row["descripcion"],
        "url_conexion" => (string)$row["url_conexion"],
        "active" => ($profile["active"] ?? true) !== false,
        "encendida" => (int)$row["encendida"],
        "profile" => $profile,
        "ojos" => [
            "fps_objetivo" => $targetFps,
            "fps_efectivo" => $effectiveFps,
            "snapshot" => "latest.jpg",
            "live" => "direct",
            "analysis" => [
                "segundos_analizar" => (int)$row["segundos_analizar"],
                "porcentaje_mov" => (int)$row["porcentaje_mov"],
                "dontCare" => (int)$row["dontCare"],
                "maximo_videos" => (int)$row["maximo_videos"],
                "redimesionframe" => (int)$row["redimesionframe"],
                "sensibilidad" => (int)$row["sensibilidad"],
                "threshold" => (int)$row["threshold"],
                "blur" => (int)$row["blur"],
                "dilate" => (int)$row["dilate"],
                "seg_antes" => (float)$row["seg_antes"],
                "seg_despues" => (float)$row["seg_despues"],
            ],
        ],
    ];
}

if (!$cameras) {
    fwrite(STDERR, "No se encontraron cámaras camaraip en la BD.\n");
    exit(5);
}

$payload = [
    "version" => 1,
    "instance" => "ojos",
    "saved_at" => date("c"),
    "source" => "camaraESP /camaraip/profile + camaras (OJOS)",
    "cameras" => $cameras,
];

$dest = rtrim(RUTA_PROYECTO, "/") . "/config/camaraip_ojos_profiles.json";
$tmp = $dest . ".tmp";
$json = json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
if ($json === false || file_put_contents($tmp, $json . "\n", LOCK_EX) === false) {
    fwrite(STDERR, "No se pudo escribir {$dest}\n");
    exit(6);
}
@chmod($tmp, 0644);
if (!rename($tmp, $dest)) {
    fwrite(STDERR, "No se pudo mover {$tmp} a {$dest}\n");
    exit(7);
}

echo "Guardado {$dest} con " . count($cameras) . " cámaras.\n";
exit(0);
