<?php

/*
 * libs/trayectoria.php — Lógica pura del reproductor de Caminos.
 *
 * Una ruta (construida por libs/rutas.php) es una cadena de puntos:
 *   {t (epoch), fecha, camara_id, desc, x, y, estancia_id, video_id, poster, ...}
 * Este lib calcula la duración real, el factor de velocidad para comprimir la
 * jornada en un objetivo de tiempo, la posición interpolada del monigote a lo
 * largo de la polilínea y los pasos con vídeo reproducible.
 */

/** Duración real de la ruta en segundos (>= 1). */
function trayectoria_duracion(array $ruta): int
{
    $pts = $ruta["puntos"] ?? [];
    $n = count($pts);
    if ($n === 0) {
        return 1;
    }
    $t0 = (int)($pts[0]["t"] ?? 0);
    $t1 = (int)($pts[$n - 1]["t"] ?? $t0);
    return max(1, $t1 - $t0);
}

/**
 * Factor de velocidad para ver la jornada real en `$dur_objetivo` segundos.
 * Ejemplos: 8 h (28 800 s) en 120 s -> x240; en 60 s -> x480.
 */
function trayectoria_velocidad(int $dur_real, int $dur_objetivo): float
{
    $obj = max(1, (int)$dur_objetivo);
    $v = $dur_real / $obj;
    return max(1.0, (float)round($v));
}

/**
 * Posición del monigote en el instante `$t` (epoch, real).
 * Devuelve ['i' => índice del punto de inicio, 'factor' => 0..1 dentro del
 * tramo]. Antes del primer punto -> {0,0}; después del último -> {n-2,1}.
 */
function trayectoria_posicion(array $ruta, int $t): array
{
    $pts = $ruta["puntos"] ?? [];
    $n = count($pts);
    if ($n === 0) {
        return ["i" => -1, "factor" => 0.0];
    }
    if ($n === 1) {
        return ["i" => 0, "factor" => 0.0];
    }
    $t0 = (int)$pts[0]["t"];
    $tn = (int)$pts[$n - 1]["t"];
    if ($t <= $t0) {
        return ["i" => 0, "factor" => 0.0];
    }
    if ($t >= $tn) {
        return ["i" => $n - 2, "factor" => 1.0];
    }
    for ($i = 0; $i < $n - 1; $i++) {
        $ta = (int)$pts[$i]["t"];
        $tb = (int)$pts[$i + 1]["t"];
        if ($t >= $ta && $t <= $tb) {
            $dt = $tb - $ta;
            $factor = ($dt > 0) ? ($t - $ta) / $dt : 0.0;
            return ["i" => $i, "factor" => (float)$factor];
        }
    }
    return ["i" => $n - 2, "factor" => 1.0];
}

/** Pasos de la ruta que tienen vídeo de movimiento reproducible (botón Ver). */
function trayectoria_pasos_con_video(array $ruta): array
{
    $pasos = [];
    foreach (($ruta["puntos"] ?? []) as $p) {
        if (!empty($p["video_id"])) {
            $pasos[] = [
                "t"          => (int)$p["t"],
                "fecha"      => (string)($p["fecha"] ?? ""),
                "camara_id"  => (int)$p["camara_id"],
                "desc"       => (string)($p["desc"] ?? ""),
                "estancia_id"=> (int)($p["estancia_id"] ?? 0),
                "video_id"   => (int)$p["video_id"],
                "poster"     => (string)($p["poster"] ?? ""),
            ];
        }
    }
    return $pasos;
}

/** Presets de velocidad del player (de 1x a 600x). */
function trayectoria_velocidades(): array
{
    return [1, 5, 10, 20, 60, 120, 300, 600];
}
