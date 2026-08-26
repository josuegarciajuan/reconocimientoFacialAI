<?php
declare(strict_types=1);

/** El endpoint debe ser consumible por DataTables incluso sin sesión válida. */
$command = [PHP_BINARY, __DIR__ . '/../admin/datatables.php'];
$process = proc_open($command, [1 => ['pipe', 'w'], 2 => ['pipe', 'w']], $pipes, __DIR__);
if (!is_resource($process)) {
    throw new RuntimeException('No se pudo invocar el endpoint DataTables');
}

$body = stream_get_contents($pipes[1]);
$stderr = stream_get_contents($pipes[2]);
fclose($pipes[1]);
fclose($pipes[2]);
$exitCode = proc_close($process);

if ($exitCode !== 0 || $stderr !== '') {
    throw new RuntimeException("El endpoint produjo errores PHP: $stderr");
}

$response = json_decode((string)$body, true);
if (!is_array($response)) {
    throw new RuntimeException('La respuesta del endpoint no es JSON válido: ' . $body);
}

foreach (['draw', 'recordsTotal', 'recordsFiltered', 'data'] as $field) {
    if (!array_key_exists($field, $response)) {
        throw new RuntimeException("Falta el campo DataTables '$field' en una respuesta controlada");
    }
}

if (!is_array($response['data'])) {
    throw new RuntimeException('El campo data debe ser un array');
}

echo "datatables_endpoint_contract_test.php: OK\n";
