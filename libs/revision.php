<?php

declare(strict_types=1);

/*
 * libs/revision.php — validación PURA de rutas de la bandeja de revisión.
 *
 * Sin BD, sin sesión y sin red: solo funciones para validar componentes y
 * confinar cualquier acceso a `motor/revision/<local>/<cam>/<file>`. Se usa
 * desde `admin/pages/revision/foto.php` (stream de miniaturas) y
 * `admin/pages/revision/acciones.php` (pre-validación antes de invocar Python).
 *
 * Test: php tests/revision_seguridad_test.php
 */

if (!defined('RF_REVISION_IMG_EXTS')) {
    define('RF_REVISION_IMG_EXTS', ['jpg', 'jpeg', 'png']);
}

/** ¿El componente es seguro? No vacío, no `.`/`..`, solo [A-Za-z0-9._:-]
 *  (se admite `:` por la hora en los nombres del motor; `/` y `..` no). */
function rf_revision_componente_valido(string $valor): bool
{
    if ($valor === '' || $valor === '.' || $valor === '..') {
        return false;
    }
    return preg_match('/^[A-Za-z0-9._:-]+$/D', $valor) === 1;
}

/** ¿El nombre tiene extensión de imagen admitida? */
function rf_revision_es_imagen(string $nombre): bool
{
    $ext = strtolower(pathinfo($nombre, PATHINFO_EXTENSION));
    return in_array($ext, RF_REVISION_IMG_EXTS, true);
}

/**
 * Ruta absoluta CANÓNICA del fichero de revisión, o null si no es segura.
 *
 * Exige que el fichero exista (realpath) y que resuelva exactamente dentro de
 * `motor/revision/<local>/<cam>/`, bloqueando traversal (`..`, `/`) y symlinks
 * que escapen de la raíz.
 */
function rf_revision_ruta_segura(string $rutaProyecto, string $local, string $cam, string $file): ?string
{
    if (!rf_revision_componente_valido($local)
        || !rf_revision_componente_valido($cam)
        || !rf_revision_componente_valido($file)) {
        return null;
    }
    if (!rf_revision_es_imagen($file)) {
        return null;
    }

    $raiz = realpath(rtrim($rutaProyecto, '/') . '/motor/revision');
    if ($raiz === false) {
        return null;
    }
    $base = realpath($raiz . '/' . $local . '/' . $cam);
    if ($base === false) {
        return null;
    }
    $destino = realpath($base . '/' . $file);
    if ($destino === false) {
        return null;
    }
    // El fichero debe colgar DIRECTAMENTE de <cam> (sin subdirectorios).
    if (dirname($destino) !== $base) {
        return null;
    }
    // Y la resolución final debe seguir dentro de motor/revision.
    $prefijo = rtrim($raiz, DIRECTORY_SEPARATOR) . DIRECTORY_SEPARATOR;
    if (!str_starts_with($destino, $prefijo)) {
        return null;
    }
    return $destino;
}

/**
 * Extrae el último objeto/array JSON de la salida del motor.
 *
 * `shell_exec` con `2>&1` mezcla el stdout (nuestro JSON) con avisos de
 * insightface/ONNX. El JSON se imprime siempre al final, así que se recorre la
 * salida de atrás hacia delante hasta la primera línea parseable.
 *
 * @return array|null Array/objeto decodificado, o null si no hay JSON.
 */
function rf_revision_json_ultimo(string $salida): ?array
{
    $lineas = preg_split('/\r?\n/', trim($salida));
    if (!is_array($lineas)) {
        return null;
    }
    for ($i = count($lineas) - 1; $i >= 0; $i--) {
        $linea = trim($lineas[$i]);
        if ($linea === '') {
            continue;
        }
        $dec = json_decode($linea, true);
        if (is_array($dec)) {
            return $dec;
        }
    }
    return null;
}
