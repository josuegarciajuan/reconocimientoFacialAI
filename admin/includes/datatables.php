<?php
declare(strict_types=1);

/** Normaliza los parámetros enviados por DataTables sin confiar en el cliente. */
function datatables_request(array $input): array
{
    $draw = max(0, (int)($input['draw'] ?? 0));
    $start = max(0, (int)($input['start'] ?? 0));
    $length = (int)($input['length'] ?? 100);
    if ($length < 1) { $length = 100; }
    $length = min(100, $length);
    $order = $input['order'][0] ?? [];
    $direction = strtolower((string)($order['dir'] ?? 'asc')) === 'desc' ? 'DESC' : 'ASC';
    return ['draw' => $draw, 'start' => $start, 'length' => $length,
        'column' => (string)($order['column'] ?? '0'), 'direction' => $direction];
}

function datatables_order(string $column, array $whitelist): string
{
    return $whitelist[$column] ?? reset($whitelist);
}

function datatables_response(int $draw, int $total, int $filtered, array $data): array
{
    return ['draw' => max(0, $draw), 'recordsTotal' => max(0, $total),
        'recordsFiltered' => max(0, $filtered), 'data' => array_values($data)];
}

function datatables_html(string $value): string
{
    return htmlspecialchars($value, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}
