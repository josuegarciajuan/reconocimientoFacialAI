<?php
declare(strict_types=1);

/**
 * El inicializador server-side vive en app.js. Su URL debe cambiar cuando se
 * modifica para que un navegador no conserve el inicializador client-side,
 * que deja vacío un tbody servido exclusivamente por AJAX.
 */
$index = file_get_contents(__DIR__ . '/../admin/index.php');
if ($index === false) {
    throw new RuntimeException('No se pudo leer el layout administrativo');
}

if (!preg_match('#<script src="\./files/app\.js\?v=[^"]+"></script>#', $index)) {
    throw new RuntimeException('app.js debe tener una versión de URL para invalidar el inicializador DataTables en caché');
}

echo "datatables_visitors_asset_version_test.php: OK\n";
