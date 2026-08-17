<?php

/* 
 * Webservice — ws.php (REFACTOR Fase 4a).
 * Acceso a BD con PDO + prepared statements (B9). Contrato compatible con el motor.
 * Se llama por CLI (`php ws.php <accion> [args...]`) o HTTP GET (`?accion=...&...`).
 */

error_reporting(0);
ini_set('display_errors', '0');

require_once("config/rutas.php");
require_once("libs/db.php");

// acción desde GET o argv[1]
$accion = $_GET["accion"] ?? ($argv[1] ?? "");

function arg($i) {
    global $argv;
    return $argv[$i] ?? null;
}

$return = ["cod" => "200", "resp" => "", "valores" => ""];

switch ($accion) {
    case "consultar":
        // solo lo usa capturador.php (tabla=camaras). Whitelist + condición parametrizada.
        $tabla = $_GET["tabla"] ?? "";
        $condicion = urldecode($_GET["condicion"] ?? "");
        $orden = urldecode($_GET["orden"] ?? "id asc");

        $tablas_ok = ["camaras", "locales", "lineas", "personas", "estancias", "fotos", "nodos", "cruces_lineas"];
        if (!in_array($tabla, $tablas_ok, true)) {
            $return["cod"] = "400";
            $return["resp"] = "Tabla no permitida";
            break;
        }
        list($where, $params) = parse_condicion($condicion);
        if ($where === false) {
            $return["cod"] = "400";
            $return["resp"] = "Condición no permitida";
            break;
        }
        if (!preg_match('/^[a-zA-Z_][a-zA-Z0-9_]*(\.`?[a-zA-Z_][a-zA-Z0-9_]*`?)?(\s+(asc|desc))?(\s*,\s*[a-zA-Z_][a-zA-Z0-9_]*(\s+(asc|desc))?)*$/', $orden)) {
            $return["cod"] = "400";
            $return["resp"] = "Orden no permitido";
            break;
        }
        $valores = DB::select("SELECT * FROM `$tabla`" . $where . " ORDER BY " . $orden, $params);
        $return["cod"] = "200";
        $return["valores"] = $valores;
        if (!$valores) {
            $return["resp"] = "No hay datos consultados";
        }
        break;

    case "nombreunico":
    case "fotos_identificadorunico":
        // código único de 25 caracteres
        echo generar_codigo_unico($accion === "nombreunico" ? "personas" : "fotos",
                                  $accion === "nombreunico" ? "cod_interno" : "identificador_unico");
        exit;

    case "listado_lineas":
        $camara_id = (int) arg(2);
        $ids = array_column(DB::select("SELECT id FROM lineas WHERE camara_id = ?", [$camara_id]), "id");
        echo implode(",", $ids);
        exit;

    case "coordenadas_linea":
        $linea_id = (int) arg(2);
        $l = DB::selectOne("SELECT x1, y1, x2, y2 FROM lineas WHERE id = ?", [$linea_id]);
        if ($l) {
            echo $l["x1"] . "," . $l["y1"] . "," . $l["x2"] . "," . $l["y2"];
        }
        exit;

    case "lineas_identificadorunico":
        echo generar_codigo_unico("cruces_lineas", "identificador");
        exit;

    case "guarda_cruce":
        $linea_id = (int) arg(2);
        $fecha = (string) arg(3);
        $direccion = (int) arg(4);
        $x_cruce = (int) arg(5);
        $y_cruce = (int) arg(6);
        $identificador = (string) arg(7);
        DB::insert("INSERT INTO cruces_lineas (linea_id, fecha, direccion, x_cruce, y_cruce, identificador) VALUES (?, ?, ?, ?, ?, ?)",
                   [$linea_id, $fecha, $direccion, $x_cruce, $y_cruce, $identificador]);
        break;

    default:
        $return["cod"] = "200";
        $return["resp"] = "La accion solicitada no puede ser procesada";
        break;
}

if ($accion === "consultar") {
    echo json_encode($return);
}

/**
 * Parsea una condición tipo "col=valor and col=valor" a (SQL parametrizado, params).
 * Devuelve [false, []] si no es válida. Solo `=` y `and`, columnas [a-zA-Z_][a-zA-Z0-9_]*,
 * valores numéricos o cadenas entre comillas simples.
 */
function parse_condicion($cond) {
    $sql = [];
    $params = [];
    $parts = preg_split('/\s+and\s+/i', trim($cond));
    foreach ($parts as $p) {
        $p = trim($p);
        if ($p === "") {
            continue;
        }
        if (!preg_match('/^([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(.+)$/', $p, $m)) {
            return [false, []];
        }
        $col = $m[1];
        $val = trim($m[2]);
        if (preg_match('/^-?\d+(\.\d+)?$/', $val)) {
            $sql[] = "`$col` = ?";
            $params[] = $val + 0;
        } elseif (preg_match("/^'([^']*)'$/", $val, $q)) {
            $sql[] = "`$col` = ?";
            $params[] = $q[1];
        } else {
            return [false, []];
        }
    }
    if (!$sql) {
        return [" WHERE 1=0", []];  // sin condición -> sin filas (evita SELECT * completo)
    }
    return [" WHERE " . implode(" AND ", $sql), $params];
}

/** Código alfanumérico único de 25 chars para la tabla/columna indicados. */
function generar_codigo_unico($tabla, $columna) {
    $alfabeto = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
    do {
        $codigo = "";
        for ($i = 0; $i < 25; $i++) {
            $codigo .= $alfabeto[random_int(0, 61)];
        }
        $existe = DB::selectOne("SELECT 1 FROM `$tabla` WHERE `$columna` = ? LIMIT 1", [$codigo]);
    } while ($existe !== null);
    return $codigo;
}
