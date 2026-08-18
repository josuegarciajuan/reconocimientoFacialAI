<?php

/*
 * Test de la lógica pura de conciliación de fichajes (libs/conciliador.php).
 * No toca BD: ejercita conciliar_eventos() con escenarios sintéticos.
 * Ejecutar: php tests/fichajes_conciliador_test.php   (exit 0 = OK)
 */

require_once __DIR__ . "/../libs/conciliador.php";

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

$horario_partida = [
    "jornada_partida" => true,
    "hora_entrada1"   => "09:00:00",
    "hora_salida1"    => "14:00:00",
    "hora_entrada2"   => "16:00:00",
    "hora_salida2"    => "19:00:00",
    "margen_min"      => 30,
];
$horario_continuo = array_merge($horario_partida, ["jornada_partida" => false]);

// Helpers de eventos
$E = fn(string $h) => ["hora" => $h, "tipo" => "ENTRY", "estancia_id" => 1, "camara_id" => 1];
$X = fn(string $h) => ["hora" => $h, "tipo" => "EXIT", "estancia_id" => 2, "camara_id" => 2];
$h = fn(string $hora) => "2026-08-19 " . $hora;

// --- 1. Sin horario configurado (legacy) ---
$r = conciliar_eventos([
    $E($h("09:05:00")), $X($h("11:00:00")), $E($h("11:10:00")), $X($h("18:45:00")),
]);
ok(count($r) === 1, "1. Sin horario: 1 bloque");
ok($r[0]["entrada"]["hora"] === $h("09:05:00"), "1. Sin horario: entrada = 1er ENTRY");
ok($r[0]["salida"]["hora"] === $h("18:45:00"), "1. Sin horario: salida = último EXIT");

// --- 2. Jornada partida normal (con fumar a media mañana que no rompe) ---
$r = conciliar_eventos([
    $E($h("08:55:00")), $X($h("11:05:00")), $E($h("11:15:00")), $X($h("13:45:00")),
    $E($h("16:10:00")), $X($h("19:00:00")),
], $horario_partida);
ok(count($r) === 2, "2. Partida normal: 2 bloques");
ok($r[0]["bloque"] === 1 && $r[0]["entrada"]["hora"] === $h("08:55:00") && $r[0]["salida"]["hora"] === $h("13:45:00"),
    "2. Bloque 1: entrada 08:55, salida 13:45 (fumar 11:05 ignorado)");
ok($r[1]["bloque"] === 2 && $r[1]["entrada"]["hora"] === $h("16:10:00") && $r[1]["salida"]["hora"] === $h("19:00:00"),
    "2. Bloque 2: entrada 16:10, salida 19:00");

// --- 3. Media jornada con jornada partida configurada => 1 bloque ---
$r = conciliar_eventos([$E($h("08:55:00")), $X($h("13:45:00"))], $horario_partida);
ok(count($r) === 1 && $r[0]["entrada"]["hora"] === $h("08:55:00") && $r[0]["salida"]["hora"] === $h("13:45:00"),
    "3. Media jornada: 1 bloque entrada 08:55 salida 13:45");

// --- 4. Jornada continua configurada, persona con otro horario => 1 bloque primer/último ---
$r = conciliar_eventos([
    $E($h("10:15:00")), $X($h("11:00:00")), $E($h("11:20:00")), $X($h("18:30:00")),
], $horario_continuo);
ok(count($r) === 1 && $r[0]["entrada"]["hora"] === $h("10:15:00") && $r[0]["salida"]["hora"] === $h("18:30:00"),
    "4. Otro horario: 1 bloque entrada 10:15 salida 18:30");

// --- 5. Sin salida todavía (provisional) ---
$r = conciliar_eventos([$E($h("08:55:00"))], $horario_continuo);
ok(count($r) === 1 && $r[0]["entrada"]["hora"] === $h("08:55:00") && $r[0]["salida"] === null,
    "5. Sin salida aún: entrada con salida null");

// --- 6. Múltiples pasos intermedios: la salida es SIEMPRE el último EXIT ---
$r = conciliar_eventos([
    $E($h("08:55:00")), $X($h("10:00:00")), $E($h("10:05:00")),
    $X($h("12:30:00")), $E($h("12:40:00")), $X($h("14:00:00")),
], $horario_continuo);
ok(count($r) === 1 && $r[0]["salida"]["hora"] === $h("14:00:00"),
    "6. Pasos intermedios: salida = último EXIT (14:00)");

// --- 7. Partida: volver de comer muy tarde (17:30) sigue formando bloque 2 ---
$r = conciliar_eventos([
    $E($h("08:55:00")), $X($h("13:45:00")), $E($h("17:30:00")), $X($h("19:30:00")),
], $horario_partida);
ok(count($r) === 2
    && $r[0]["salida"]["hora"] === $h("13:45:00")
    && $r[1]["entrada"]["hora"] === $h("17:30:00")
    && $r[1]["salida"]["hora"] === $h("19:30:00"),
    "7. Vuelta tarde de comer: b1 salida 13:45, b2 entrada 17:30 salida 19:30");

// --- 8. Jornada continua dentro de horario partida (nunca sale a comer) => 1 bloque ---
$r = conciliar_eventos([$E($h("08:55:00")), $X($h("19:00:00"))], $horario_partida);
ok(count($r) === 1 && $r[0]["entrada"]["hora"] === $h("08:55:00") && $r[0]["salida"]["hora"] === $h("19:00:00"),
    "8. Continua con partida configurada: 1 bloque 08:55-19:00");

// --- 9. Bloque 1 sin EXIT (sale a comer por otra puerta) => salida1 null, bloque 2 completo ---
$r = conciliar_eventos([
    $E($h("08:55:00")), $E($h("16:10:00")), $X($h("19:00:00")),
], $horario_partida);
ok(count($r) === 2
    && $r[0]["entrada"]["hora"] === $h("08:55:00") && $r[0]["salida"] === null
    && $r[1]["entrada"]["hora"] === $h("16:10:00") && $r[1]["salida"]["hora"] === $h("19:00:00"),
    "9. Sin EXIT de comida: b1 salida null, b2 completo");

echo "\n$total tests, $fallos fallos\n";
exit($fallos ? 1 : 0);
