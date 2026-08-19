<?php

/* 
 * Lógica pura de nodos (sin BD) — libs/nodos.php.
 * Agrupa y ordena las cadenas de nodos entre dos cámaras, corrigiendo el sentido.
 *
 * Contexto: los nodos se guardan en el orden en que se marcaron desde la cámara
 * "camara_id1" hacia "camara_id2" (orden ASC = camara_id1 → camara_id2). Si al
 * reconstruir una ruta la persona recorrió el par en sentido contrario (camara_id2
 * → camara_id1), hay que INVERTIR la cadena; si no, el trazado hace zigzag.
 *
 * Además, un mismo par de cámaras puede tener varios caminos reales (p. ej. los dos
 * arcos de un pasillo en anillo), distinguidos por la columna `camino`.
 */

/**
 * Agrupa filas de nodos en cadenas listas para dibujar desde $cam_a.
 *
 * Entrada: array de filas con claves [camara_id1, camino, x, y], ya ordenadas
 *          por camino ASC, orden ASC (como las devuelve nodos_caminos_entre()).
 * Salida:  [ ["camino" => int, "nodos" => [[x,y],...]], ... ]
 *          Cada cadena queda orientada de $cam_a hacia la otra cámara.
 *
 * @param array $rows  Filas de la tabla nodos.
 * @param int   $cam_a Id de la cámara de origen del recorrido.
 * @return array
 */
function ordenar_cadenas_nodos(array $rows, int $cam_a): array
{
    $cadenas = [];
    foreach ($rows as $r) {
        $camino = (int)$r["camino"];
        if (!isset($cadenas[$camino])) {
            $cadenas[$camino] = [
                "camino" => $camino,
                "nodos"  => [],
                "dir"    => (int)$r["camara_id1"],
            ];
        }
        $cadenas[$camino]["nodos"][] = [(int)$r["x"], (int)$r["y"]];
    }

    $out = [];
    foreach ($cadenas as $camino => $c) {
        // Si la cadena se guardó en sentido contrario al recorrido, se invierte.
        if ($c["dir"] !== $cam_a) {
            $c["nodos"] = array_reverse($c["nodos"]);
        }
        $out[] = ["camino" => $camino, "nodos" => $c["nodos"]];
    }
    return $out;
}
