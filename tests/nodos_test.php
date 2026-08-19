<?php

/*
 * Test de la lógica pura de ordenación/agrupación de nodos (libs/nodos.php).
 * No toca BD: ejercita ordenar_cadenas_nodos() con filas sintéticas.
 * Ejecutar: php tests/nodos_test.php   (exit 0 = OK)
 */

require_once __DIR__ . "/../libs/nodos.php";

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

// Helper de fila de nodo tal como la devuelve nodos_caminos_entre().
$F = fn(int $camara_id1, int $camino, int $x, int $y) => [
    "camara_id1" => $camara_id1, "camino" => $camino, "x" => $x, "y" => $y,
];

// --- 1. Sentido directo (camara_id1 == cam_a) → orden preservado ---
$r = ordenar_cadenas_nodos([$F(1, 0, 10, 10), $F(1, 0, 20, 20), $F(1, 0, 30, 30)], 1);
ok(count($r) === 1 && $r[0]["camino"] === 0, "1. Directo: 1 cadena camino 0");
ok($r[0]["nodos"] === [[10, 10], [20, 20], [30, 30]], "1. Directo: orden 10→20→30 preservado");

// --- 2. Sentido inverso (camara_id1 != cam_a) → cadena invertida ---
$r = ordenar_cadenas_nodos([$F(2, 0, 10, 10), $F(2, 0, 20, 20), $F(2, 0, 30, 30)], 1);
ok($r[0]["nodos"] === [[30, 30], [20, 20], [10, 10]], "2. Inverso: orden 30→20→10 (invertido)");

// --- 3. Sin filas → array vacío ---
$r = ordenar_cadenas_nodos([], 1);
ok($r === [], "3. Vacío: sin cadenas");

// --- 4. Múltiples caminos: agrupados y orientados por separado ---
$r = ordenar_cadenas_nodos([
    $F(1, 0, 10, 10), $F(1, 0, 20, 20),
    $F(1, 1, 50, 50), $F(1, 1, 60, 60),
], 1);
ok(count($r) === 2, "4. Multi: 2 cadenas");
ok($r[0]["camino"] === 0 && $r[0]["nodos"] === [[10, 10], [20, 20]], "4. Camino 0: 10→20");
ok($r[1]["camino"] === 1 && $r[1]["nodos"] === [[50, 50], [60, 60]], "4. Camino 1: 50→60");

// --- 5. Un camino en sentido inverso y otro directo (mixto) ---
$r = ordenar_cadenas_nodos([
    $F(2, 0, 10, 10), $F(2, 0, 20, 20),          // guardado 2→1, recorrido 1→2: invertir
    $F(1, 1, 30, 30), $F(1, 1, 40, 40),          // guardado 1→2, recorrido 1→2: directo
], 1);
ok($r[0]["camino"] === 0 && $r[0]["nodos"] === [[20, 20], [10, 10]], "5. Camino 0 invertido (20→10)");
ok($r[1]["camino"] === 1 && $r[1]["nodos"] === [[30, 30], [40, 40]], "5. Camino 1 directo (30→40)");

echo "\n$total tests, $fallos fallos\n";
exit($fallos ? 1 : 0);
