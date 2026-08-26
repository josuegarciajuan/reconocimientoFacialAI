<?php
declare(strict_types=1);

$bundle = file_get_contents(__DIR__ . '/../admin/files/app.js');
$serverSide = file_get_contents(__DIR__ . '/../includes/javascript.php');
$visitantes = file_get_contents(__DIR__ . '/../admin/pages/visitantes/list.php');

if ($bundle === false || $serverSide === false || $visitantes === false) {
    throw new RuntimeException('No se pudieron leer los inicializadores de DataTables');
}

if (strpos($bundle, "$('.datatable').not('[data-datatable-source]')") === false) {
    throw new RuntimeException('El bundle debe excluir las tablas server-side');
}

if (strpos($bundle, 'window.rfInitServerSideDataTables') === false) {
    throw new RuntimeException('El bundle que carga DataTables debe exponer el inicializador server-side');
}

foreach (['serverSide: true', 'processing: true', 'pageLength: 100', "url: './datatables.php'"] as $option) {
    if (strpos($bundle, $option) === false) {
        throw new RuntimeException('Falta la configuración DataTables requerida: ' . $option);
    }
}

if (strpos($bundle, 'isDataTable') === false) {
    throw new RuntimeException('El inicializador server-side debe ser idempotente');
}

if (strpos($visitantes, 'data-datatable-source="visitantes"') === false) {
    throw new RuntimeException('La tabla de visitantes debe declarar su fuente sin usar data-ajax');
}

if (strpos($visitantes, 'data-ajax=') !== false) {
    throw new RuntimeException('data-ajax es una opción reservada por DataTables y sobrescribe la URL configurada');
}

if (strpos($visitantes, 'data-empty-filters="desde,hasta"') === false) {
    throw new RuntimeException('Visitantes debe distinguir fechas vacías de valores visuales del datepicker');
}

if (strpos($bundle, 'emptyFilters') === false || strpos($bundle, 'URLSearchParams') === false) {
    throw new RuntimeException('El inicializador debe omitir filtros opcionales ausentes de la URL');
}

echo "datatables_initialization_test.php: OK\n";
