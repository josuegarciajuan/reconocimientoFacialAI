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
require_once("libs/alarmas.php");

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

    case "listado_fotos_persona":
        // Barrido de fotos cruzadas (motor/detectar_fotos_cruzadas.py): por cada
        // foto del local, la persona asignada en BD (vía estancia) + cod_interno.
        // Solo lectura; JSON. Uso: php ws.php listado_fotos_persona <local_id>
        $local_id = (string) arg(2);
        $rows = DB::select(
            "SELECT f.id AS foto_id, e.persona_id, p.cod_interno, e.camara_id
             FROM fotos f
             JOIN estancias e ON e.id = f.estancia_id
             JOIN personas p ON p.id = e.persona_id
             WHERE p.local_id = ?
             ORDER BY f.id",
            [$local_id]
        );
        echo json_encode($rows);
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

    case "guardar_video":
        // argv: local_id, camara_id, nombre, ruta, fecha_ini, fecha_fin, duracion, peso, fps, ancho, alto [, poster]
        // Idempotente: si el MP4 ya está registrado (misma cámara + nombre) se devuelve su id
        // sin insertar de nuevo. Evita duplicados en `videos` cuando archiva_video.py se
        // reintenta (marcador limpiado como huérfano y relanzado con el mismo origen).
        $ya = DB::selectOne(
            "SELECT id FROM videos WHERE camara_id = ? AND nombre = ?",
            [(int) arg(3), (string) arg(4)]
        );
        if ($ya) {
            echo (string) (int) $ya["id"];
            exit;
        }
        $video_id = DB::insert(
            "INSERT INTO videos (local_id, camara_id, nombre, ruta, fecha_ini, fecha_fin, duracion, peso, fps, ancho, alto, poster)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(int) arg(2), (int) arg(3), (string) arg(4), (string) arg(5),
             (string) arg(6), (string) arg(7), (float) arg(8), (int) arg(9),
             (float) arg(10), (int) arg(11), (int) arg(12), (string) (arg(13) ?? "")]
        );
        echo $video_id;
        exit;

    case "video_info":
        // devuelve la fila de `videos` (JSON) por id
        $v = DB::selectOne("SELECT * FROM videos WHERE id = ?", [(int) arg(2)]);
        echo json_encode($v);
        exit;

    case "camaras_activas":
        // Cámaras encendidas (sistema=0) para vigilar la deriva (motor/vigilar_deriva.py).
        // Solo id + descripción + url_conexion (necesaria para capturar); nunca se loguea.
        $local_id_f = (int) arg(2);
        if ($local_id_f > 0) {
            $valores = DB::select(
                "SELECT id, descripcion, url_conexion FROM camaras WHERE sistema = 0 AND encendida = 1 AND local_id = ? ORDER BY id ASC",
                [$local_id_f]
            );
        } else {
            $valores = DB::select(
                "SELECT id, descripcion, url_conexion FROM camaras WHERE sistema = 0 AND encendida = 1 ORDER BY id ASC"
            );
        }
        echo json_encode($valores);
        exit;

    case "listado_videos":
        // argv: local_id [camara_id] [desde] [hasta] [limite]
        $v_where = ["local_id = ?"];
        $v_params = [(int) arg(2)];
        $cam_f = (int) (arg(3) ?? 0);
        if ($cam_f > 0) { $v_where[] = "camara_id = ?"; $v_params[] = $cam_f; }
        $desde_f = (string) (arg(4) ?? "");
        if ($desde_f !== "") { $v_where[] = "fecha_ini >= ?"; $v_params[] = $desde_f; }
        $hasta_f = (string) (arg(5) ?? "");
        if ($hasta_f !== "") { $v_where[] = "fecha_ini <= ?"; $v_params[] = $hasta_f; }
        $limite = min(500, max(1, (int) (arg(6) ?? 200)));
        $videos = DB::select(
            "SELECT * FROM videos WHERE " . implode(" AND ", $v_where) . " ORDER BY fecha_ini DESC LIMIT " . $limite,
            $v_params
        );
        echo json_encode($videos);
        exit;

    case "listado_videos_antiguos":
        // argv: dias  -> filas (id, ruta, poster) más antiguas que N días (para purgar)
        $dias = max(1, (int) arg(2));
        $rows = DB::select(
            "SELECT id, ruta, poster FROM videos WHERE fecha_ini < (NOW() - INTERVAL ? DAY) ORDER BY fecha_ini ASC LIMIT 500",
            [$dias]
        );
        echo json_encode($rows);
        exit;

    case "borrar_videos":
        // argv: id1,id2,...  -> borra las filas de `videos` indicadas (los ficheros los borra el llamante)
        $ids = [];
        foreach (explode(",", (string) (arg(2) ?? "")) as $id_raw) {
            $id_v = (int) trim($id_raw);
            if ($id_v > 0) { $ids[] = $id_v; }
        }
        if (!$ids) {
            echo "0";
            break;
        }
        $marks = implode(",", array_fill(0, count($ids), "?"));
        $n = DB::execute("DELETE FROM videos WHERE id IN (" . $marks . ")", $ids);
        echo (string) $n;
        break;

    case "alarma_estado":
        // Estado de vigilancia de una cámara (lo consulta guarda_movimientosV3.py).
        // Params: local_id, camara_id (HTTP GET o CLI argv) -> {"ok":bool,"armada":bool,"boost":bool}
        $estado = alarma_estado(
            (int)($_GET["local_id"] ?? arg(2) ?? 0),
            (int)($_GET["camara_id"] ?? arg(3) ?? 0)
        );
        echo json_encode($estado);
        exit;

    case "alarma_disparar":
        // Dispara una alarma (movimiento detectado estando armado).
        // Params: local_id, camara_id (HTTP GET o CLI argv) -> {"ok":bool,"id":int,"nueva":bool,"escalada":bool}
        $disparo = alarma_disparar(
            (int)($_GET["local_id"] ?? arg(2) ?? 0),
            (int)($_GET["camara_id"] ?? arg(3) ?? 0)
        );
        echo json_encode($disparo);
        exit;

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
