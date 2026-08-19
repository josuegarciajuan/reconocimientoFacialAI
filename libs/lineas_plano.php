<?php

/*
 * libs/lineas_plano.php — Vínculo 1:1 línea de cámara (lineas) ↔ línea del plano (lineas_plano).
 *
 * Una línea de vigilancia se dibuja sobre lo que enfoca la cámara (`lineas`) y
 * se registra un cruce si algo la atraviesa. La MISMA línea se representa sobre
 * el plano 2D del local (`lineas_plano`) para ver en el mapa dónde enfoca cada
 * cámara. La columna `lineas_plano.linea_id` (UNIQUE, nullable) une ambos lados.
 *
 * Funciones puras (testeables sin BD) + acceso a datos PDO (DB).
 */

require_once __DIR__ . "/db.php";

/**
 * Normaliza una fila de lineas_plano (o de lineas) a UTF-8 válido para json_encode.
 * La BD es latin1; sin esto, json_encode devuelve false y el JS se rompe.
 */
function lineas_plano_utf8(array $row): array
{
    $fix = function ($v) {
        $v = (string)$v;
        return ($v !== "" && function_exists("mb_check_encoding") && !mb_check_encoding($v, "UTF-8"))
            ? mb_convert_encoding($v, "UTF-8", "latin1")
            : $v;
    };
    foreach ($row as $k => $v) {
        if (is_string($v)) {
            $row[$k] = $fix($v);
        }
    }
    return $row;
}

/**
 * Vincula una línea del plano con su línea de cámara (1:1).
 * Si la línea de cámara ya estaba vinculada a otra línea del plano, se reasigna
 * (la antigua queda sin vínculo). Con $lineaId <= 0 desvincula.
 * @return bool éxito
 */
function lineas_plano_vincular(int $planoId, int $lineaId): bool
{
    if ($planoId <= 0) {
        return false;
    }
    DB::beginTransaction();
    try {
        if ($lineaId > 0) {
            // Desvincula cualquier línea del plano que ya representara esta línea de cámara.
            DB::execute("UPDATE lineas_plano SET linea_id = NULL WHERE linea_id = ? AND id <> ?", [$lineaId, $planoId]);
        }
        DB::execute("UPDATE lineas_plano SET linea_id = ? WHERE id = ? AND eliminada = 0", [$lineaId > 0 ? $lineaId : null, $planoId]);
        DB::commit();
        return true;
    } catch (Throwable $e) {
        DB::rollBack();
        return false;
    }
}

/** Desvincula la línea del plano de su línea de cámara. */
function lineas_plano_desvincular(int $planoId): bool
{
    return lineas_plano_vincular($planoId, 0);
}

/**
 * Líneas de cámara de una cámara que AÚN no tienen representación en el plano.
 * @return array filas de `lineas` (id, nombre, x1..y2)
 */
function lineas_sin_plano(int $camaraId): array
{
    if ($camaraId <= 0) {
        return [];
    }
    return DB::select(
        "SELECT l.id, l.nombre, l.x1, l.y1, l.x2, l.y2
         FROM lineas l
         WHERE l.camara_id = ? AND l.eliminada = 0
           AND NOT EXISTS (SELECT 1 FROM lineas_plano lp WHERE lp.linea_id = l.id)
         ORDER BY l.id ASC",
        [$camaraId]
    );
}

/** La línea del plano que representa una línea de cámara, o null. */
function linea_plano_de_linea(int $lineaId): ?array
{
    if ($lineaId <= 0) {
        return null;
    }
    return DB::selectOne(
        "SELECT lp.*, c.descripcion AS camara_nombre
         FROM lineas_plano lp
         LEFT JOIN camaras c ON c.id = lp.camara_id
         WHERE lp.linea_id = ? AND lp.eliminada = 0",
        [$lineaId]
    );
}

/**
 * Líneas del plano de un local listas para el mapa (rutas/player y forja):
 * con su línea de cámara vinculada (nombre + id) para dibujar el rayo de enfoque.
 * @return array filas enriquecidas
 */
function lineas_plano_del_local(int $localId): array
{
    $filas = DB::select(
        "SELECT lp.*, c.descripcion AS camara_nombre,
                l.nombre AS linea_camara_nombre, l.camara_id AS linea_camara_fk
         FROM lineas_plano lp
         JOIN camaras c ON c.id = lp.camara_id
         LEFT JOIN lineas l ON l.id = lp.linea_id
         WHERE c.local_id = ? AND lp.eliminada = 0
         ORDER BY lp.id DESC",
        [$localId]
    );
    return array_map("lineas_plano_utf8", $filas);
}
