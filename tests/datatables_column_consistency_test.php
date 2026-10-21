<?php
declare(strict_types=1);

/**
 * Consistencia de columnas en los listados server-side de DataTables.
 *
 * Cada tabla con `data-datatable-source="X"` declara sus columnas con <th>.
 * `admin/datatables.php` debe devolver exactamente una celda por columna en
 * cada fila; si devuelve menos, DataTables lanza el warning tn/4
 * ("Requested unknown parameter ... for row ..., column ...").
 *
 * El test no necesita BD: compara el HTML de los listados con la forma de los
 * arrays `$data[] = [...]` del endpoint.
 */

$root = dirname(__DIR__);
$endpoint = file_get_contents($root . '/admin/datatables.php');
if ($endpoint === false) {
    throw new RuntimeException('No se pudo leer admin/datatables.php');
}

/** Página que declara cada tabla server-side. */
$pages = [
    'visitantes'        => 'admin/pages/visitantes/list.php',
    'accesos'           => 'admin/pages/accesos/list.php',
    'fichajes'          => 'admin/pages/fichajes/list.php',
    'lineas'            => 'admin/pages/lineas/list.php',
    'locales'           => 'admin/pages/locales/list.php',
    'alarmas'           => 'admin/pages/alarmas/list.php',
    'alarmas_telefonos' => 'admin/pages/alarmas/config.php',
    'config_locales'    => 'admin/pages/config/tabs/tab_locales.php',
    'rutas'             => 'admin/pages/rutas/list.php',
];

/**
 * Marcador único de la consulta cuyo `$data[] = [...]` construye las celdas.
 * Se busca el siguiente `$data[] = [` después del marcador.
 */
$markers = [
    'visitantes'        => 'GROUP BY e.persona_id,p.cod_interno,p.nombre,p.trabajador ORDER BY',
    'accesos'           => 'JOIN camaras c ON c.id=e.camara_id',
    'fichajes'          => 'FROM fichajes f JOIN personas p',
    'lineas'            => 'ORDER BY cl.created',
    'locales'           => 'FROM locales l WHERE',
    'alarmas'           => 'FROM alarmas a LEFT JOIN camaras',
    'alarmas_telefonos' => 'FROM alarmas_telefonos WHERE',
    'config_locales'    => 'FROM locales l ORDER BY',
    'rutas'             => 'ORDER BY e.fecha_ini ASC',
];

function th_count(string $html, string $source): int
{
    $marker = 'data-datatable-source="' . $source . '"';
    $at = strpos($html, $marker);
    if ($at === false) {
        throw new RuntimeException("No se encontró $marker en el listado");
    }
    $tableStart = strrpos(substr($html, 0, $at), '<table');
    $tableEnd = strpos($html, '</table>', $at);
    if ($tableStart === false || $tableEnd === false) {
        throw new RuntimeException("No se pudo delimitar la tabla $source");
    }
    $block = substr($html, $tableStart, $tableEnd - $tableStart);
    preg_match_all('/<th[\s>]/i', $block, $matches);
    return count($matches[0]);
}

/**
 * Cuenta los elementos de primer nivel de la expresión `$data[] = [ ... ]`
 * que empieza después de $marker, ignorando comas dentro de strings,
 * paréntesis, corchetes y llaves anidados.
 */
function cell_count(string $endpoint, string $marker): int
{
    $markerAt = strpos($endpoint, $marker);
    if ($markerAt === false) {
        throw new RuntimeException("No se encontró el marcador del endpoint: $marker");
    }
    if (!preg_match('/\$data\[\]\s*=\s*\[/', $endpoint, $match, PREG_OFFSET_CAPTURE, $markerAt)) {
        throw new RuntimeException("No se encontró \$data[] = [ tras el marcador: $marker");
    }
    $start = $match[0][1] + strlen($match[0][0]);
    $length = strlen($endpoint);
    $depth = 0;
    $commas = 0;
    $hasContent = false;
    $inString = null;
    $escaped = false;
    $closed = false;

    for ($i = $start; $i < $length; $i++) {
        $char = $endpoint[$i];

        if ($inString !== null) {
            if ($escaped) {
                $escaped = false;
            } elseif ($char === '\\') {
                $escaped = true;
            } elseif ($char === $inString) {
                $inString = null;
            }
            continue;
        }

        if ($char === "'" || $char === '"') {
            $inString = $char;
            $hasContent = true;
            continue;
        }
        if ($char === '[' || $char === '(' || $char === '{') {
            $depth++;
            $hasContent = true;
            continue;
        }
        if ($char === ']' || $char === ')' || $char === '}') {
            if ($depth === 0) {
                if ($char === ']') {
                    $closed = true;
                    break;
                }
                continue;
            }
            $depth--;
            continue;
        }
        if ($char === ',' && $depth === 0) {
            $commas++;
            continue;
        }
        if (!ctype_space($char)) {
            $hasContent = true;
        }
    }

    if (!$closed) {
        throw new RuntimeException('No se pudo cerrar el array $data[] del endpoint');
    }
    return $hasContent ? $commas + 1 : 0;
}

// Descubre todas las tablas server-side para que una nueva no quede sin cubrir.
$discovered = [];
$iterator = new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root . '/admin/pages'));
foreach ($iterator as $file) {
    if (!$file->isFile() || $file->getExtension() !== 'php') {
        continue;
    }
    $contents = file_get_contents($file->getPathname());
    if ($contents === false) {
        continue;
    }
    if (preg_match_all('/data-datatable-source="([a-z_]+)"/', $contents, $matches)) {
        foreach ($matches[1] as $source) {
            $discovered[$source] = true;
        }
    }
}
$undocumented = array_diff(array_keys($discovered), array_keys($pages));
if ($undocumented) {
    throw new RuntimeException('Tablas server-side sin cobertura en el test: ' . implode(', ', $undocumented));
}
$stale = array_diff(array_keys($pages), array_keys($discovered));
if ($stale) {
    throw new RuntimeException('El test referencia tablas que ya no existen: ' . implode(', ', $stale));
}

foreach ($pages as $source => $relative) {
    $page = file_get_contents($root . '/' . $relative);
    if ($page === false) {
        throw new RuntimeException("No se pudo leer $relative");
    }
    $columns = th_count($page, $source);
    $cells = cell_count($endpoint, $markers[$source]);
    if ($columns !== $cells) {
        throw new RuntimeException(sprintf(
            "%s: la tabla declara %d columnas pero el endpoint devuelve %d celdas por fila (DataTables tn/4)",
            $source,
            $columns,
            $cells
        ));
    }
    echo "$source: $columns columnas OK\n";
}

echo "datatables_column_consistency_test.php: OK\n";
