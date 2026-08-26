<?php
declare(strict_types=1);

require_once __DIR__ . '/../admin/includes/datatables.php';

function assert_same($expected, $actual, string $message): void
{
    if ($expected !== $actual) {
        throw new RuntimeException($message . "\nExpected: " . var_export($expected, true) . "\nActual: " . var_export($actual, true));
    }
}

$request = datatables_request([
    'draw' => '7', 'start' => '-10', 'length' => '1000',
    'order' => [['column' => '1', 'dir' => 'desc']],
]);
assert_same(7, $request['draw'], 'draw debe convertirse a entero');
assert_same(0, $request['start'], 'start negativo debe limitarse a cero');
assert_same(100, $request['length'], 'length debe limitarse al tamaño máximo');
assert_same('DESC', $request['direction'], 'la dirección debe normalizarse');

assert_same('p.nombre', datatables_order('1', ['0' => 'p.id', '1' => 'p.nombre']), 'la ordenación usa whitelist');
assert_same('p.id', datatables_order('invalido', ['0' => 'p.id']), 'columna desconocida usa la primera opción');

$response = datatables_response(3, 20, 5, [['id' => 1]]);
assert_same(['draw' => 3, 'recordsTotal' => 20, 'recordsFiltered' => 5, 'data' => [['id' => 1]],], $response, 'contrato DataTables inválido');

echo "server_side_datatables_test.php: OK\n";
