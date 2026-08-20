<?php

/*
 * alarmador.php — daemon (p8) de "La Almenara" (sistema de alarmas).
 *
 * Ciclo (cada CONFIG_ALARMADOR_LOOP segundos, def. 60):
 *   - Refuerzo de vínculo vídeo↔alarma (idempotente; el vinculador también lo hace).
 *   - Despacho de alarmas nuevas por canales (hoy solo in-app = sin-op; WhatsApp
 *     se añadirá implementando CanalWhatsApp en libs/notificador.php).
 *   - "Ronda de la mañana": una vez al día (tras las 06:00) registra el resumen
 *     de alarmas de las últimas 24 h (base del futuro envío por WhatsApp).
 *
 * Despliegue: systemd rf-alarmador (deploy/systemd/rf-alarmador.service).
 * Logs: stdout -> journalctl -u rf-alarmador -f.
 */

require_once("config/rutas.php");
require_once("libs/db.php");
require_once("libs/alarmas.php");
require_once("libs/notificador.php");

$loop = max(1, (int)CONFIG_ALARMADOR_LOOP);
$margen = (int)CONFIG_VINCULO_MARGEN_SEGS;

$ultimo_id = [];      // último id de alarma despachado por local
$ultimo_digest = [];  // fecha del último digest "ronda de la mañana" por local

while (true) {
    $locales = DB::select("SELECT id FROM locales ORDER BY id ASC");
    foreach ($locales as $l) {
        $local_id = (int)$l["id"];

        // 1) Refuerzo de vínculos vídeo↔alarma (cubre alarmas sin vídeo previo)
        $n = alarma_vincular_pendientes($local_id, $margen);
        if ($n > 0) {
            printf("[vinculo] local %d: %d alarma(s) enlazada(s) a vídeo\n", $local_id, $n);
        }

        // 2) Despacho de alarmas nuevas por canales (in-app hoy; WhatsApp futuro)
        $desde = (int)($ultimo_id[$local_id] ?? 0);
        $nuevas = DB::select(
            "SELECT * FROM alarmas WHERE local_id = ? AND id > ? ORDER BY id ASC",
            [$local_id, $desde]
        );
        foreach ($nuevas as $al) {
            NotificadorAlarma::notificar($al, $local_id);
            $ultimo_id[$local_id] = (int)$al["id"];
        }
        if ($nuevas) {
            printf("[aviso] local %d: %d alarma(s) despachada(s) por canales\n", $local_id, count($nuevas));
        }

        // 3) Ronda de la mañana: una vez al día tras las 06:00
        $hoy = date("Y-m-d");
        if (($ultimo_digest[$local_id] ?? "") !== $hoy && (int)date("G") >= 6) {
            $desde = date("Y-m-d H:i:s", strtotime("-24 hours"));
            $r = alarma_resumen_rango($local_id, $desde, date("Y-m-d H:i:s"));
            if ($r["total"] > 0) {
                printf("[ronda] local %d: %d alarma(s) en 24 h (avisos %d, asedios %d)\n",
                    $local_id, $r["total"], $r["avisos"], $r["asedios"]);
            }
            $ultimo_digest[$local_id] = $hoy;
        }
    }
    sleep($loop);
}
