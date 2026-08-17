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

switch($server){
    case "server":
        /* Entorno actual: /root/reconocimientoFacial (Ubuntu 22.04, PHP 8.4, MariaDB, venv Python 3.10) */
        define("URL_PROGRAMA_SERVER","http://localhost/reconocimientoFacial/");

        define('BD_BBDD', 'reconocimientofacial');
        define('BD_USUARIO', 'root');
        define('BD_PASS', '');          // root local sin password (MariaDB); mover a .env (M10)
        define('BD_HOST', 'localhost');
        define('PREFIJO_TABLAS', '');

        define('RUTA_PROYECTO', "/root/reconocimientoFacial/");
        define("RUTA_PHP","php");
        define("RUTA_PYTHON","/root/reconocimientoFacial/motor/venv/bin/python");  // venv aislado (R6)

        define("URL_BASE_SERVER","http://localhost/reconocimientoFacial/");

        // FTP legacy (M12): pendiente de sustituir por transferencia local/pysftp en Fase 2
        define("FTP_SERVER","localhost");
        define("FTP_USER","");
        define("FTP_PASS","");
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

require_once("config.php");
