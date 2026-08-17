<?php

/* 
 * Lógica de rutas — libs/rutas.php
 * Funciones puras (reciben la conexión como parámetro) para construir la cadena de
 * estancias de una persona. Reutilizable y testeable (Fase 3; Fase 4 lo migrará a PDO).
 */

require_once __DIR__ . "/fechas.php";

/** Cámaras de entrada (puerta) y salida de un local. */
function camaras_puerta_salida($sql, $local_id) {
    $puerta = [];
    $salida = [];
    $sql->Consultar("camaras", "id", "local_id=" . intval($local_id) . " and puerta=1", "id asc");
    if ($sql->num > 0) {
        do { $puerta[] = $sql->row["id"]; } while ($sql->Siguiente());
    }
    $sql->Consultar("camaras", "id", "local_id=" . intval($local_id) . " and salida=1", "id asc");
    if ($sql->num > 0) {
        do { $salida[] = $sql->row["id"]; } while ($sql->Siguiente());
    }
    return [$puerta, $salida];
}

/** Nodos ordenados entre dos cámaras (array de [x, y]); [] si no hay. */
function nodos_entre($tmp, $cam_a, $cam_b) {
    $pts = [];
    $tmp->Consultar("nodos", "x,y",
        "(camara_id1=" . intval($cam_a) . " and camara_id2=" . intval($cam_b) . ") or (camara_id1=" . intval($cam_b) . " and camara_id2=" . intval($cam_a) . ")",
        "orden asc");
    if ($tmp->num > 0) {
        do { $pts[] = [(int)$tmp->row["x"], (int)$tmp->row["y"]]; } while ($tmp->Siguiente());
    }
    return $pts;
}

/** Construye la cadena de estancias (ruta) a partir de una estancia de entrada. */
function construye_ruta($tmp, $tmp2, $entrada, $camaras_salida) {
    $inicio_id = $entrada["id"];
    $persona_id = $entrada["persona_id"];
    $fecha_ini = $entrada["fecha_ini"];
    $fin = $entrada["fecha_fin"];

    $tmp->Consultar("personas", "nombre,cod_interno", "id=" . intval($persona_id));
    if ($tmp->num > 0) {
        $nombre = ($tmp->row["nombre"] !== "") ? $tmp->row["nombre"] : $tmp->row["cod_interno"];
    } else {
        $nombre = (string)$persona_id;
    }

    $tmp->Consultar("fotos", "min(id) as mind", "estancia_id=" . intval($inicio_id));
    $imagen = "./caras_procesadas/" . (($tmp->num > 0 && $tmp->row["mind"]) ? $tmp->row["mind"] : 0) . ".jpg";

    $puntos = [];
    $ids = [$inicio_id];

    $tmp2->Consultar("camaras", "id,descripcion,x,y", "id=" . intval($entrada["camara_id"]));
    if ($tmp2->num > 0) {
        $puntos[] = [
            "fecha" => $fecha_ini,
            "camara_id" => $tmp2->row["id"],
            "x" => $tmp2->row["x"],
            "y" => $tmp2->row["y"],
            "desc" => $tmp2->row["descripcion"],
        ];
    }

    $esta_dentro = true;
    $tmp->Consultar("estancias", "*",
        "fecha_ini>='" . $fecha_ini . "' and persona_id=" . intval($persona_id) . " and id<>" . intval($inicio_id),
        "fecha_ini asc");
    if ($tmp->num > 0) {
        do {
            $ids[] = $tmp->row["id"];
            $tmp2->Consultar("camaras", "id,descripcion,x,y", "id=" . intval($tmp->row["camara_id"]));
            if ($tmp2->num > 0) {
                $puntos[] = [
                    "fecha" => $tmp->row["fecha_ini"],
                    "camara_id" => $tmp2->row["id"],
                    "x" => $tmp2->row["x"],
                    "y" => $tmp2->row["y"],
                    "desc" => $tmp2->row["descripcion"],
                ];
                if (in_array($tmp2->row["id"], $camaras_salida)) {
                    $esta_dentro = false;
                }
            }
            $fin = $tmp->row["fecha_fin"];
        } while ($tmp->Siguiente() && $esta_dentro);
    }

    $segmentos = [];
    for ($i = 0; $i < count($puntos) - 1; $i++) {
        $segmentos[] = nodos_entre($tmp, $puntos[$i]["camara_id"], $puntos[$i + 1]["camara_id"]);
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
function obtener_rutas($sql, $tmp, $tmp2, $local_id, $desde_sql, $hasta_sql, $persona_filtro) {
    list($camaras_puerta, $camaras_salida) = camaras_puerta_salida($sql, $local_id);

    $rutas_data = [];
    if (count($camaras_puerta) === 0) {
        return [$rutas_data, count($camaras_puerta)];
    }

    $where = "camara_id IN (" . implode(",", $camaras_puerta) . ") and fecha_ini>='" . $desde_sql . "' and fecha_ini<='" . $hasta_sql . "'" . $persona_filtro;
    $sql->Consultar("estancias", "*", $where, "fecha_ini asc", false);
    $estancias_procesadas = [];
    if ($sql->num > 0) {
        do {
            $entrada = $sql->row;
            if (in_array($entrada["id"], $estancias_procesadas)) {
                continue;
            }
            $ruta = construye_ruta($tmp, $tmp2, $entrada, $camaras_salida);
            $rutas_data[] = $ruta;
            foreach ($ruta["ids"] as $eid) {
                $estancias_procesadas[] = $eid;
            }
        } while ($sql->Siguiente());
    }

    return [$rutas_data, count($camaras_puerta)];
}
