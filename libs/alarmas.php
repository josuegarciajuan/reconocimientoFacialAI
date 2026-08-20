<?php

/*
 * libs/alarmas.php — Sistema de alarmas de inactividad ("La Almenara").
 *
 * Modelo:
 *   - Ventana de inactividad por local (alarma_hora_inicio/fin, cruce de medianoche
 *     permitido) y por cámara (heredada por defecto).
 *   - Una cámara está "armada" si el local tiene la vigilancia activa, no hay
 *     "actividad 24h" (ni en local ni en cámara) y la hora actual cae en la ventana.
 *   - `alarma_estado()` es el endpoint que consultan los workers (guarda_movimientosV3.py)
 *     cada CONFIG_ALARMA_ESTADO_TTL segundos: {armada, boost}.
 *   - `alarma_disparar()` inserta el evento con cooldown: dentro del cooldown no se
 *     duplica, se refresca la ventana de asedio (boost) y, si hay actividad sostenida,
 *     se escala aviso -> asedio.
 *
 * Las horas de la ventana las interpreta SIEMPRE PHP (misma zona horaria del servidor
 * que la BD): el worker Python solo pregunta "¿estoy armado?".
 */

require_once __DIR__ . "/../config/rutas.php";
require_once __DIR__ . "/db.php";

/** "HH:MM" -> minutos desde medianoche (o null). */
function alarma_tiempo_min(?string $hora): ?int
{
    if ($hora === null || $hora === "") {
        return null;
    }
    $p = explode(":", (string)$hora);
    return ((int)($p[0] ?? 0) * 60) + (int)($p[1] ?? 0);
}

/**
 * ¿El minuto $t cae en la ventana [inicio, fin]? Admite cruce de medianoche
 * (inicio >= fin). $margen_min es la gracia tras el cierre (último en salir).
 */
function alarma_en_ventana(?string $inicio, ?string $fin, int $margen_min, int $t): bool
{
    $a = alarma_tiempo_min($inicio);
    $b = alarma_tiempo_min($fin);
    if ($a === null || $b === null) {
        return false;
    }
    $a += max(0, $margen_min);
    if ($a < $b) {
        return $t >= $a && $t < $b;
    }
    // cruce de medianoche (p. ej. 20:00 -> 07:00)
    return $t >= $a || $t < $b;
}

/**
 * Ventana de inactividad efectiva de una cámara (resuelve la herencia del local).
 * @return array{inicio: ?string, fin: ?string, margen: int}
 */
function alarma_ventana_efectiva(array $cam, ?array $local): array
{
    $heredar = (int)($cam["alarma_heredar"] ?? 1) === 1;
    $tiene_propia = ($cam["alarma_hora_inicio"] ?? "") !== "" && ($cam["alarma_hora_fin"] ?? "") !== "";
    if (!$heredar && $tiene_propia) {
        return [
            "inicio" => $cam["alarma_hora_inicio"],
            "fin"    => $cam["alarma_hora_fin"],
            "margen" => (int)($local["alarma_margen_min"] ?? 0),
        ];
    }
    if ($local === null) {
        return ["inicio" => null, "fin" => null, "margen" => 0];
    }
    return [
        "inicio" => $local["alarma_hora_inicio"] ?? null,
        "fin"    => $local["alarma_hora_fin"] ?? null,
        "margen" => (int)($local["alarma_margen_min"] ?? 0),
    ];
}

/**
 * Estado de vigilancia de una cámara (lo consulta el worker en tiempo real).
 * @return array{ok: bool, armada: bool, boost: bool}
 */
function alarma_estado(int $local_id, int $camara_id): array
{
    $cam = DB::selectOne("SELECT * FROM camaras WHERE id = ? AND local_id = ?", [$camara_id, $local_id]);
    if (!$cam) {
        return ["ok" => false, "armada" => false, "boost" => false];
    }
    $local = DB::selectOne("SELECT * FROM locales WHERE id = ?", [$local_id]);

    // Modo asedio: ¿sigue en vigor la ventana de boost?
    $boost = false;
    if ($local !== null && !empty($local["alarma_boost_hasta"])) {
        $bh = strtotime((string)$local["alarma_boost_hasta"]);
        if ($bh !== false && $bh > time()) {
            $boost = true;
        }
    }

    $armada = false;
    if ($local !== null && (int)($local["alarma_activa"] ?? 0) === 1) {
        $cam_24h   = (int)($cam["alarma_24h"] ?? 0) === 1;
        $local_24h = (int)($local["alarma_24h"] ?? 0) === 1;
        if (!$cam_24h && !$local_24h) {
            $ventana = alarma_ventana_efectiva($cam, $local);
            if ($ventana["inicio"] !== null && $ventana["fin"] !== null) {
                $t = ((int)date("G") * 60) + (int)date("i");
                $armada = alarma_en_ventana($ventana["inicio"], $ventana["fin"], $ventana["margen"], $t);
            }
        }
    }

    return ["ok" => true, "armada" => $armada, "boost" => $boost];
}

/**
 * Dispara una alarma (lo llama el worker al detectar movimiento estando armado).
 * Cooldown: si ya hay una alarma del local dentro de CONFIG_ALARMA_COOLDOWN_SEGS,
 * no se duplica: se refresca la ventana de asedio y se escala a "asedio" si la
 * actividad se sostiene (>= CONFIG_ALARMA_ESCALADA_EVENTOS eventos en la ventana).
 *
 * @return array{ok: bool, id: int, nueva: bool, escalada: bool, error?: string}
 */
function alarma_disparar(int $local_id, ?int $camara_id, string $origen = "camara"): array
{
    $local = DB::selectOne("SELECT * FROM locales WHERE id = ?", [$local_id]);
    if ($local === null || (int)($local["alarma_activa"] ?? 0) !== 1) {
        return ["ok" => false, "error" => "alarma inactiva", "id" => 0, "nueva" => false, "escalada" => false];
    }

    $cooldown  = max(1, (int)CONFIG_ALARMA_COOLDOWN_SEGS);
    $boost_seg = max(1, (int)CONFIG_ALARMA_BOOST_SEGS);
    $esc_ev    = max(1, (int)CONFIG_ALARMA_ESCALADA_EVENTOS);

    $camara_id = ($camara_id !== null && $camara_id > 0) ? (int)$camara_id : null;
    $cam = $camara_id ? DB::selectOne("SELECT descripcion FROM camaras WHERE id = ?", [$camara_id]) : null;

    $mensaje = "Movimiento en horario de inactividad";
    if ($cam !== null) {
        $mensaje .= " en " . (string)$cam["descripcion"];
    }

    $corte_cooldown = date("Y-m-d H:i:s", time() - $cooldown);
    $reciente = DB::selectOne(
        "SELECT id, severidad, eventos FROM alarmas
         WHERE local_id = ? AND fecha >= ? ORDER BY id DESC LIMIT 1",
        [$local_id, $corte_cooldown]
    );

    $hasta = date("Y-m-d H:i:s", time() + $boost_seg);

    if ($reciente) {
        // No duplicar: contar el evento y refrescar el modo asedio.
        $eventos = (int)($reciente["eventos"] ?? 1) + 1;
        $escalada = false;
        $nueva_sev = (string)$reciente["severidad"];
        if ($nueva_sev === "aviso" && $eventos >= $esc_ev) {
            $nueva_sev = "asedio";
            $escalada = true;
        }
        DB::execute(
            "UPDATE alarmas SET eventos = ?, severidad = ? WHERE id = ?",
            [$eventos, $nueva_sev, (int)$reciente["id"]]
        );
        DB::execute("UPDATE locales SET alarma_boost_hasta = ? WHERE id = ?", [$hasta, $local_id]);
        return ["ok" => true, "id" => (int)$reciente["id"], "nueva" => false, "escalada" => $escalada];
    }

    $id = DB::insert(
        "INSERT INTO alarmas (local_id, camara_id, fecha, severidad, eventos, origen, mensaje)
         VALUES (?, ?, NOW(), 'aviso', 1, ?, ?)",
        [$local_id, $camara_id, $origen, $mensaje]
    );
    DB::execute("UPDATE locales SET alarma_boost_hasta = ? WHERE id = ?", [$hasta, $local_id]);

    return ["ok" => true, "id" => (int)$id, "nueva" => true, "escalada" => false];
}

/**
 * Asocia a la alarma el vídeo de movimiento más cercano en el tiempo (misma
 * cámara, solape con margen). Devuelve el video_id asignado o null.
 */
function alarma_vincular_video(int $alarma_id, int $margen = 30): ?int
{
    $a = DB::selectOne(
        "SELECT id, local_id, camara_id, fecha FROM alarmas WHERE id = ? AND video_id IS NULL",
        [$alarma_id]
    );
    if (!$a || !$a["camara_id"]) {
        return null;
    }
    $t = strtotime((string)$a["fecha"]);
    if ($t === false) {
        return null;
    }
    $desde = date("Y-m-d H:i:s", $t - $margen);
    $hasta = date("Y-m-d H:i:s", $t + $margen);
    $v = DB::selectOne(
        "SELECT id FROM videos
         WHERE local_id = ? AND camara_id = ? AND fecha_ini <= ? AND (fecha_fin IS NULL OR fecha_fin >= ?)
         ORDER BY ABS(TIMESTAMPDIFF(SECOND, fecha_ini, ?)) ASC LIMIT 1",
        [(int)$a["local_id"], (int)$a["camara_id"], $hasta, $desde, $a["fecha"]]
    );
    if (!$v) {
        return null;
    }
    DB::execute("UPDATE alarmas SET video_id = ? WHERE id = ?", [(int)$v["id"], $alarma_id]);
    return (int)$v["id"];
}

/** Rellena video_id de todas las alarmas del local aún sin vídeo (llamado por el vinculador). */
function alarma_vincular_pendientes(int $local_id, int $margen = 30): int
{
    $pend = DB::select(
        "SELECT id FROM alarmas WHERE local_id = ? AND video_id IS NULL AND camara_id IS NOT NULL ORDER BY id ASC LIMIT 200",
        [$local_id]
    );
    $n = 0;
    foreach ($pend as $p) {
        if (alarma_vincular_video((int)$p["id"], $margen) !== null) {
            $n++;
        }
    }
    return $n;
}

/** Nº de alarmas no vistas del local (banner/badge de la UI). */
function alarma_no_vistas_count(int $local_id): int
{
    $r = DB::selectOne("SELECT COUNT(*) AS n FROM alarmas WHERE local_id = ? AND notificacion_vista = 0", [$local_id]);
    return $r ? (int)$r["n"] : 0;
}

/** Marca todas las alarmas del local como leídas. */
function alarma_marcar_leidas(int $local_id): void
{
    DB::execute("UPDATE alarmas SET notificacion_vista = 1 WHERE local_id = ? AND notificacion_vista = 0", [$local_id]);
}

/**
 * Listado de alarmas del local con la descripción de la cámara.
 * @return array<int, array>
 */
function alarma_listado(int $local_id, int $limite = 50): array
{
    $limite = max(1, min(500, $limite));
    return DB::select(
        "SELECT a.*, c.descripcion AS camara_desc
         FROM alarmas a
         LEFT JOIN camaras c ON c.id = a.camara_id
         WHERE a.local_id = ?
         ORDER BY a.id DESC LIMIT " . $limite,
        [$local_id]
    );
}

/** Resumen de una alarma para el digest "Ronda de la mañana" (alarmador.php). */
function alarma_resumen_rango(int $local_id, string $desde, string $hasta): array
{
    $rows = DB::select(
        "SELECT a.severidad, a.fecha, a.camara_id, c.descripcion AS camara_desc
         FROM alarmas a LEFT JOIN camaras c ON c.id = a.camara_id
         WHERE a.local_id = ? AND a.fecha >= ? AND a.fecha < ?
         ORDER BY a.id ASC",
        [$local_id, $desde, $hasta]
    );
    $n_aviso  = 0;
    $n_asedio = 0;
    foreach ($rows as $r) {
        if ((string)$r["severidad"] === "asedio") { $n_asedio++; } else { $n_aviso++; }
    }
    return ["total" => count($rows), "avisos" => $n_aviso, "asedios" => $n_asedio, "detalle" => $rows];
}
