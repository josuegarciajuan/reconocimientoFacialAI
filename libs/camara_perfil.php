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
        return null;
    }
    $data = json_decode($raw, true);
    if (!is_array($data) || !isset($data['profile']) || !is_array($data['profile'])) {
        return null;
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
