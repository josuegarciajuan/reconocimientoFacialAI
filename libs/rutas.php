<?php

/* 
 * Lógica de rutas — libs/rutas.php (REFACTOR Fase 4b: PDO).
 * Funciones puras sobre PDO (DB) para construir la cadena de estancias de una persona.
 */

require_once __DIR__ . "/fechas.php";
require_once __DIR__ . "/db.php";
require_once __DIR__ . "/nodos.php";
require_once __DIR__ . "/avatars.php";

/** Cámaras de entrada (puerta) y salida de un local. */
function camaras_puerta_salida($local_id) {
    $puerta = array_column(DB::select("SELECT id FROM camaras WHERE local_id = ? AND puerta = 1", [$local_id]), "id");
    $salida = array_column(DB::select("SELECT id FROM camaras WHERE local_id = ? AND salida = 1", [$local_id]), "id");
    return [$puerta, $salida];
}

/**
 * Posteres de vídeo por video_id (para los botones Ver del player).
 * @return array [video_id => poster_relativo]
 */
function rutas_posteres(array $video_ids): array {
    $video_ids = array_values(array_unique(array_filter(array_map("intval", $video_ids))));
    if (!$video_ids) {
        return [];
    }
    $in = implode(",", array_fill(0, count($video_ids), "?"));
    $filas = DB::select("SELECT id, poster FROM videos WHERE id IN ($in)", $video_ids);
    $out = [];
    foreach ($filas as $f) {
        $out[(int)$f["id"]] = (string)$f["poster"];
    }
    return $out;
}

/** URL relativa del avatar de una persona (o ""). */
function rutas_avatar_url(int $persona_id): string {
    return avatar_url($persona_id);
}

/**
 * Cadenas de nodos entre dos cámaras, agrupadas por camino y orientadas en el
 * sentido del recorrido (corrige el zigzag al recorrer el par al revés).
 * Devuelve [ ["camino" => int, "nodos" => [[x,y],...]], ... ]; [] si no hay.
 */
function nodos_caminos_entre($cam_a, $cam_b) {
    $rows = DB::select(
        "SELECT camara_id1, camino, x, y FROM nodos
         WHERE (camara_id1 = ? AND camara_id2 = ?) OR (camara_id1 = ? AND camara_id2 = ?)
         ORDER BY camino ASC, orden ASC",
        [$cam_a, $cam_b, $cam_b, $cam_a]
    );
    return ordenar_cadenas_nodos($rows, (int)$cam_a);
}

/** Nodos del camino principal entre dos cámaras (array de [x, y]); [] si no hay. */
function nodos_entre($cam_a, $cam_b) {
    $cadenas = nodos_caminos_entre($cam_a, $cam_b);
    return $cadenas ? $cadenas[0]["nodos"] : [];
}

/** Construye la cadena de estancias (ruta) a partir de una estancia de entrada. */
function construye_ruta($entrada, $camaras_salida) {
    $inicio_id = (int)$entrada["id"];
    $persona_id = (int)$entrada["persona_id"];
    $fecha_ini = $entrada["fecha_ini"];
    $fin = $entrada["fecha_fin"];

    $pers = DB::selectOne("SELECT nombre, cod_interno FROM personas WHERE id = ?", [$persona_id]);
    $nombre = ($pers && $pers["nombre"] !== "") ? $pers["nombre"] : ($pers ? $pers["cod_interno"] : $persona_id);

    $foto = DB::selectOne("SELECT MIN(id) AS fid FROM fotos WHERE estancia_id = ?", [$inicio_id]);
    $imagen = "./caras_procesadas/" . ($foto && $foto["fid"] ? $foto["fid"] : 0) . ".jpg";

    $puntos = [];
    $ids = [$inicio_id];

    $cam = DB::selectOne("SELECT id, descripcion, x, y FROM camaras WHERE id = ?", [(int)$entrada["camara_id"]]);
    if ($cam) {
        $puntos[] = [
            "fecha"      => $fecha_ini,
            "t"          => (int)strtotime($fecha_ini),
            "camara_id"  => $cam["id"],
            "x"          => $cam["x"],
            "y"          => $cam["y"],
            "desc"       => $cam["descripcion"],
            "estancia_id"=> $inicio_id,
            "video_id"   => (int)($entrada["video_id"] ?? 0),
        ];
    }

    $esta_dentro = true;
    $siguientes = DB::select(
        "SELECT * FROM estancias WHERE fecha_ini >= ? AND persona_id = ? AND id <> ? ORDER BY fecha_ini ASC",
        [$fecha_ini, $persona_id, $inicio_id]
    );
    foreach ($siguientes as $e) {
        $ids[] = (int)$e["id"];
        $cam2 = DB::selectOne("SELECT id, descripcion, x, y FROM camaras WHERE id = ?", [(int)$e["camara_id"]]);
        if ($cam2) {
            $puntos[] = [
                "fecha"      => $e["fecha_ini"],
                "t"          => (int)strtotime($e["fecha_ini"]),
                "camara_id"  => $cam2["id"],
                "x"          => $cam2["x"],
                "y"          => $cam2["y"],
                "desc"       => $cam2["descripcion"],
                "estancia_id"=> (int)$e["id"],
                "video_id"   => (int)($e["video_id"] ?? 0),
            ];
            if (in_array((int)$cam2["id"], $camaras_salida)) {
                $esta_dentro = false;
            }
        }
        $fin = $e["fecha_fin"];
        if (!$esta_dentro) {
            break;
        }
    }

    // Posteres de los vídeos de los pasos (para el botón Ver del player).
    $video_ids = array_column($puntos, "video_id");
    $posteres = rutas_posteres($video_ids);
    foreach ($puntos as &$p) {
        $p["poster"] = $posteres[(int)$p["video_id"]] ?? "";
    }
    unset($p);

    $segmentos = [];
    for ($i = 0; $i < count($puntos) - 1; $i++) {
        $segmentos[] = nodos_caminos_entre((int)$puntos[$i]["camara_id"], (int)$puntos[$i + 1]["camara_id"]);
    }

    if ($esta_dentro) {
        $tiempo = "Dentro " . formato_duracion(strtotime(date("Y-m-d H:i:s")) - strtotime($fecha_ini));
    } else {
        $tiempo = formato_duracion(strtotime($fin) - strtotime($fecha_ini));
    }

    return [
        "inicio_id" => $inicio_id,
        "persona_id" => $persona_id,
        "nombre" => $nombre,
        "imagen" => $imagen,
        "inicio" => $fecha_ini,
        "fin" => $esta_dentro ? date("Y-m-d H:i:s") : $fin,
        "num_camaras" => count($puntos),
        "tiempo" => $tiempo,
        "esta_dentro" => $esta_dentro,
        "puntos" => $puntos,
        "segmentos" => $segmentos,
        "ids" => $ids,
    ];
}

/** Obtiene todas las rutas del local para el rango de fechas y filtro. */
function obtener_rutas($local_id, $desde_sql, $hasta_sql, $persona_filtro) {
    list($camaras_puerta, $camaras_salida) = camaras_puerta_salida($local_id);
    $rutas_data = [];

    if (count($camaras_puerta) === 0) {
        return [$rutas_data, 0];
    }

    $params = [$desde_sql, $hasta_sql];
    $where = "camara_id IN (" . implode(",", $camaras_puerta) . ") AND fecha_ini >= ? AND fecha_ini <= ?" . $persona_filtro;
    $entradas = DB::select("SELECT * FROM estancias WHERE " . $where . " ORDER BY fecha_ini ASC", $params);

    $estancias_procesadas = [];
    foreach ($entradas as $entrada) {
        if (in_array((int)$entrada["id"], $estancias_procesadas)) {
            continue;
        }
        $ruta = construye_ruta($entrada, $camaras_salida);
        $rutas_data[] = $ruta;
        foreach ($ruta["ids"] as $eid) {
            $estancias_procesadas[] = (int)$eid;
        }
    }

    return [$rutas_data, count($camaras_puerta)];
}

/**
 * Una sola ruta completa a partir de su estancia de entrada (para el player).
 * @return array|null la ruta (construye_ruta) o null si no existe/pertenece al local.
 */
function obtener_ruta($local_id, $inicio_id) {
    $inicio_id = (int)$inicio_id;
    if ($inicio_id <= 0) {
        return null;
    }
    $entrada = DB::selectOne(
        "SELECT e.* FROM estancias e
         JOIN camaras c ON c.id = e.camara_id
         WHERE e.id = ? AND c.local_id = ?",
        [$inicio_id, (int)$local_id]
    );
    if (!$entrada) {
        return null;
    }
    list($camaras_puerta, $camaras_salida) = camaras_puerta_salida($local_id);
    return construye_ruta($entrada, $camaras_salida);
}
