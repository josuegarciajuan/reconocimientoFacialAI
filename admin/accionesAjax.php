<?php

/* 
 * AJAX global del panel — admin/accionesAjax.php (REFACTOR Fase 4a).
 * PDO + prepared statements (B9). Esquema actual: estancias/personas (antes accesos/usuarios).
 * Fix B11: marcar notificación usaba local_id en vez del id de la estancia.
 */

@session_start();
require_once '../config/rutas.php';
require_once '../libs/db.php';
require_once './pages/dashboard/widgets.php';

$local_id = (int)($_SESSION["local_id"] ?? 0);

switch ($_GET["a"]) {
    case "4": // dashboard: fragmentos en vivo (feed + dentro + falta)
        header("Content-Type: application/json; charset=utf-8");
        $dentro = dash_almas_dentro($local_id);
        $falta  = dash_falta_fichar($local_id);
        echo json_encode([
            "ok"          => true,
            "feed"        => dash_feed_html($local_id, 10),
            "dentro"      => dash_dentro_html($local_id),
            "falta"       => dash_falta_html($local_id),
            "dentro_count"=> count($dentro),
            "falta_count" => count($falta),
            "updated"     => "hace un momento",
        ], JSON_UNESCAPED_UNICODE);
        break;

    case "5": // dashboard: estado de los daemons
        header("Content-Type: application/json; charset=utf-8");
        echo json_encode(["ok" => true, "html" => dash_daemons_html()], JSON_UNESCAPED_UNICODE);
        break;

    case "6": // dashboard: fijar el aforo actual sin recargar
        header("Content-Type: application/json; charset=utf-8");
        $nuevo = (int)($_GET["nuevo_aforo"] ?? -1);
        $loc = DB::selectOne("SELECT aforo_max FROM locales WHERE id = ?", [$local_id]);
        $max = (int)($loc["aforo_max"] ?? 0);
        if ($nuevo < 0) {
            echo json_encode(["ok" => false, "error" => "valor inválido"]);
            break;
        }
        if ($max > 0 && $nuevo > $max) { $nuevo = $max; }
        DB::execute("UPDATE locales SET aforo_actual = ? WHERE id = ?", [$nuevo, $local_id]);
        $a = dash_aforo($local_id);
        $sem_txt = $a["estado"] === "full"
            ? "🔴 Asedio · " . $a["pct"] . "%"
            : ($a["estado"] === "warn" ? "🟡 Animado · " . $a["pct"] . "%" : "🟢 Tranquilo · " . $a["pct"] . "%");
        echo json_encode([
            "ok" => true, "actual" => $a["actual"], "max" => $a["max"],
            "pct" => $a["pct"], "estado" => $a["estado"], "sem_txt" => $sem_txt,
        ], JSON_UNESCAPED_UNICODE);
        break;

    case "1": // notificaciones sin ver
        $return = "false";
        $rows = DB::select(
            "SELECT e.id, e.camara_id, e.created, p.cod_interno, p.nombre, c.descripcion, c.puerta, c.salida
             FROM estancias e
             JOIN personas p ON p.id = e.persona_id
             JOIN camaras c ON c.id = e.camara_id
             WHERE c.local_id = ? AND e.notificacion_vista = 0
             ORDER BY e.id DESC LIMIT 5",
            [$local_id]
        );
        if ($rows) {
            $return = "truee###";
            foreach ($rows as $r) {
                $nombre = $r["nombre"] !== "" ? $r["nombre"] : $r["cod_interno"];
                $mode = "-";
                if ((int)$r["puerta"] === 1) {
                    $mode = "Entrada al local por " . $r["descripcion"];
                } elseif ((int)$r["salida"] === 1) {
                    $mode = "Salida del local por " . $r["descripcion"];
                }
                $foto = DB::selectOne("SELECT MIN(id) as mid FROM fotos WHERE estancia_id = ?", [(int)$r["id"]]);
                $img = "./caras_procesadas/" . ($foto && $foto["mid"] ? $foto["mid"] : 0) . ".jpg";
                $return .= $r["cod_interno"] . " - (" . $nombre . ")///" . $r["descripcion"] . "///" . $mode . "///" . $img . "///" . $img . "///" . $r["created"] . "###";
            }
        }
        echo $return;
        break;

    case "2": // marcar notificaciones como leídas
        DB::execute(
            "UPDATE estancias e JOIN camaras c ON c.id = e.camara_id
             SET e.notificacion_vista = 1 WHERE c.local_id = ? AND e.notificacion_vista = 0",
            [$local_id]
        );
        break;

    case "3": // series para el gráfico
        $labels = "";
        $datos1 = "";
        $datos2 = "";
        $filtro = $_GET["filtro"] ?? "dia";

        switch ($filtro) {
            case "dia":
                $labels = implode(",", array_map(fn($i) => str_pad($i, 2, "0", STR_PAD_LEFT), range(0, 23)));
                for ($i = 0; $i <= 23; $i++) {
                    $h1 = str_pad($i, 2, "0", STR_PAD_LEFT);
                    $h2 = str_pad($i + 1, 2, "0", STR_PAD_LEFT);
                    $datos1 .= cuenta_entradas($local_id, date("Y-m-d $h1:00:00"), date("Y-m-d $h2:00:00"));
                    $datos2 .= cuenta_entradas($local_id, date("Y-m-d $h1:00:00", strtotime("-1 days")), date("Y-m-d $h2:00:00", strtotime("-1 days")));
                    if ($i < 23) { $datos1 .= ","; $datos2 .= ","; }
                }
                break;

            case "semana":
                $labels = "lun,mar,mie,jue,vie,sab,dom";
                $dias = ["monday","tuesday","wednesday","thursday","friday","saturday","sunday"];
                for ($i = 1; $i <= 7; $i++) {
                    $dia = $dias[$i - 1];
                    $datos1 .= cuenta_entradas($local_id, date("Y-m-d 00:00:00", strtotime("$dia this week")), date("Y-m-d 23:59:59", strtotime("$dia this week")));
                    $datos2 .= cuenta_entradas($local_id, date("Y-m-d 00:00:00", strtotime("$dia last week")), date("Y-m-d 23:59:59", strtotime("$dia last week")));
                    if ($i < 7) { $datos1 .= ","; $datos2 .= ","; }
                }
                break;

            case "mes":
                for ($i = 1; $i <= 31; $i++) {
                    $label = str_pad($i, 2, "0", STR_PAD_LEFT);
                    $labels .= $label;
                    $datos1 .= cuenta_entradas($local_id, date("Y-m-$label 00:00:00"), date("Y-m-$label 23:59:59"));
                    $datos2 .= cuenta_entradas($local_id, date("Y-m-$label 00:00:00", strtotime("-1 month")), date("Y-m-$label 23:59:59", strtotime("-1 month")));
                    if ($i < 31) { $datos1 .= ","; $datos2 .= ","; $labels .= ","; }
                }
                break;

            case "anyo":
                $labels = "Ene,Feb,Mar,Abr,May,Jun,Jul,Ago,Sep,Oct,Nov,Dic";
                $meses = ["January","February","March","April","May","June","July","August","September","October","November","December"];
                for ($i = 1; $i <= 12; $i++) {
                    $label = str_pad($i, 2, "0", STR_PAD_LEFT);
                    $datos1 .= cuenta_entradas($local_id, date("Y-$label-01 00:00:00"), date("Y-$label-01 23:59:59"));
                    $datos2 .= cuenta_entradas($local_id, date("Y-$label-01 00:00:00", strtotime("-1 year")), date("Y-$label-01 23:59:59", strtotime("-1 year")));
                    if ($i < 12) { $datos1 .= ","; $datos2 .= ","; }
                }
                break;
        }

        echo $labels . "---" . $datos1 . "---" . $datos2;
        break;
}

/** Nº de personas distintas que entraron (cámara puerta) en el rango. */
function cuenta_entradas($local_id, $desde, $hasta) {
    $r = DB::selectOne(
        "SELECT COUNT(DISTINCT e.persona_id) AS cuenta
         FROM estancias e
         JOIN camaras c ON c.id = e.camara_id
         JOIN personas p ON p.id = e.persona_id
         WHERE p.trabajador = 0 AND c.puerta = 1 AND c.local_id = ? AND e.created >= ? AND e.created < ?",
        [$local_id, $desde, $hasta]
    );
    return $r ? (int)$r["cuenta"] : 0;
}
