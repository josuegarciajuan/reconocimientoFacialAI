<?php

/*
 * conciliador.php — daemon (p6) de conciliación de fichajes con horario.
 * Consume libs/conciliador.php y escribe en la tabla `fichajes`.
 *
 * Ciclo (cada CONFIG_CONCILIADOR_LOOP segundos, def. 60):
 *   - Hoy            => fichajes provisionales (la salida se actualiza en vivo).
 *   - Ayer (+días abiertos anteriores) => conciliados (salida definitiva).
 *   - 1ª vez por local => backfill de CONFIG_CONCILIADOR_BACKFILL_DIAS días.
 *
 * Despliegue: systemd rf-conciliador (deploy/systemd/rf-conciliador.service).
 * Logs: stdout -> journalctl -u rf-conciliador -f.
 */

require_once("config/rutas.php");
require_once("libs/db.php");
require_once("libs/conciliador.php");

$loop = max(1, (int)CONFIG_CONCILIADOR_LOOP);
$backfill_dias = (int)CONFIG_CONCILIADOR_BACKFILL_DIAS;

while (true) {
    $locales = DB::select("SELECT id FROM locales ORDER BY id ASC");
    foreach ($locales as $l) {
        $local_id = (int)$l["id"];

        // Backfill histórico solo si el local aún no tiene ningún fichaje.
        $n = DB::selectOne("SELECT COUNT(*) AS n FROM fichajes WHERE local_id = ?", [$local_id]);
        if ($n && (int)$n["n"] === 0) {
            for ($i = $backfill_dias; $i >= 1; $i--) {
                conciliar_local_dia($local_id, date("Y-m-d", strtotime("-" . $i . " day")), true);
            }
        }

        // Días abiertos anteriores (p. ej. tras un corte del servicio) => cerrar.
        $abiertos = DB::select(
            "SELECT DISTINCT fecha FROM fichajes
             WHERE local_id = ? AND estado = 'provisional' AND fecha < ?",
            [$local_id, date("Y-m-d")]
        );
        foreach ($abiertos as $a) {
            conciliar_local_dia($local_id, $a["fecha"], true);
        }

        // Ayer cerrado + hoy provisional.
        conciliar_local_dia($local_id, date("Y-m-d", strtotime("-1 day")), true);
        conciliar_local_dia($local_id, date("Y-m-d"), false);
    }
    sleep($loop);
}

/**
 * Concilia todos los trabajadores del local con actividad de puerta en $fecha.
 */
function conciliar_local_dia(int $local_id, string $fecha, bool $finalizado): void {
    $fin = date("Y-m-d H:i:s", strtotime($fecha . " +1 day"));
    $personas = DB::select(
        "SELECT DISTINCT e.persona_id
         FROM estancias e
         JOIN camaras c ON c.id = e.camara_id
         JOIN personas p ON p.id = e.persona_id
         WHERE c.local_id = ? AND p.trabajador = 1
           AND (c.puerta = 1 OR c.salida = 1)
           AND e.fecha_ini >= ? AND e.fecha_ini < ?",
        [$local_id, $fecha . " 00:00:00", $fin]
    );
    foreach ($personas as $p) {
        conciliar_dia($local_id, (int)$p["persona_id"], $fecha, $finalizado);
    }
}
