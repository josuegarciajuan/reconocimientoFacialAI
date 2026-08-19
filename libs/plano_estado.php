<?php

/*
 * libs/plano_estado.php — Estado y grafo de senderos de La Forja (2026-08-19).
 *
 * Nuevo modelo de recorridos (sustituye a las cadenas cámara→cámara de `nodos`):
 *   * NODO del grafo:
 *       - tipo 'camara'      -> cámara SIN líneas configuradas (posición x/y).
 *       - tipo 'linea_plano' -> línea de cámara colocada en el plano (punto medio).
 *   * SENDERO (arista): conexión entre dos nodos (recto/ortogonal/curvo).
 *
 * Compleción:
 *   * Una cámara está "completa" si no tiene líneas o todas sus líneas tienen
 *     representación en lineas_plano (linea_id vinculado).
 *   * El plano está "completo" si todas las cámaras están colocadas y completas.
 *
 * Funciones puras (testeables) + acceso a datos PDO (DB).
 */

require_once __DIR__ . "/db.php";

/**
 * Cámaras de un local con su estado de completado.
 * Añade a cada fila: colocada, num_lineas, num_lineas_plano, completa.
 * @return array filas enriquecidas de `camaras`
 */
function camaras_con_estado(int $local_id): array
{
    $filas = DB::select(
        "SELECT c.*,
                (SELECT COUNT(*) FROM lineas l WHERE l.camara_id = c.id AND l.eliminada = 0) AS num_lineas,
                (SELECT COUNT(*) FROM lineas l
                  JOIN lineas_plano lp ON lp.linea_id = l.id AND lp.eliminada = 0
                  WHERE l.camara_id = c.id AND l.eliminada = 0) AS num_lineas_plano
         FROM camaras c
         WHERE c.local_id = ?
         ORDER BY c.id ASC",
        [(int)$local_id]
    );
    foreach ($filas as &$c) {
        $c["colocada"] = (int)($c["colocada"] ?? 0);
        $nl  = (int)($c["num_lineas"] ?? 0);
        $nlp = (int)($c["num_lineas_plano"] ?? 0);
        $c["num_lineas"] = $nl;
        $c["num_lineas_plano"] = $nlp;
        $c["completa"] = ($nl === 0) || ($nl === $nlp);
    }
    unset($c);
    return $filas;
}

/**
 * ¿Está completa una fila de cámara (enriquecida por camaras_con_estado)?
 * @param array $cam fila con claves num_lineas / num_lineas_plano
 */
function camara_es_completa(array $cam): bool
{
    $nl  = (int)($cam["num_lineas"] ?? 0);
    $nlp = (int)($cam["num_lineas_plano"] ?? 0);
    return ($nl === 0) || ($nl === $nlp);
}

/**
 * ¿Está completo el plano del local?
 * Todas las cámaras colocadas en el plano Y completas (líneas colocadas).
 */
function plano_completo(int $local_id): bool
{
    $cams = camaras_con_estado($local_id);
    if (!$cams) {
        return false;
    }
    foreach ($cams as $c) {
        if ((int)($c["colocada"] ?? 0) !== 1) {
            return false;
        }
        if (!camara_es_completa($c)) {
            return false;
        }
    }
    return true;
}

/**
 * Nodos del grafo de un local.
 * @return array [{tipo:'camara'|'linea_plano', ref_id, x, y, nombre}]
 */
function nodos_del_local(int $local_id): array
{
    $out = [];

    // Nodos-cámara: cámaras colocadas SIN líneas configuradas.
    $cams = DB::select(
        "SELECT c.id, c.x, c.y, c.descripcion
         FROM camaras c
         WHERE c.local_id = ? AND c.colocada = 1
           AND NOT EXISTS (SELECT 1 FROM lineas l WHERE l.camara_id = c.id AND l.eliminada = 0)
         ORDER BY c.id ASC",
        [(int)$local_id]
    );
    foreach ($cams as $c) {
        $out[] = [
            "tipo"   => "camara",
            "ref_id" => (int)$c["id"],
            "x"      => (int)$c["x"],
            "y"      => (int)$c["y"],
            "nombre" => (string)$c["descripcion"],
        ];
    }

    // Nodos-línea: líneas de cámara colocadas en el plano (punto medio).
    $lineas = DB::select(
        "SELECT lp.id, lp.nombre, lp.x1, lp.y1, lp.x2, lp.y2
         FROM lineas_plano lp
         JOIN camaras c ON c.id = lp.camara_id
         WHERE c.local_id = ? AND lp.eliminada = 0
         ORDER BY lp.id ASC",
        [(int)$local_id]
    );
    foreach ($lineas as $l) {
        $out[] = [
            "tipo"   => "linea_plano",
            "ref_id" => (int)$l["id"],
            "x"      => (int)round(((int)$l["x1"] + (int)$l["x2"]) / 2),
            "y"      => (int)round(((int)$l["y1"] + (int)$l["y2"]) / 2),
            "nombre" => (string)$l["nombre"],
        ];
    }

    return $out;
}

/**
 * Senderos de un local con sus puntos intermedios ordenados.
 * @return array [{id, origen_tipo, origen_id, destino_tipo, destino_id,
 *                estilo, nombre, puntos:[[x,y],...]}]
 */
function senderos_del_local(int $local_id): array
{
    $senderos = DB::select(
        "SELECT * FROM senderos WHERE local_id = ? ORDER BY id ASC",
        [(int)$local_id]
    );
    if (!$senderos) {
        return [];
    }

    $ids = array_column($senderos, "id");
    $in = implode(",", array_fill(0, count($ids), "?"));
    $puntos_raw = DB::select(
        "SELECT sendero_id, x, y FROM senderos_puntos WHERE sendero_id IN ($in) ORDER BY sendero_id ASC, orden ASC",
        $ids
    );

    $puntos = [];
    foreach ($puntos_raw as $p) {
        $puntos[(int)$p["sendero_id"]][] = [(int)$p["x"], (int)$p["y"]];
    }

    $out = [];
    foreach ($senderos as $s) {
        $out[] = [
            "id"           => (int)$s["id"],
            "origen_tipo"  => (string)$s["origen_tipo"],
            "origen_id"    => (int)$s["origen_id"],
            "destino_tipo" => (string)$s["destino_tipo"],
            "destino_id"   => (int)$s["destino_id"],
            "estilo"       => (string)$s["estilo"],
            "nombre"       => (string)($s["nombre"] ?? ""),
            "puntos"       => $puntos[(int)$s["id"]] ?? [],
        ];
    }
    return $out;
}
