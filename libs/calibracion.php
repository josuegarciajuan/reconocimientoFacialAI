<?php

/* 
 * La Forja · Templar — librería del calibrador guiado.
 *
 * 2026-08-20:
 *  - Valores de fábrica (CONFIG_*) y metadatos de los 7 parámetros de análisis por cámara.
 *  - Lectura de recomendaciones del probe (motor/calibrador/recomendaciones/<camara>.json).
 *  - Journal de calibración en la tabla `calibraciones` (reversible: guarda el "antes").
 *
 * Regla: git = código, no datos. Las recomendaciones y el journal son runtime.
 */

require_once __DIR__ . "/db.php";

/** Metadatos de los 7 parámetros de análisis por cámara (dominio -> sección del form). */
function calib_parametros(): array
{
    return [
        "segundos_analizar" => [
            "label"   => "Segundos a analizar",
            "dominio" => "movimiento",
            "factory" => (int) (defined("CONFIG_segundos_analizar") ? CONFIG_segundos_analizar : 2),
            "rango"   => [1, 10],
            "unidad"  => "s",
            "lore"    => "Ventana (en segundos) que mira el centinela para decidir si hay movimiento.",
        ],
        "porcentaje_mov" => [
            "label"   => "Porcentaje de movimiento",
            "dominio" => "movimiento",
            "factory" => (int) (defined("CONFIG_porcentaje_mov") ? CONFIG_porcentaje_mov : 60),
            "rango"   => [1, 100],
            "unidad"  => "%",
            "lore"    => "Porcentaje de frames con movimiento necesarios en la ventana para disparar.",
        ],
        "dontCare" => [
            "label"   => "Área mínima de movimiento (px²)",
            "dominio" => "movimiento",
            "factory" => (int) (defined("CONFIG_dontCare") ? CONFIG_dontCare : 220),
            "rango"   => [10, 2000],
            "unidad"  => "px²",
            "lore"    => "Área mínima del contorno (px²) sobre el frame redimensionado por «Redimensionar frame».",
        ],
        "fps" => [
            "label"   => "FPS",
            "dominio" => "rendimiento",
            "factory" => (int) (defined("CONFIG_fps") ? CONFIG_fps : 14),
            "rango"   => [1, 30],
            "unidad"  => "fps",
            "lore"    => "Cadencia de análisis/captura: más alto = movimiento más fluido y más CPU.",
        ],
        "sensibilidad" => [
            "label"   => "Salto de frames (cada N)",
            "dominio" => "rendimiento",
            "factory" => (int) (defined("CONFIG_sensibilidad") ? CONFIG_sensibilidad : 1),
            "rango"   => [1, 15],
            "unidad"  => "N",
            "lore"    => "Se analiza 1 de cada N frames: más alto = menos CPU y menos sensibilidad.",
        ],
        "redimesionframe" => [
            "label"   => "Redimensionar frame",
            "dominio" => "rendimiento",
            "factory" => (int) (defined("CONFIG_redimesionframe") ? CONFIG_redimesionframe : 60),
            "rango"   => [1, 100],
            "unidad"  => "%",
            "lore"    => "Escala del frame de análisis. Afecta al área mínima (dontCare) y a la CPU.",
        ],
        "maximo_videos" => [
            "label"   => "Máximo de vídeos",
            "dominio" => "almacenamiento",
            "factory" => (int) (defined("CONFIG_maximo_videos") ? CONFIG_maximo_videos : 60),
            "rango"   => [20, 120],
            "unidad"  => "s",
            "lore"    => "Longitud máxima de cada clip de movimiento (disco).",
        ],
    ];
}

/** Ruta absoluta al JSON de recomendaciones de una cámara (0 = global). */
function calib_ruta_recomendaciones(int $camara_id): string
{
    return rtrim(RUTA_PROYECTO, "/") . "/motor/calibrador/recomendaciones/" . (int) $camara_id . ".json";
}

/** Recomendaciones vigentes de una cámara: {parametro: {recomendado, motivo}} o [] si no hay. */
function calib_recomendaciones(int $camara_id): array
{
    $f = calib_ruta_recomendaciones($camara_id);
    if (!is_file($f)) {
        return [];
    }
    $data = json_decode((string) file_get_contents($f), true);
    if (!is_array($data) || !isset($data["recomendaciones"])) {
        return [];
    }
    $out = [];
    foreach ($data["recomendaciones"] as $k => $v) {
        if (is_array($v) && array_key_exists("recomendado", $v)) {
            $out[$k] = $v;
        }
    }
    return $out;
}

/** Recomendaciones de parámetros POR CÁMARA (mismo fichero, sección por_camara). */
function calib_recomendaciones_camara(int $camara_id): array
{
    $f = calib_ruta_recomendaciones($camara_id);
    if (!is_file($f)) {
        return [];
    }
    $data = json_decode((string) file_get_contents($f), true);
    if (!is_array($data) || !isset($data["por_camara"])) {
        return [];
    }
    $out = [];
    foreach ($data["por_camara"] as $k => $v) {
        if (is_array($v) && array_key_exists("recomendado", $v)) {
            $out[$k] = $v;
        }
    }
    return $out;
}

/** Escribe (o actualiza) las recomendaciones de una cámara. */
function calib_guardar_recomendaciones(int $camara_id, array $recomendaciones, array $por_camara = [], string $ritual = ""): void
{
    $dir = dirname(calib_ruta_recomendaciones($camara_id));
    if (!is_dir($dir)) {
        @mkdir($dir, 0777, true);
    }
    $data = [
        "camara_id"     => $camara_id,
        "actualizados"  => date("Y-m-d H:i:s"),
        "ritual"        => $ritual,
        "recomendaciones" => $recomendaciones,
        "por_camara"    => $por_camara,
    ];
    @file_put_contents(calib_ruta_recomendaciones($camara_id), json_encode($data, JSON_PRETTY_PRINT | JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES));
}

/**
 * Journal de calibración: registra un cambio aplicado con su valor anterior.
 * Si $despues es null, se interpreta como "restauración" (despues = valor de fábrica).
 */
function calib_journal(int $local_id, int $camara_id, string $ambito, string $parametro, $antes, $despues): void
{
    try {
        DB::insert(
            "INSERT INTO calibraciones (local_id, camara_id, ambito, parametro, antes, despues, aplicado)
             VALUES (?, ?, ?, ?, ?, ?, 1)",
            [
                $local_id,
                $camara_id,
                in_array($ambito, ["camara", "global"], true) ? $ambito : "camara",
                $parametro,
                $antes === null ? null : (string) $antes,
                $despues === null ? null : (string) $despues,
            ]
        );
    } catch (Throwable $e) {
        // El journal nunca debe romper la operación principal.
    }
}

/** Aplica parámetros por cámara (7 columnas) con journal de cada uno. */
function calib_aplicar_parametros(int $local_id, int $camara_id, array $params): void
{
    $actual = DB::selectOne("SELECT * FROM camaras WHERE id = ? AND local_id = ?", [$camara_id, $local_id]);
    if (!$actual) {
        return;
    }
    $set = [];
    $bind = [];
    foreach (calib_parametros() as $k => $meta) {
        if (!array_key_exists($k, $params)) {
            continue;
        }
        $v = (int) $params[$k];
        $v = max((int) $meta["rango"][0], min((int) $meta["rango"][1], $v));
        $set[] = "`$k` = ?";
        $bind[] = $v;
        if ((int) $actual[$k] !== $v) {
            calib_journal($local_id, $camara_id, "camara", $k, $actual[$k], $v);
        }
    }
    if (!$set) {
        return;
    }
    $bind[] = $camara_id;
    DB::execute("UPDATE camaras SET " . implode(", ", $set) . " WHERE id = ? AND local_id = ?", $bind);
}

/** Restaura los 7 parámetros de una cámara a los valores de fábrica (CONFIG_*). */
function calib_restaurar_camara(int $local_id, int $camara_id): void
{
    $factory = [];
    foreach (calib_parametros() as $k => $meta) {
        $factory[$k] = $meta["factory"];
    }
    calib_aplicar_parametros($local_id, $camara_id, $factory);
}

/**
 * Restaura una variable GLOBAL del .env a su valor de fábrica (borra la línea para
 * que aplique el default del código). Devuelve la lista de claves tocadas.
 * Hace copia de seguridad .env.bak.<ts> antes de escribir (datos runtime, no git).
 */
function calib_restaurar_globales(int $local_id): array
{
    $env = RUTA_PROYECTO . ".env";
    if (!is_file($env)) {
        return [];
    }
    $lineas = file($env, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    $tocadas = [];
    $resto = [];
    foreach ($lineas as $l) {
        $l = rtrim($l);
        if (preg_match('/^RF_[A-Z0-9_]+\s*=/', $l)) {
            $k = trim(explode("=", $l, 2)[0]);
            $v = trim(explode("=", $l, 2)[1] ?? "");
            $tocadas[$k] = trim($v, "\"'");
        } else {
            $resto[] = $l;
        }
    }
    if (!$tocadas) {
        return [];
    }
    // Copia de seguridad antes de tocar (nunca commitear .env ni .bak).
    @copy($env, $env . ".bak." . date("Ymd_His"));
    @file_put_contents($env, implode("\n", $resto) . "\n");
    foreach ($tocadas as $k => $antes) {
        calib_journal($local_id, 0, "global", $k, $antes, "(default)");
    }
    return array_keys($tocadas);
}

/**
 * Aplica al .env las recomendaciones GLOBALES (RF_*) de una cámara: sustituye o
 * añade la línea con el valor recomendado. Copia de seguridad + journal por clave.
 * Devuelve {clave: valor} aplicado (vacío si no hay recomendaciones RF_*).
 */
function calib_aplicar_globales(int $local_id, int $camara_id): array
{
    $reco = calib_recomendaciones($camara_id);
    if (!$reco) {
        return [];
    }
    $keys = array_filter(array_keys($reco), function ($k) {
        return (bool) preg_match('/^RF_[A-Z0-9_]+$/', (string) $k);
    });
    if (!$keys) {
        return [];
    }

    $env = RUTA_PROYECTO . ".env";
    $env_lines = is_file($env) ? file($env, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) : [];

    $resto = [];
    $antes_map = [];
    foreach ($env_lines as $l) {
        $l = rtrim($l);
        $match = null;
        foreach ($keys as $k) {
            if (preg_match('/^' . preg_quote($k, "/") . '\s*=/', $l)) {
                $match = $k;
                break;
            }
        }
        if ($match !== null) {
            $antes_map[$match] = trim(explode("=", $l, 2)[1] ?? "", "\"'");
        } else {
            $resto[] = $l;
        }
    }

    $nuevas = [];
    $aplicadas = [];
    foreach ($keys as $k) {
        $v = $reco[$k]["recomendado"] ?? null;
        if ($v === null) {
            continue;
        }
        $nuevas[] = $k . "=" . $v;
        calib_journal($local_id, 0, "global", $k, $antes_map[$k] ?? null, (string) $v);
        $aplicadas[$k] = $v;
    }
    if (!$nuevas) {
        return [];
    }

    @copy($env, $env . ".bak." . date("Ymd_His"));
    @file_put_contents($env, implode("\n", array_merge($resto, [""], $nuevas)) . "\n");
    return $aplicadas;
}

/* =====================================================================
 * Vigilancia de deriva (F3) — motor/vigilar_deriva.py, 1x/día por timer
 * ===================================================================== */

/** Ruta base de los datos de deriva (gitignored). */
function calib_deriva_dir(): string
{
    return rtrim(RUTA_PROYECTO, "/") . "/motor/calibrador/deriva";
}

/** Alertas de deriva activas (motor/calibrador/deriva/alertas.json) del local. */
function calib_deriva_alertas(int $local_id): array
{
    $f = calib_deriva_dir() . "/alertas.json";
    if (!is_file($f)) {
        return [];
    }
    $data = json_decode((string) file_get_contents($f), true);
    if (!is_array($data) || !$data) {
        return [];
    }
    $cams = [];
    foreach (DB::select("SELECT id, descripcion, local_id FROM camaras") as $c) {
        $cams[(int) $c["id"]] = $c;
    }
    $out = [];
    foreach ($data as $cam_id => $a) {
        $cam_id = (int) $cam_id;
        $c = $cams[$cam_id] ?? null;
        if (!$c || (int) $c["local_id"] !== $local_id) {
            continue;
        }
        $out[] = [
            "camara_id"   => $cam_id,
            "descripcion" => $c["descripcion"],
            "fecha"       => $a["fecha"] ?? "",
            "similitud"   => $a["similitud"] ?? null,
            "dias_bajos"  => (int) ($a["dias_bajos"] ?? 0),
            "celdas"      => $a["celdas"] ?? [],
        ];
    }
    return $out;
}

/** Estado de deriva por cámara del local (para la tabla de Templar · General). */
function calib_deriva_estado(int $local_id): array
{
    $dir = calib_deriva_dir();
    $alertas = [];
    $f_alertas = $dir . "/alertas.json";
    if (is_file($f_alertas)) {
        $alertas = json_decode((string) file_get_contents($f_alertas), true) ?: [];
    }
    $out = [];
    foreach (DB::select("SELECT id, descripcion FROM camaras WHERE local_id = ? ORDER BY id ASC", [$local_id]) as $c) {
        $f = $dir . "/" . (int) $c["id"] . ".json";
        $st = is_file($f) ? (json_decode((string) file_get_contents($f), true) ?: []) : [];
        $out[] = [
            "camara_id"          => (int) $c["id"],
            "descripcion"        => $c["descripcion"],
            "fecha_ultimo_check" => $st["fecha_ultimo_check"] ?? null,
            "fecha_referencia"   => $st["fecha_referencia"] ?? null,
            "n_dias"             => (int) ($st["n_dias"] ?? 0),
            "ultima_sim"         => $st["ultima_sim"] ?? null,
            "dias_bajos"         => (int) ($st["dias_bajos"] ?? 0),
            "alerta"             => isset($alertas[(string) (int) $c["id"]]),
        ];
    }
    return $out;
}
