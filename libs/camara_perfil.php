<?php

/*
 * Perfil operativo de las cámaras del bridge `camaraip`.
 *
 * El bridge de camaraESP es la fuente de verdad. Ojos solo lee el perfil para
 * las URLs con `camera=<id>`; las RTSP de laboral no se tocan.
 *
 * El endpoint es local (127.0.0.1:8111) y no contiene claves. Si el bridge no
 * responde, las funciones devuelven null y el llamador conserva su fallback.
 */

/**
 * Extrae el ID camaraip de una URL, o null si no es una cámara del bridge.
 * Acepta http://127.0.0.1:8111/camaraip/... y https://josue.ink/camaraip/...
 */
function rf_camaraip_id(?string $url): ?string
{
    if ($url === null || trim($url) === '') {
        return null;
    }
    $parts = parse_url($url);
    if (!is_array($parts)) {
        return null;
    }
    $host = strtolower((string)($parts['host'] ?? ''));
    $port = (int)($parts['port'] ?? 0);
    $path = (string)($parts['path'] ?? '');
    $esBridgeLocal = in_array($host, ['127.0.0.1', 'localhost', '::1'], true)
        && ($port === 0 || $port === 8111);
    $esRutaCamaraip = strpos($path, '/camaraip/') !== false;
    if (!$esBridgeLocal && !$esRutaCamaraip) {
        return null;
    }
    parse_str((string)($parts['query'] ?? ''), $query);
    $id = isset($query['camera']) ? trim((string)$query['camera']) : '';
    return $id !== '' ? $id : null;
}


/**
 * Copia versionada de los perfiles de las cámaras camaraip para /ojos.
 * Se genera con tools/export_camaraip_profiles.php.
 */
function rf_camaraip_saved_profiles(): array
{
    static $cache = null;
    if ($cache !== null) {
        return $cache;
    }
    $file = __DIR__ . "/../config/camaraip_ojos_profiles.json";
    $raw = @file_get_contents($file);
    $data = json_decode((string)$raw, true);
    $cache = is_array($data) && is_array($data["cameras"] ?? null)
        ? $data
        : ["version" => 1, "instance" => "ojos", "cameras" => []];
    return $cache;
}

/** Respuesta sintética desde la copia guardada, o null si no existe. */
function rf_camaraip_saved_response(string $cameraId): ?array
{
    $doc = rf_camaraip_saved_profiles();
    $cam = $doc["cameras"][$cameraId] ?? null;
    if (!is_array($cam) || !is_array($cam["profile"] ?? null)) {
        return null;
    }
    $ojos = is_array($cam["ojos"] ?? null) ? $cam["ojos"] : [];
    return [
        "ok" => true,
        "camera" => $cameraId,
        "version" => (int)($doc["version"] ?? 1),
        "profile" => $cam["profile"],
        "measured" => [
            "fps" => (float)($ojos["fps_efectivo"] ?? 0),
            "frame_bytes" => 0,
            "last_frame_age_ms" => null,
        ],
        "config_source" => "saved",
    ];
}

/**
 * Perfil completo devuelto por GET /camaraip/profile.
 * Cachea 10 s por ID para no golpear el bridge en cada render.
 */
function rf_camara_perfil(?string $url, float $timeout = 0.8): ?array
{
    static $cache = [];
    $id = rf_camaraip_id($url);
    if ($id === null) {
        return null;
    }
    $now = time();
    if (isset($cache[$id]) && ($now - $cache[$id]['ts']) < 10) {
        return $cache[$id]['data'];
    }

    $base = getenv('RF_CAMARA_PROFILE_URL');
    if ($base === false || $base === '') {
        $base = 'http://127.0.0.1:8111/camaraip/profile';
    }
    $sep = strpos($base, '?') === false ? '?' : '&';
    $ctx = stream_context_create([
        'http' => [
            'timeout' => $timeout,
            'ignore_errors' => true,
            'header' => "Accept: application/json\r\n",
        ],
    ]);
    $raw = @file_get_contents($base . $sep . 'camera=' . urlencode($id), false, $ctx);
    if ($raw === false || $raw === '') {
        $saved = rf_camaraip_saved_response($id);
        if ($saved !== null) {
            $cache[$id] = ['ts' => $now, 'data' => $saved];
        }
        return $saved;
    }
    $data = json_decode($raw, true);
    if (!is_array($data) || !isset($data['profile']) || !is_array($data['profile'])) {
        $saved = rf_camaraip_saved_response($id);
        if ($saved !== null) {
            $cache[$id] = ['ts' => $now, 'data' => $saved];
        }
        return $saved;
    }
    $cache[$id] = ['ts' => $now, 'data' => $data];
    return $data;
}

/** fps real del perfil, o $fallback si no es camaraip/no responde. */
function rf_camara_perfil_fps(?string $url, int $fallback): int
{
    $data = rf_camara_perfil($url);
    if ($data === null) {
        return $fallback;
    }
    $fps = $data['profile']['stream']['fps'] ?? null;
    $perfil_fps = is_numeric($fps) ? max(1, (int)round((float)$fps)) : $fallback;

    // Si el bridge ya está midiendo, usar el fps REAL: evita que un agente
    // antiguo (2 fps) se grabe con el fps objetivo (5) y acelere los clips.
    $measured = $data['measured']['fps'] ?? null;
    if (is_numeric($measured) && (float)$measured >= 1.0) {
        $medido = (int)round((float)$measured);
        if ($medido <= max($perfil_fps * 2, 10)) {
            return $medido;
        }
    }
    return $perfil_fps;
}

/** Resumen listo para pintar en la UI. */
function rf_camara_perfil_resumen(?string $url): ?array
{
    $data = rf_camara_perfil($url);
    if ($data === null) {
        return null;
    }
    $p = $data['profile'];
    $stream = is_array($p['stream'] ?? null) ? $p['stream'] : [];
    return [
        'id' => (string)($data['camera'] ?? ''),
        'model' => (string)($p['model'] ?? ''),
        'sensor' => (string)($p['sensor'] ?? ''),
        'kind' => (string)($p['kind'] ?? ''),
        'width' => (int)($stream['width'] ?? 0),
        'height' => (int)($stream['height'] ?? 0),
        'fps' => (int)round((float)($stream['fps'] ?? 0)),
        'jpeg_quality' => (int)($stream['jpeg_quality'] ?? 0),
        'rotation' => (int)($stream['rotation'] ?? 0),
        'measured_fps' => isset($data['measured']['fps']) ? (float)$data['measured']['fps'] : null,
        'config_source' => (string)($data['config_source'] ?? ''),
    ];
}

/** URL local del último JPEG, o null si no es camaraip. */
function rf_camara_perfil_latest_url(?string $url): ?string
{
    $id = rf_camaraip_id($url);
    if ($id === null) {
        return null;
    }
    return 'http://127.0.0.1:8111/camaraip/latest.jpg?camera=' . urlencode($id);
}

/** URL local del stream MJPEG, o null si no es camaraip. */
function rf_camara_perfil_stream_url(?string $url): ?string
{
    $id = rf_camaraip_id($url);
    if ($id === null) {
        return null;
    }
    return 'http://127.0.0.1:8111/camaraip/stream?camera=' . urlencode($id);
}
