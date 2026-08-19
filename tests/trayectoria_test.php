<?php

/*
 * Test de la lógica pura del reproductor de Caminos (libs/trayectoria.php).
 * No toca BD: duracciones, factores de velocidad e interpolación sintéticos.
 * Ejecutar: php tests/trayectoria_test.php   (exit 0 = OK)
 */

require_once __DIR__ . "/../libs/trayectoria.php";

$fallos = 0;
$total = 0;

function ok(bool $cond, string $msg): void {
    global $fallos, $total;
    $total++;
    if ($cond) {
        echo "PASS  $msg\n";
    } else {
        $fallos++;
        echo "FAIL  $msg\n";
    }
}

function ruta_test(): array {
    // 3 puntos: 09:00, 09:10, 09:25 (600s y 900s de separación).
    $pts = [
        ["t" => strtotime("2026-08-19 09:00:00"), "fecha" => "2026-08-19 09:00:00", "camara_id" => 1, "x" => 10, "y" => 10, "desc" => "A", "estancia_id" => 1, "video_id" => 0, "poster" => ""],
        ["t" => strtotime("2026-08-19 09:10:00"), "fecha" => "2026-08-19 09:10:00", "camara_id" => 2, "x" => 100, "y" => 100, "desc" => "B", "estancia_id" => 2, "video_id" => 7, "poster" => "x.jpg"],
        ["t" => strtotime("2026-08-19 09:25:00"), "fecha" => "2026-08-19 09:25:00", "camara_id" => 3, "x" => 200, "y" => 50, "desc" => "C", "estancia_id" => 3, "video_id" => 0, "poster" => ""],
    ];
    return ["puntos" => $pts];
}

$T0 = strtotime("2026-08-19 09:00:00");

// --- 1. Duración ---
ok(trayectoria_duracion(ruta_test()) === 1500, "1. Duración real 09:00→09:25 = 1500 s");
ok(trayectoria_duracion(["puntos" => []]) === 1, "1. Ruta vacía -> 1 s (evita división por cero)");
$unpunto = ["puntos" => [["t" => $T0]]];
ok(trayectoria_duracion($unpunto) === 1, "1. Ruta de 1 punto -> 1 s");

// --- 2. Velocidad (jornada de 8 h) ---
ok(trayectoria_velocidad(28800, 120) === 240.0, "2. 8 h en 2 min = x240");
ok(trayectoria_velocidad(28800, 60) === 480.0, "2. 8 h en 1 min = x480");
ok(trayectoria_velocidad(1500, 150) === 10.0, "2. 25 min en 150 s = x10");
ok(trayectoria_velocidad(100, 50) === 2.0, "2. Redondeo hacia arriba (100/50 = 2)");
ok(trayectoria_velocidad(100, 1000) === 1.0, "2. Nunca baja de 1x");
ok(trayectoria_velocidad(0, 120) === 1.0, "2. Duración real 0 -> 1x");

// --- 3. Posición interpolada ---
$r = ruta_test();
$p0 = trayectoria_posicion($r, $T0);
ok($p0["i"] === 0 && $p0["factor"] === 0.0, "3. t = inicio -> tramo 0, factor 0");

$p_mitad = trayectoria_posicion($r, $T0 + 300);
ok($p_mitad["i"] === 0 && abs($p_mitad["factor"] - 0.5) < 1e-9, "3. t = 09:05 -> mitad del primer tramo (0.5)");

$p_b = trayectoria_posicion($r, $T0 + 600);
ok($p_b["i"] === 0 && abs($p_b["factor"] - 1.0) < 1e-9, "3. t = 09:10 -> fin del primer tramo (factor 1)");

$p_tercero = trayectoria_posicion($r, $T0 + 900);
ok($p_tercero["i"] === 1 && abs($p_tercero["factor"] - (300 / 900)) < 1e-9, "3. t = 09:15 -> tramo 1, factor 1/3");

$p_fin = trayectoria_posicion($r, $T0 + 10000);
ok($p_fin["i"] === 1 && $p_fin["factor"] === 1.0, "3. t > final -> último tramo, factor 1");

$p_antes = trayectoria_posicion($r, $T0 - 1000);
ok($p_antes["i"] === 0 && $p_antes["factor"] === 0.0, "3. t < inicio -> tramo 0, factor 0");

// --- 4. Pasos con vídeo ---
$pasos = trayectoria_pasos_con_video($r);
ok(count($pasos) === 1, "4. Solo el paso B tiene vídeo (video_id 7)");
ok((int)($pasos[0]["video_id"] ?? 0) === 7 && (int)($pasos[0]["estancia_id"] ?? 0) === 2, "4. Paso con vídeo correcto (video 7, estancia 2)");

// --- 5. Presets ---
$vel = trayectoria_velocidades();
ok(in_array(1, $vel, true) && in_array(600, $vel, true) && $vel === array_values(array_unique($vel)),
    "5. Presets de 1x a 600x sin duplicados");

echo "\n{$total} comprobaciones, {$fallos} fallos\n";
exit($fallos > 0 ? 1 : 0);
