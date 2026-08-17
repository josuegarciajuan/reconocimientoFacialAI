<?php

/* 
 * Rutas — AJAX (REFACTOR Fase 3).
 * Eliminado a=1 (referenciaba la tabla `accesos`/`usuarios`, que ya no existe).
 * a=2 devuelve nodos entre dos cámaras (paréntesis explícitos en el OR).
 */

require_once '../../../config/rutas.php';
require_once '../../../libs/mysql.class.php';

$sql = new Conectar();

switch ($_GET["a"]) {
    case "2":
        $camara_id1 = intval($_GET["camara_id1"]);
        $camara_id2 = intval($_GET["camara_id2"]);
        $return = [];
        $sql->Consultar(
            'nodos', 'x,y',
            "(camara_id1=" . $camara_id1 . " and camara_id2=" . $camara_id2 . ") or (camara_id1=" . $camara_id2 . " and camara_id2=" . $camara_id1 . ")",
            "orden asc"
        );
        if ($sql->num > 0) {
            do {
                $return[] = $sql->row["x"] . "," . $sql->row["y"];
            } while ($sql->Siguiente());
        }
        echo implode(";;;", $return);
        break;

    default:
        break;
}

$sql->Desconectar();
