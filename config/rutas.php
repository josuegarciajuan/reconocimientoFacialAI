<?php

/* 
 * Config de rutas y credenciales por entorno.
 * REFACTOR Fase 0 (2026-08-17):
 *  - Entorno "server" = máquina actual (hostname liveyourdre2). RUTA_PYTHON apunta al venv aislado.
 *  - Default por defecto a "server" (B21: antes quedaba indefinido si el hostname no estaba mapeado).
 *  - NOTA (M10): credenciales reales deben ir a .env en Fase 5. Las de entornos legacy
 *    (oficina/localhost) se purgan en la Fase 5.
 */


$entornos=[
    "liveyourdre2" => "server",
    "camjump"      => "server",   // legacy (webdock antiguo), se mantiene mapeado
    "oficina"      => "oficina",
];
$host= gethostname();

$server="server"; // default: si el hostname no está mapeado, usamos "server" (antes: indefinido)
foreach($entornos as $nombre=>$entorno){
    if($host==$nombre){
        $server=$entorno;
        break;
    }
}

/* M10: credenciales desde .env (fuera de git). Si no existe .env, se usan los valores por defecto. */
$env_file = __DIR__ . "/../.env";
if (is_file($env_file)) {
    foreach (file($env_file, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) as $linea) {
        $linea = trim($linea);
        if ($linea === "" || $linea[0] === "#" || strpos($linea, "=") === false) {
            continue;
        }
        list($k, $v) = explode("=", $linea, 2);
        if (getenv($k) === false) {
            putenv($k . "=" . trim($v));
        }
    }
}
if (!function_exists("env_or")) {
    function env_or($k, $d) {
        $v = getenv($k);
        return ($v === false || $v === "") ? $d : $v;
    }
}

switch($server){
    case "server":
        /* Entorno actual: /root/reconocimientoFacial (Ubuntu 22.04, PHP 8.4, MariaDB, venv Python 3.10) */
        define("URL_PROGRAMA_SERVER", env_or("RF_URL", "http://localhost/reconocimientoFacial/"));

        define('BD_BBDD', env_or('RF_DB_NAME', 'reconocimientofacial'));
        define('BD_USUARIO', env_or('RF_DB_USER', 'root'));
        define('BD_PASS', env_or('RF_DB_PASS', ''));
        define('BD_HOST', env_or('RF_DB_HOST', 'localhost'));
        define('PREFIJO_TABLAS', '');

        define('RUTA_PROYECTO', env_or('RF_RUTA', "/root/reconocimientoFacial/"));
        define("RUTA_PHP","php");
        define("RUTA_PYTHON", env_or('RF_PYTHON', "/root/reconocimientoFacial/motor/venv/bin/python"));  // venv aislado (R6)

        define("URL_BASE_SERVER", env_or('RF_URL', "http://localhost/reconocimientoFacial/"));

        // FTP legacy (M12): pendiente de sustituir por transferencia local/pysftp en Fase 2
        define("FTP_SERVER", env_or('RF_FTP_HOST', "localhost"));
        define("FTP_USER", env_or('RF_FTP_USER', ""));
        define("FTP_PASS", env_or('RF_FTP_PASS', ""));
        break;


    case "oficina":
        /* ENTORNO LEGACY — sin mantenimiento; credenciales obsoletas */
        define("URL_PROGRAMA_SERVER","http://localhost/reconocimientofacialV2/");

        define('BD_BBDD', 'reconocimientofacial');
        define('BD_USUARIO', 'newuser');
        define('BD_PASS', 'prueba123@4522gwrQWWERw');   // LEGACY — mover a .env o purgar (M10)
        define('BD_HOST', 'localhost');
        define('PREFIJO_TABLAS', '');

        define('RUTA_PROYECTO', "/var/www/html/reconocimientofacialV2/");
        define("RUTA_PHP","php");
        define("RUTA_PYTHON","/root/reconocimientoFacial/motor/venv/bin/python");

        define("URL_BASE_SERVER","http://localhost/reconocimientofacialV2/");
        define("FTP_SERVER","localhost");
        define("FTP_USER","");
        define("FTP_PASS","");
        break;

    default:
        die("Entorno no soportado: ".$server);
}

// Credenciales del superadmin (M10: desde .env). Por defecto: cambiar-ahora.
define("ADMIN_USER", env_or("RF_ADMIN_USER", "admin"));
define("ADMIN_PASS_HASH", password_hash(env_or("RF_ADMIN_PASS", "cambiar-ahora"), PASSWORD_DEFAULT));

// Auto-login por dispositivo (matrícula única): habilitado, IP de matrícula y cookie.
// Ver libs/autologin.php y la migración sql/2026-08-18-dispositivos-autologin.sql.
define("AUTOLOGIN_ENABLED", env_or("RF_AUTOLOGIN_ENABLED", "0") === "1");
define("AUTOLOGIN_IP", env_or("RF_AUTOLOGIN_IP", ""));
define("AUTOLOGIN_COOKIE", env_or("RF_AUTOLOGIN_COOKIE", "rf_autologin"));

require_once(__DIR__ . "/config.php");
