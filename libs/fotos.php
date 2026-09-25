<?php

/*
 * libs/fotos.php — Rutas y existencia de las fotos del panel.
 *
 * Las fotos viven en `admin/caras_procesadas/<foto_id>.jpg` (datos runtime,
 * gitignored). Pueden faltar aunque exista la fila en `fotos` (p. ej. una
 * publicación fallida de una versión antigua del clasificador). Estas funciones
 * son la fuente única de verdad para no pintar <img> rotas en el panel.
 */

require_once __DIR__ . "/db.php";

/** Ruta absoluta del fichero de una foto publicada. */
function foto_path(int $foto_id): string
{
    return rtrim(RUTA_PROYECTO, "/") . "/admin/caras_procesadas/" . $foto_id . ".jpg";
}

/** ¿Existe el fichero de la foto en disco? */
function foto_existe(int $foto_id): bool
{
    return $foto_id > 0 && is_file(foto_path($foto_id));
}

/** URL relativa lista para <img> ("" si el fichero no existe). */
function foto_url(int $foto_id): string
{
    return foto_existe($foto_id) ? "./caras_procesadas/" . (int)$foto_id . ".jpg" : "";
}

/**
 * URL de la primera foto EXISTENTE de una persona.
 * Con $nueva=true devuelve la última existente (más reciente).
 */
function foto_persona_url(int $persona_id, bool $nueva = false): string
{
    if ($persona_id <= 0) {
        return "";
    }
    $orden = $nueva ? "DESC" : "ASC";
    $rows = DB::select(
        "SELECT f.id FROM fotos f JOIN estancias e ON e.id = f.estancia_id
         WHERE e.persona_id = ? ORDER BY f.id " . $orden,
        [$persona_id]
    );
    foreach ($rows as $r) {
        $id = (int)$r["id"];
        if (foto_existe($id)) {
            return "./caras_procesadas/" . $id . ".jpg";
        }
    }
    return "";
}

/**
 * URL de la primera foto EXISTENTE de una estancia.
 * Con $nueva=true devuelve la última existente (más reciente).
 */
function foto_estancia_url(int $estancia_id, bool $nueva = false): string
{
    if ($estancia_id <= 0) {
        return "";
    }
    $orden = $nueva ? "DESC" : "ASC";
    $rows = DB::select("SELECT id FROM fotos WHERE estancia_id = ? ORDER BY id " . $orden, [$estancia_id]);
    foreach ($rows as $r) {
        $id = (int)$r["id"];
        if (foto_existe($id)) {
            return "./caras_procesadas/" . $id . ".jpg";
        }
    }
    return "";
}
