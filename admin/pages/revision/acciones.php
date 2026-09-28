<?php
if (session_status() !== PHP_SESSION_ACTIVE) @session_start();

/*
 * Revisión — acciones POST (aprobar / asignar / descartar).
 *
 * El trabajo pesado (galería face_enc_v2 + publicación en motor/caras) lo hace
 * `motor/revision.py`; aquí solo se valida, se invoca con escapeshellarg y,
 * para `aprobar --nombre`, se fija `personas.nombre` por `cod_interno` (el
 * daemon rf-clasificador crea la fila de forma asíncrona al ingerir la foto).
 */

require_once __DIR__ . "/../../../config/rutas.php";
require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/security.php";
require_once __DIR__ . "/../../../libs/revision.php";

$local_id = rf_require_local_session();

/**
 * Redirección PRG tolerante a que admin/index.php ya haya emitido el layout.
 *
 * En este panel las páginas se incluyen dentro del HTML (content.php), así que
 * `header()` puede fallar si el buffer ya se volcó. Si es el caso, se emite el
 * equivalente JS para no dejar la PRG a medias.
 */
function rf_revision_volver(): void
{
    $destino = "?page=revision";
    if (!headers_sent()) {
        header("Location: " . $destino);
    } else {
        echo '<script>window.location.replace(' . json_encode($destino) . ');</script>';
    }
    exit;
}

if (($_SERVER["REQUEST_METHOD"] ?? "") !== "POST") {
    return;
}

rf_require_csrf();

$action = (string)($_POST["action"] ?? "");
$cam = (string)($_POST["cam"] ?? "");
$file = (string)($_POST["file"] ?? "");

if (!rf_revision_componente_valido($cam)
    || !rf_revision_componente_valido($file)
    || !rf_revision_es_imagen($file)) {
    http_response_code(400);
    exit("Parámetros de revisión inválidos");
}

// RUTA_PROYECTO ya termina en "/": se concatena el script igual que en
// admin/pages/visitantes/acciones.php (patrón del repo).
$script = RUTA_PROYECTO . "motor/revision.py";
$salida = null;
$nombre = "";

if ($action === "descartar") {
    $cmd = RUTA_PYTHON . " " . $script . " descartar"
         . " " . escapeshellarg((string)$local_id)
         . " " . escapeshellarg($cam)
         . " " . escapeshellarg($file)
         . " --ruta " . RUTA_PROYECTO . " --json 2>&1";
    $salida = shell_exec($cmd);
    error_log("[revision][descartar] " . $cam . "/" . $file . " -> " . trim((string)$salida));

} elseif ($action === "aprobar") {
    $nombre = trim((string)($_POST["nombre"] ?? ""));
    if ($nombre !== "" && mb_strlen($nombre) > 120) {
        $nombre = mb_substr($nombre, 0, 120);
    }
    $cmd = RUTA_PYTHON . " " . $script . " aprobar"
         . " " . escapeshellarg((string)$local_id)
         . " " . escapeshellarg($cam)
         . " " . escapeshellarg($file)
         . " --ruta " . RUTA_PROYECTO . " --json 2>&1";
    if ($nombre !== "") {
        $cmd .= " --nombre " . escapeshellarg($nombre);
    }
    $salida = shell_exec($cmd);
    error_log("[revision][aprobar] " . $cam . "/" . $file . " -> " . trim((string)$salida));

} elseif ($action === "asignar") {
    $cod_destino = (string)($_POST["cod_destino"] ?? "");
    if (!rf_revision_componente_valido($cod_destino)) {
        http_response_code(400);
        exit("Persona destino inválida");
    }
    $cmd = RUTA_PYTHON . " " . $script . " asignar"
         . " " . escapeshellarg((string)$local_id)
         . " " . escapeshellarg($cam)
         . " " . escapeshellarg($file)
         . " " . escapeshellarg($cod_destino)
         . " --ruta " . RUTA_PROYECTO . " --json 2>&1";
    $salida = shell_exec($cmd);
    error_log("[revision][asignar] " . $cam . "/" . $file . " -> " . trim((string)$salida));
}

// Nombre opcional al aprobar: el daemon ingiere el JPEG de forma asíncrona
// (escaneo ~1 s), así que se sondea un instante antes de fijar el nombre.
if ($action === "aprobar" && $nombre !== "") {
    $res = rf_revision_json_ultimo((string)$salida);
    if (is_array($res) && !empty($res["ok"]) && !empty($res["cod"])) {
        $cod = (string)$res["cod"];
        $actualizado = false;
        for ($i = 0; $i < 12; $i++) {
            $p = DB::selectOne(
                "SELECT id FROM personas WHERE cod_interno = ? AND local_id = ? LIMIT 1",
                [$cod, $local_id]
            );
            if ($p) {
                DB::execute(
                    "UPDATE personas SET nombre = ? WHERE id = ? AND local_id = ?",
                    [$nombre, (int)$p["id"], $local_id]
                );
                $actualizado = true;
                break;
            }
            usleep(250000);
        }
        if (!$actualizado) {
            error_log("[revision][aprobar] no se pudo fijar el nombre '{$nombre}' a {$cod}: el daemon aún no ingirió la foto");
        }
    }
}

rf_revision_volver();
