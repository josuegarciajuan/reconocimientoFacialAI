<?php

/*
 * Plano del local — resolución del plano activo (Fase 2026-08-19).
 * Un local puede tener DOS planos en admin/pages/config/planos/:
 *   * plano_<local_id>.<ext>      -> imagen subida (comportamiento legacy).
 *   * plano_dibujo_<local_id>.png -> croquis dibujado a mano alzada.
 * La columna locales.plano_activo ('subida'|'dibujo') decide cuál se usa.
 * Si el plano activo no existe (p. ej. migración sin aplicar), se cae al otro.
 */

require_once __DIR__ . "/db.php";

/** Devuelve 'subida'|'dibujo': el plano marcado como activo (default 'subida'). */
function plano_activo($local_id)
{
    try {
        $row = DB::selectOne("SELECT plano_activo FROM locales WHERE id = ?", [(int)$local_id]);
        if ($row && in_array($row["plano_activo"], ["subida", "dibujo"], true)) {
            return $row["plano_activo"];
        }
    } catch (Throwable $e) {
        // Columna aún no migrada: comportamiento legacy (imagen subida).
    }
    return "subida";
}

/** Directorio absoluto donde se guardan los planos. */
function plano_dir()
{
    return rtrim(defined("RUTA_PROYECTO") ? RUTA_PROYECTO : dirname(__DIR__) . "/", "/") . "/admin/pages/config/planos/";
}

/** Extensiones aceptadas para la imagen subida (legacy). */
function plano_extensiones()
{
    return ["jpg", "jpeg", "png", "bmp"];
}

/** Devuelve la ruta relativa (URL) del plano activo, o "" si no hay ninguno. */
function plano_url($local_id)
{
    $local_id = (int)$local_id;
    $dir = plano_dir();

    // Orden de preferencia: activo primero, luego el otro como fallback.
    $candidatos = ["subida" => [], "dibujo" => []];
    foreach (plano_extensiones() as $ext) {
        $candidatos["subida"][] = "pages/config/planos/plano_" . $local_id . "." . $ext;
    }
    $candidatos["dibujo"][] = "pages/config/planos/plano_dibujo_" . $local_id . ".png";

    $activo = plano_activo($local_id);
    $orden = ($activo === "dibujo") ? ["dibujo", "subida"] : ["subida", "dibujo"];

    foreach ($orden as $tipo) {
        foreach ($candidatos[$tipo] as $rel) {
            if (file_exists($dir . basename($rel))) {
                return $rel;
            }
        }
    }
    return "";
}

/** ¿Existe ya un croquis dibujado para este local? */
function plano_dibujo_existe($local_id)
{
    return file_exists(plano_dir() . "plano_dibujo_" . (int)$local_id . ".png");
}

/** ¿Existe una imagen subida para este local? */
function plano_subida_existe($local_id)
{
    $dir = plano_dir();
    foreach (plano_extensiones() as $ext) {
        if (file_exists($dir . "plano_" . (int)$local_id . "." . $ext)) {
            return true;
        }
    }
    return false;
}
