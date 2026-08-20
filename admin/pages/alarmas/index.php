<?php

/*
 * La Almenara — Sistema de alarmas de inactividad.
 * Sub-vistas: listar (alarmas) / config (teléfonos de recepción).
 * Los horarios de inactividad se configuran en los formularios de local y cámara
 * (La Forja). Aquí se revisan las alarmas disparadas y los teléfonos de aviso.
 */

switch ($_GET["mode"] ?? "listar") {
    case "config":
        require_once __DIR__ . "/config.php";
        break;
    default:
        require_once __DIR__ . "/list.php";
        break;
}
