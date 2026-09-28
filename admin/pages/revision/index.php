<?php

/*
 * Revisión — router de la bandeja de caras dudosas (revision-only).
 *
 * mode: list (default). Se incluyen las acciones antes de pintar para que un
 * POST haga su trabajo y redirija (PRG) sin depender del orden del layout.
 */

include "acciones.php";

switch ($_GET["mode"] ?? "") {
    case "listar":
        include "list.php";
        break;
    default:
        include "list.php";
        break;
}

include "javascript.php";
