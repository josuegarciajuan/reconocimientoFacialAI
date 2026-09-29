<?php

/** Staging path written by Python before the PHP row exists. */
function foto_original_staging_path(string $local_id, string $camera_id, string $correlation_id): string
{
    foreach ([$local_id, $camera_id, $correlation_id] as $part) {
        if ($part === '' || preg_match('/[^A-Za-z0-9_.-]/', $part)) {
            throw new InvalidArgumentException('Componente de evidencia no válido');
        }
    }
    return rtrim(RUTA_PROYECTO, '/') . '/motor/photo_evidence/' . $local_id . '/' .
        $camera_id . '/' . $correlation_id . '.jpg';
}

function foto_original_path(int $foto_id): string
{
    return rtrim(RUTA_PROYECTO, '/') . '/admin/fotos_originales/' . $foto_id . '.jpg';
}

function foto_original_existe(int $foto_id): bool
{
    return $foto_id > 0 && is_file(foto_original_path($foto_id));
}

function foto_original_url(int $foto_id): string
{
    return foto_original_existe($foto_id) ? './fotos_originales/' . $foto_id . '.jpg' : '';
}

/** Publishes the native-resolution frame once `fotos.id` is available. */
function ingest_photo_original(int $foto_id, string $correlation_id, string $local_id, string $camera_id): bool
{
    try {
        $source = foto_original_staging_path($local_id, $camera_id, $correlation_id);
    } catch (InvalidArgumentException $e) {
        return false;
    }
    if (!is_file($source) || filesize($source) <= 0) {
        return false;
    }
    $dir = dirname(foto_original_path($foto_id));
    if (!is_dir($dir)) {
        @mkdir($dir, 0755, true);
    }
    $target = foto_original_path($foto_id);
    if (@rename($source, $target)) {
        @chmod($target, 0644);
        return true;
    }
    return false;
}
