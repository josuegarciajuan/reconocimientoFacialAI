<?php
declare(strict_types=1);

/*
 * Contrato del reintento ante deadlock de libs/db.php.
 *
 * Importante: NO se conecta a la BD. `esReintentable()` y `conReintento()` con
 * $pdo sin inicializar son puros, así que el test corre sin MySQL.
 */
require_once __DIR__ . '/../libs/db.php';

// --- esReintentable ---
$casos = [
    [['40001', 1213, 'Deadlock found when trying to get lock'], true],
    [['HY000', 1213, 'Deadlock'], true],
    [['23000', 1062, 'Duplicate entry'], false],
    [['40001', 0, 'Serialization failure'], true],
    [null, false],
];
foreach ($casos as $i => [$info, $esperado]) {
    if (DB::esReintentable($info) !== $esperado) {
        throw new RuntimeException("esReintentable incorrecto en caso {$i}: " . json_encode($info));
    }
}

// --- conReintento: dos deadlocks y luego exito ---
$llamadas = 0;
$out = DB::conReintento(function () use (&$llamadas) {
    $llamadas++;
    if ($llamadas < 3) {
        $e = new PDOException('Deadlock found when trying to get lock');
        $e->errorInfo = ['40001', 1213, 'Deadlock found when trying to get lock'];
        throw $e;
    }
    return 'ok';
});
if ($out !== 'ok' || $llamadas !== 3) {
    throw new RuntimeException("conReintento no reintentó bien (out={$out}, llamadas={$llamadas})");
}

// --- conReintento: un error NO reintentable se propaga a la primera ---
$llamadas2 = 0;
try {
    DB::conReintento(function () use (&$llamadas2) {
        $llamadas2++;
        $e = new PDOException('Duplicate entry');
        $e->errorInfo = ['23000', 1062, 'Duplicate entry'];
        throw $e;
    });
    throw new RuntimeException('debería haber propagado el error no reintentable');
} catch (PDOException $e) {
    if ($llamadas2 !== 1) {
        throw new RuntimeException("no debía reintentar un error no reintentable (llamadas={$llamadas2})");
    }
}

// --- conReintento: agotar reintentos propaga el deadlock ---
$llamadas3 = 0;
try {
    DB::conReintento(function () use (&$llamadas3) {
        $llamadas3++;
        $e = new PDOException('Deadlock');
        $e->errorInfo = ['40001', 1213, 'Deadlock'];
        throw $e;
    });
    throw new RuntimeException('debería haber propagado tras agotar reintentos');
} catch (PDOException $e) {
    if ($llamadas3 !== DB::DEADLOCK_RETRIES) {
        throw new RuntimeException("reintentos inesperados: {$llamadas3} (esperado " . DB::DEADLOCK_RETRIES . ")");
    }
}

echo "db_retry_test.php: OK\n";
