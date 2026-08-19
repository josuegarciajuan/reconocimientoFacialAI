<?php

/*
 * libs/avatars.php — Avatar por persona (cabeza recortada con fondo transparente).
 *
 * El PNG lo genera motor/avatar.py (venv) en admin/caras_procesadas/avatares/
 * con un sidecar <png>.foto que indica qué foto se usó. Este lib gestiona:
 *   - avatar_url(): URL pública del avatar (o "" si aún no existe).
 *   - avatar_generar(): lanza la generación en segundo plano si hace falta
 *     (patrón dofoto.py) y persiste el resultado en `personas_avatar`.
 */

require_once __DIR__ . "/db.php";

/** Directorio absoluto de los avatares. */
function avatars_dir(): string
{
    return rtrim(RUTA_PROYECTO, "/") . "/admin/caras_procesadas/avatares/";
}

/** Ruta absoluta del PNG del avatar de una persona. */
function avatar_png_path(int $persona_id): string
{
    return avatars_dir() . $persona_id . ".png";
}

/** Sidecar con el id de la foto elegida. */
function avatar_sidecar_path(int $persona_id): string
{
    return avatar_png_path($persona_id) . ".foto";
}

/** URL relativa del avatar ("" si no existe). */
function avatar_url(int $persona_id): string
{
    if ($persona_id <= 0) {
        return "";
    }
    $png = avatar_png_path($persona_id);
    if (!is_file($png)) {
        return "";
    }
    return "caras_procesadas/avatares/" . $persona_id . ".png?v=" . filemtime($png);
}

/**
 * Garantiza el avatar: devuelve estado listo|generando|pendiente.
 * Si el PNG ya existe (con sidecar), persiste personas_avatar y devuelve listo.
 * Si un proceso está en marcha, devuelve generando.
 * Si no, lanza motor/avatar.py en segundo plano (--fotos) y devuelve generando.
 */
function avatar_generar(int $persona_id, array $fotos = []): array
{
    $png = avatar_png_path($persona_id);
    $sidecar = avatar_sidecar_path($persona_id);
    $marker = $png . ".pid";

    // 1) Ya generado: persiste el resultado y listo.
    if (is_file($png) && is_file($sidecar)) {
        $foto_id = (int)trim((string)file_get_contents($sidecar));
        if ($foto_id > 0) {
            DB::execute(
                "INSERT INTO personas_avatar (persona_id, foto_id, png) VALUES (?, ?, ?)
                 ON DUPLICATE KEY UPDATE foto_id = VALUES(foto_id), png = VALUES(png)",
                [$persona_id, $foto_id, "caras_procesadas/avatares/" . $persona_id . ".png"]
            );
        }
        return ["ok" => true, "estado" => "listo", "foto_id" => $foto_id];
    }

    // 2) Proceso en marcha (pid vivo) -> generando.
    if (is_file($marker)) {
        $pid = (int)trim((string)file_get_contents($marker));
        if ($pid > 0 && is_dir("/proc/" . $pid)) {
            return ["ok" => true, "estado" => "generando", "foto_id" => 0];
        }
        @unlink($marker); // pid muerto: relanzar
    }

    // 3) Lanzar en segundo plano.
    $fotos_ok = [];
    foreach ($fotos as $fid) {
        $fid = (int)$fid;
        if ($fid <= 0) {
            continue;
        }
        $jpg = rtrim(RUTA_PROYECTO, "/") . "/admin/caras_procesadas/" . $fid . ".jpg";
        if (is_file($jpg)) {
            $fotos_ok[] = $fid . ":" . $jpg;
        }
    }
    if (!$fotos_ok) {
        // Sin fotos: marcar como pendiente (el perfil usa el fallback normal).
        return ["ok" => false, "estado" => "pendiente", "foto_id" => 0];
    }

    $cmd = RUTA_PYTHON . " " . RUTA_PROYECTO . "motor/avatar.py --fotos \""
         . implode(";", $fotos_ok) . "\" --out " . $png . " > /dev/null 2>&1 &";
    $pid = (int)shell_exec($cmd . " echo $!");
    if ($pid > 0) {
        @file_put_contents($marker, (string)$pid);
    }
    return ["ok" => true, "estado" => "generando", "foto_id" => 0];
}

/** Fotos candidatas de una persona (las más recientes, acotadas). */
function avatar_fotos_candidatas(int $persona_id, int $limite = 20): array
{
    if ($persona_id <= 0) {
        return [];
    }
    $rows = DB::select(
        "SELECT f.id FROM fotos f JOIN estancias e ON e.id = f.estancia_id
         WHERE e.persona_id = ? ORDER BY f.id DESC LIMIT ?",
        [$persona_id, $limite]
    );
    return array_map(fn($r) => (int)$r["id"], $rows);
}
