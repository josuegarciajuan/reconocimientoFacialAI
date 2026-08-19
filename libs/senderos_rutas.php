<?php

/*
 * libs/senderos_rutas.php — Recorrido del monigote sobre el grafo de senderos.
 *
 * La sección Caminos anima a una persona sobre el plano. En el nuevo modelo:
 *   * NODOS del grafo: cámaras SIN líneas (nodo-cámara) o líneas de cámara
 *     colocadas en el plano (nodo-línea).
 *   * SENDEROS: aristas entre nodos (recto/ortogonal/curvo), con puntos intermedios.
 *
 * Este lib construye el grafo a partir de `senderos`/`senderos_puntos` y calcula
 * el camino más corto entre dos nodos para que el monigote siga los pasillos
 * trazados (no rectas entre cámaras).
 *
 * Funciones puras (testeables) + acceso a datos PDO (DB).
 */

require_once __DIR__ . "/db.php";
require_once __DIR__ . "/plano_estado.php";

/** Clave canónica de un nodo. */
function sendero_nodo_key(string $tipo, int $ref_id): string
{
    return $tipo . ":" . $ref_id;
}

/**
 * Construye el grafo de senderos de un local.
 * @return array ["nodos" => [key => nodo], "ady" => [key => [["nodo"=>key, "sendero"=>sendero], ...]]]
 */
function senderos_grafo(int $local_id): array
{
    $nodos = nodos_del_local($local_id);
    $senderos = senderos_del_local($local_id);

    $grafo = ["nodos" => [], "ady" => []];
    foreach ($nodos as $n) {
        $k = sendero_nodo_key($n["tipo"], $n["ref_id"]);
        $grafo["nodos"][$k] = $n;
        $grafo["ady"][$k] = [];
    }
    foreach ($senderos as $s) {
        $a = sendero_nodo_key($s["origen_tipo"], $s["origen_id"]);
        $b = sendero_nodo_key($s["destino_tipo"], $s["destino_id"]);
        if (!isset($grafo["ady"][$a]) || !isset($grafo["ady"][$b])) {
            continue;
        }
        $grafo["ady"][$a][] = ["nodo" => $b, "sendero" => $s];
        $grafo["ady"][$b][] = ["nodo" => $a, "sendero" => $s];
    }
    return $grafo;
}

/**
 * Polilínea completa de un sendero: nodo origen -> puntos intermedios -> nodo destino.
 * @return array [[x,y], ...]
 */
function sendero_polilinea(array $grafo, array $sendero): array
{
    $a = $grafo["nodos"][sendero_nodo_key($sendero["origen_tipo"], $sendero["origen_id"])] ?? null;
    $b = $grafo["nodos"][sendero_nodo_key($sendero["destino_tipo"], $sendero["destino_id"])] ?? null;
    if (!$a || !$b) {
        return [];
    }
    $poly = [[(int)$a["x"], (int)$a["y"]]];
    foreach ($sendero["puntos"] as $p) {
        $poly[] = [(int)$p[0], (int)$p[1]];
    }
    $poly[] = [(int)$b["x"], (int)$b["y"]];
    return $poly;
}

/** Longitud (px) de la polilínea de un sendero. */
function sendero_distancia(array $grafo, array $sendero): float
{
    $poly = sendero_polilinea($grafo, $sendero);
    $d = 0.0;
    for ($i = 0; $i < count($poly) - 1; $i++) {
        $dx = $poly[$i + 1][0] - $poly[$i][0];
        $dy = $poly[$i + 1][1] - $poly[$i][1];
        $d += sqrt($dx * $dx + $dy * $dy);
    }
    return $d;
}

/**
 * Camino más corto entre dos nodos (Dijkstra por longitud de sendero).
 * @return array|null lista de senderos en orden, o null si no hay camino.
 */
function camino_entre_nodos(array $grafo, string $desde, string $hasta): ?array
{
    if (!isset($grafo["ady"][$desde]) || !isset($grafo["ady"][$hasta])) {
        return null;
    }
    if ($desde === $hasta) {
        return [];
    }

    $dist = [$desde => 0.0];
    $prev = [];
    $visitados = [];
    $cola = [[0.0, $desde]];

    while ($cola) {
        usort($cola, function ($x, $y) { return $x[0] <=> $y[0]; });
        [$d, $u] = array_shift($cola);
        if (isset($visitados[$u])) {
            continue;
        }
        $visitados[$u] = true;
        if ($u === $hasta) {
            break;
        }
        foreach ($grafo["ady"][$u] as $arista) {
            $v = $arista["nodo"];
            $w = sendero_distancia($grafo, $arista["sendero"]);
            $nd = $d + $w;
            if (!isset($dist[$v]) || $nd < $dist[$v]) {
                $dist[$v] = $nd;
                $prev[$v] = ["desde" => $u, "sendero" => $arista["sendero"]];
                $cola[] = [$nd, $v];
            }
        }
    }

    if (!isset($visitados[$hasta])) {
        return null;
    }

    $senderos = [];
    $cur = $hasta;
    while (isset($prev[$cur])) {
        array_unshift($senderos, $prev[$cur]["sendero"]);
        $cur = $prev[$cur]["desde"];
    }
    return $senderos;
}

/**
 * Nodo representativo de una cámara en el grafo:
 *  - cámara SIN líneas y colocada -> nodo-cámara (su x/y).
 *  - cámara CON líneas -> su primera línea colocada en el plano (nodo-línea).
 *  - si no procede -> null.
 * @return array|null ["tipo", "ref_id", "x", "y"]
 */
function nodo_representante_camara(int $cam_id): ?array
{
    $cam = DB::selectOne(
        "SELECT id, x, y, colocada,
                (SELECT COUNT(*) FROM lineas l WHERE l.camara_id = camaras.id AND l.eliminada = 0) AS num_lineas
         FROM camaras WHERE id = ?",
        [(int)$cam_id]
    );
    if (!$cam) {
        return null;
    }
    if ((int)$cam["num_lineas"] === 0) {
        if ((int)$cam["colocada"] !== 1) {
            return null;
        }
        return [
            "tipo"   => "camara",
            "ref_id" => (int)$cam["id"],
            "x"      => (int)$cam["x"],
            "y"      => (int)$cam["y"],
        ];
    }
    $lp = DB::selectOne(
        "SELECT lp.id, lp.x1, lp.y1, lp.x2, lp.y2
         FROM lineas_plano lp
         JOIN lineas l ON l.id = lp.linea_id
         WHERE l.camara_id = ? AND lp.eliminada = 0
         ORDER BY lp.id ASC LIMIT 1",
        [(int)$cam_id]
    );
    if (!$lp) {
        return null;
    }
    return [
        "tipo"   => "linea_plano",
        "ref_id" => (int)$lp["id"],
        "x"      => (int)round(((int)$lp["x1"] + (int)$lp["x2"]) / 2),
        "y"      => (int)round(((int)$lp["y1"] + (int)$lp["y2"]) / 2),
    ];
}

/**
 * Puntos intermedios entre dos cámaras siguiendo el grafo de senderos.
 * Devuelve los puntos INTERMEDIOS (sin los extremos de las cámaras), listos
 * para el player de Caminos. Si no hay camino por senderos, devuelve [].
 *
 * @return array [[x,y], ...]
 */
function senderos_puntos_entre_camaras(array $grafo, int $cam_a, int $cam_b): array
{
    $nA = nodo_representante_camara($cam_a);
    $nB = nodo_representante_camara($cam_b);
    if (!$nA || !$nB) {
        return [];
    }
    $keyA = sendero_nodo_key($nA["tipo"], $nA["ref_id"]);
    $keyB = sendero_nodo_key($nB["tipo"], $nB["ref_id"]);
    $senderos = camino_entre_nodos($grafo, $keyA, $keyB);
    if ($senderos === null || $senderos === []) {
        return [];
    }

    // Aplanar las polilíneas de los senderos del camino y deduplicar.
    $flat = [];
    foreach ($senderos as $s) {
        foreach (sendero_polilinea($grafo, $s) as $p) {
            $flat[] = $p;
        }
    }
    $dedup = [];
    foreach ($flat as $p) {
        $last = end($dedup);
        if ($last === false || $last[0] !== $p[0] || $last[1] !== $p[1]) {
            $dedup[] = $p;
        }
    }
    // Quitar extremos (nodo origen y nodo destino, que ya son las cámaras/nodos).
    if (count($dedup) > 2) {
        array_shift($dedup);
        array_pop($dedup);
    } else {
        return [];
    }
    return $dedup;
}
