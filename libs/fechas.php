<?php

/* 
 * Helpers de fecha compartidos (fix B13: conversión 12h->24h rota).
 * Se usa desde los listados (rutas, lineas, visitantes, fichajes, accesos).
 */

/**
 * Convierte el formato de los inputs datepicker "n/d hh:mm AM|PM" a "Y-m-d H:i:s".
 * Si la cadena está vacía o malformada, devuelve $defecto.
 */
function rango_a_sql($str, $defecto) {
    if ($str === null || trim((string)$str) === "") {
        return $defecto;
    }
    $partes = explode(" ", trim((string)$str));
    if (count($partes) < 2) {
        return $defecto;
    }
    $fecha = explode("/", $partes[0]);
    $hora = explode(":", $partes[1]);
    if (count($fecha) < 2 || count($hora) < 2) {
        return $defecto;
    }
    $mes = (int)$fecha[0];
    $dia = (int)$fecha[1];
    $h = (int)$hora[0];
    $m = (int)$hora[1];
    $ampm = isset($partes[2]) ? strtoupper(trim($partes[2])) : "";
    if ($ampm === "PM" && $h < 12) {
        $h += 12;
    } elseif ($ampm === "AM" && $h === 12) {
        $h = 0;
    }
    $anio = (int)date("Y");
    return sprintf("%04d-%02d-%02d %02d:%02d:00", $anio, $mes, $dia, $h, $m);
}

/**
 * Duración legible a partir de segundos.
 */
function formato_duracion($s) {
    $s = (int)$s;
    if ($s < 0) {
        $s = 0;
    }
    if ($s < 60) {
        return $s . "s";
    }
    $m = intdiv($s, 60);
    $sec = $s % 60;
    if ($m < 60) {
        return $m . "m y " . $sec . "s";
    }
    $h = intdiv($m, 60);
    $m = $m % 60;
    return $h . "h y " . $m . "m y " . $sec . "s";
}
