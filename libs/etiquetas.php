<?php

/*
 * libs/etiquetas.php — Etiquetas y enlaces de entidades (personas, cámaras).
 *
 * Unifica la presentación de una persona en TODA la UI:
 *   - persona_label():  si tiene nombre se muestra el nombre, si no el código interno,
 *                       y si no hay nada, el id (fallback). Evita la concatenación
 *                       heredada "codigo - nombre" que duplicaba la información.
 *   - persona_url()/camara_url(): destinos de enlace de cada entidad.
 *   - persona_link()/camara_link(): enlaces HTML ya escapados (deep-link a la
 *                       ficha de la persona / a la vista en vivo de la cámara).
 *
 * Funciones puras: no dependen de sesión ni de DB, solo de sus argumentos.
 */

/** Etiqueta única de una persona: nombre si existe, si no código interno. */
function persona_label($nombre, $cod_interno, $fallback = "")
{
    $nombre     = (string)$nombre;
    $cod_interno = (string)$cod_interno;
    if ($nombre !== "") {
        return $nombre;
    }
    if ($cod_interno !== "") {
        return $cod_interno;
    }
    return (string)$fallback;
}

/** URL de la ficha de una persona. */
function persona_url($persona_id)
{
    return "?page=visitantes&mode=editar&id=" . (int)$persona_id;
}

/** URL de la vista en vivo de una cámara (abre el modal automáticamente). */
function camara_url($camara_id)
{
    return "?page=camaras&id=" . (int)$camara_id;
}

/**
 * Etiqueta de cámara: antepone el prefijo "cam_" para que el nombre no se
 * confunda con nombres de trabajadores (las cámaras están sobre los puestos).
 * Idempotente: si la descripción ya empieza por "cam", se deja tal cual.
 */
function camara_label($descripcion, $camara_id = 0)
{
    $d = (string)$descripcion;
    $t = trim($d);
    if ($t === "" || $t === "—" || $t === "-") {
        return $d !== "" ? $d : ($camara_id > 0 ? "cam_" . (int)$camara_id : "");
    }
    if (stripos($d, "cam") === 0) {
        return $d;
    }
    return "cam_" . $d;
}

/**
 * Enlace a la ficha de una persona.
 * @param string $label  Texto ya unificado (persona_label) o null para usar $cod_interno.
 */
function persona_link($persona_id, $label = null, $cod_interno = "", $title = "Ver la ficha de la persona")
{
    $pid = (int)$persona_id;
    if ($pid <= 0) {
        return htmlspecialchars((string)($label ?? ""), ENT_QUOTES);
    }
    if ($label === null) {
        $label = persona_label("", $cod_interno, (string)$pid);
    }
    return '<a class="text-theme-1 font-medium hover:underline" href="' . persona_url($pid)
        . '" title="' . htmlspecialchars($title, ENT_QUOTES) . '">'
        . htmlspecialchars((string)$label, ENT_QUOTES) . '</a>';
}

/**
 * Enlace a la vista en vivo de una cámara.
 * @param string $label  Texto a mostrar (típicamente la descripción de la cámara).
 */
function camara_link($camara_id, $label = null, $title = "Ver la cámara en vivo")
{
    $cid = (int)$camara_id;
    if ($label === null) {
        $label = $cid > 0 ? "cam_" . $cid : "";
    }
    $label = camara_label($label, $cid);
    if ($cid <= 0) {
        return htmlspecialchars($label, ENT_QUOTES);
    }
    return '<a class="text-theme-1 font-medium hover:underline" href="' . camara_url($cid)
        . '" title="' . htmlspecialchars($title, ENT_QUOTES) . '">'
        . htmlspecialchars($label, ENT_QUOTES) . '</a>';
}
