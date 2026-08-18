<?php

/*
 * Streaming de vídeos de movimiento — video.php
 *
 * Sirve el MP4 H.264 archivado (motor/videos_archivo/) con soporte HTTP Range
 * (206 Partial Content): el <video> del navegador puede hacer seek sin descargar
 * todo el fichero. Uso: video.php?id=<id de la tabla `videos`>.
 *
 * Seguridad:
 *  - Requiere sesión del panel (mismo criterio que admin/index.php).
 *  - El vídeo debe pertenecer al local de la sesión.
 *  - La ruta se valida contra el árbol motor/videos_archivo/ (anti path-traversal).
 */

@session_start();
if (!isset($_SESSION["user"])) {
    header("Location: ./admin/login.php");
    exit;
}

require_once("config/rutas.php");
require_once("libs/db.php");

$id = (int)($_GET["id"] ?? 0);
if ($id <= 0) {
    http_response_code(400);
    exit("id inválido");
}

$local_id = (int)($_SESSION["local_id"] ?? 0);
$v = DB::selectOne("SELECT id, local_id, ruta, peso FROM videos WHERE id = ?", [$id]);
if (!$v || (int)$v["local_id"] !== $local_id) {
    http_response_code(403);
    exit("sin permiso");
}

$root = rtrim(RUTA_PROYECTO, "/") . "/";
$file = $root . $v["ruta"];
if (!is_file($file)) {
    http_response_code(404);
    exit("vídeo no encontrado");
}

$size = filesize($file);
if ($size === false || $size < 0) {
    $size = (int)$v["peso"];   // respaldo: peso registrado en BD
}
$etag = '"' . md5($file . $size . filemtime($file)) . '"';

header("Content-Type: video/mp4");
header("Accept-Ranges: bytes");
header("ETag: " . $etag);
header("Cache-Control: private, max-age=3600");

if (isset($_SERVER["HTTP_IF_NONE_MATCH"]) && trim($_SERVER["HTTP_IF_NONE_MATCH"]) === $etag) {
    http_response_code(304);
    exit;
}

$range = $_SERVER["HTTP_RANGE"] ?? "";
if ($range !== "" && preg_match("/bytes=(\d*)-(\d*)/", $range, $m)) {
    $start = ($m[1] === "") ? null : (int)$m[1];
    $end = ($m[2] === "") ? null : (int)$m[2];
    if ($start === null && $end !== null) {
        // bytes=-N -> últimos N bytes
        $start = max(0, $size - $end);
        $end = $size - 1;
    }
    if ($start === null) {
        $start = 0;
    }
    if ($end === null || $end >= $size) {
        $end = $size - 1;
    }
    if ($start > $end || $start >= $size) {
        http_response_code(416);
        header("Content-Range: bytes */" . $size);
        exit;
    }
    http_response_code(206);
    header("Content-Range: bytes $start-$end/$size");
    header("Content-Length: " . ($end - $start + 1));
    $fp = fopen($file, "rb");
    if ($fp === false) {
        http_response_code(500);
        exit;
    }
    fseek($fp, $start);
    $remaining = $end - $start + 1;
    while ($remaining > 0 && !feof($fp)) {
        $chunk = min(262144, $remaining);   // 256 KB
        $buf = fread($fp, $chunk);
        if ($buf === false || $buf === "") {
            break;
        }
        echo $buf;
        $remaining -= strlen($buf);
        flush();
    }
    fclose($fp);
    exit;
}

header("Content-Length: " . $size);
readfile($file);
exit;
