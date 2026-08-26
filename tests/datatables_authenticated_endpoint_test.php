<?php
declare(strict_types=1);
require_once __DIR__ . '/../libs/db.php';

/**
 * Ejecuta visitantes por HTTP con la misma cookie de sesión que usa el panel.
 * Requiere la base de datos de integración/local; no modifica datos.
 */
$sessionId = 'dtregression' . bin2hex(random_bytes(8));
session_id($sessionId);
session_start();
$_SESSION['user'] = 'regression';
$_SESSION['local_id'] = 1;
session_write_close();

$port = random_int(20000, 40000);
$root = realpath(__DIR__ . '/..');
$process = proc_open(
    [PHP_BINARY, '-S', '127.0.0.1:' . $port, '-t', $root],
    [1 => ['pipe', 'w'], 2 => ['pipe', 'w']],
    $pipes,
    $root
);
if (!is_resource($process)) {
    throw new RuntimeException('No se pudo iniciar el servidor de integración DataTables');
}

try {
    usleep(500_000);
    $url = 'http://127.0.0.1:' . $port . '/admin/datatables.php?table=visitantes&draw=1&start=0&length=100&order[0][column]=0&order[0][dir]=desc';
    $context = stream_context_create(['http' => ['header' => 'Cookie: PHPSESSID=' . $sessionId]]);
    $body = file_get_contents($url, false, $context);
    $status = $http_response_header[0] ?? '';

    if ($body === false || !str_contains($status, ' 200 ')) {
        throw new RuntimeException('El endpoint autenticado de visitantes no respondió HTTP 200: ' . $status);
    }
    $response = json_decode($body, true, flags: JSON_THROW_ON_ERROR);
    if (!is_array($response['data'] ?? null)) {
        throw new RuntimeException('La respuesta autenticada de visitantes no tiene data array');
    }
    if (($response['recordsTotal'] ?? 0) > 0 && $response['data'] === []) {
        throw new RuntimeException('Visitantes informó registros pero no devolvió filas');
    }

    $compatible = DB::selectOne(
        'SELECT e.persona_id FROM estancias e JOIN camaras c ON c.id = e.camara_id WHERE c.local_id = ? LIMIT 1',
        [1]
    );
    if ($compatible !== null && $response['data'] === []) {
        throw new RuntimeException('Visitantes debe devolver una fila cuando existe una estancia compatible con el local');
    }
} finally {
    proc_terminate($process);
    foreach ($pipes as $pipe) {
        fclose($pipe);
    }
    proc_close($process);
}

echo "datatables_authenticated_endpoint_test.php: OK\n";
