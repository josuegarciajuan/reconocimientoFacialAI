<?php

/*
 * Test de la lógica pura de vínculos (libs/vinculos.php).
 * No toca BD: ejercita vinculos_solapa() y vinculos_mas_cercano() con escenarios
 * sintéticos (solape, margen, sin solape, ambiguo).
 * Ejecutar: php tests/vinculos_test.php   (exit 0 = OK)
 */

require_once __DIR__ . "/../libs/vinculos.php";

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

$h = fn(string $hora) => "2026-08-19 " . $hora;
$M = 30;

// --- 1. vinculos_solapa: casos básicos ---
ok(vinculos_solapa($h("10:00:00"), $h("10:10:00"), $h("10:05:00"), $h("10:15:00"), $M),
    "1. Solape real de intervalos");
ok(vinculos_solapa($h("10:00:00"), $h("10:10:00"), $h("10:10:00"), $h("10:20:00"), $M),
    "1. Bordes tocándose (10:10 == 10:10)");
ok(!vinculos_solapa($h("10:00:00"), $h("10:10:00"), $h("10:11:00"), $h("10:20:00"), 5),
    "1. Sin solape y fuera de margen (5s)");
ok(!vinculos_solapa($h("10:00:00"), $h("10:10:00"), $h("10:11:00"), $h("10:20:00"), $M),
    "1. Sin solape, 60s de separación > margen 30s");
ok(vinculos_solapa($h("10:00:00"), $h("10:10:00"), $h("10:10:20"), $h("10:20:00"), $M),
    "1. Sin solape pero dentro de margen (20s de separación)");
ok(vinculos_solapa($h("10:00:00"), $h("10:10:00"), $h("09:55:00"), $h("10:05:00"), $M),
    "1. Estancia que empieza antes y solapa");
ok(vinculos_solapa($h("10:00:00"), $h("10:10:00"), $h("10:03:00"), $h("10:07:00"), $M),
    "1. Intervalo contenido dentro de otro");

// --- 2. vinculos_solapa: fechas raras ---
ok(!vinculos_solapa("", "", $h("10:00:00"), $h("10:10:00"), $M),
    "2. Fecha vacía -> false");
ok(!vinculos_solapa("no-es-fecha", $h("10:10:00"), $h("10:00:00"), $h("10:10:00"), $M),
    "2. Fecha no parseable -> false");
ok(vinculos_solapa($h("10:00:00"), "", $h("10:00:00"), $h("10:10:00"), $M),
    "2. Fin vacío se trata como el inicio (mismo punto)");

// --- 3. vinculos_mas_cercano: atribución de persona al cruce ---
$ints = [
    ["ini" => strtotime($h("10:00:00")), "fin" => strtotime($h("10:05:00"))],   // 0
    ["ini" => strtotime($h("10:10:00")), "fin" => strtotime($h("10:20:00"))],   // 1
    ["ini" => strtotime($h("11:00:00")), "fin" => strtotime($h("11:30:00"))],   // 2
];
$t_dentro = strtotime($h("10:12:00"));
ok(vinculos_mas_cercano($t_dentro, $ints, $M) === 1, "3. Punto dentro del intervalo 1");
$t_borde = strtotime($h("10:10:02"));
ok(vinculos_mas_cercano($t_borde, $ints, $M) === 1, "3. Punto a 2s del inicio del intervalo 1 (dentro de margen)");
$t_fuera = strtotime($h("10:45:00"));
ok(vinculos_mas_cercano($t_fuera, $ints, $M) === null, "3. Punto sin intervalo a menos de margen -> null");
$t_antes = strtotime($h("09:59:55"));
ok(vinculos_mas_cercano($t_antes, $ints, $M) === 0, "3. Punto a 5s antes del primer intervalo (margen 30s)");
$t_entre = strtotime($h("10:07:10"));
$ints_cerca = [
    ["ini" => strtotime($h("10:00:00")), "fin" => strtotime($h("10:05:00"))],
    ["ini" => strtotime($h("10:07:30")), "fin" => strtotime($h("10:20:00"))],
];
ok(vinculos_mas_cercano($t_entre, $ints_cerca, $M) === 1, "3. Punto entre dos intervalos -> el más cercano (20s vs 130s)");
$t_ambiguo = strtotime($h("10:07:00"));
$ints_amb = [
    ["ini" => strtotime($h("10:00:00")), "fin" => strtotime($h("10:07:00"))],
    ["ini" => strtotime($h("10:07:00")), "fin" => strtotime($h("10:14:00"))],
];
ok(vinculos_mas_cercano($t_ambiguo, $ints_amb, $M) === 0, "3. Empate exacto -> el primero");

// --- 4. vinculos_mas_cercano: márgenes y vacíos ---
ok(vinculos_mas_cercano(strtotime($h("10:00:00")), [], $M) === null, "4. Sin intervalos -> null");
ok(vinculos_mas_cercano(strtotime($h("10:06:00")), $ints, 5) === null,
    "4. Dentro de la ventana amplia pero fuera de margen estricto (5s) -> null");

echo "\n" . $total . " comprobaciones, " . $fallos . " fallos\n";
exit($fallos === 0 ? 0 : 1);
