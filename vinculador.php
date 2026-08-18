<?php

/*
 * vinculador.php — daemon (p7) de vínculos automáticos vídeos ↔ estancias ↔ cruces.
 * Consume libs/vinculos.php y escribe en:
 *   - estancias.video_id
 *   - cruces_lineas.video_id
 *   - cruces_lineas.persona_id
 *
 * Ciclo (cada CONFIG_VINCULADOR_LOOP segundos, def. 60):
 *   - 1ª vez por local => backfill completo (videos, estancias y cruces históricos).
 *   - Incremental      => estancias/cruces huérfanos + vídeos de las últimas 24 h.
 *   - Log de candidatos a re-estudio (vídeos sin NINGUNA estancia: movimiento sin
 *     cara reconocible; el re-análisis del MP4 es opcional y manual).
 *
 * Despliegue: systemd rf-vinculador (deploy/systemd/rf-vinculador.service).
 * Logs: stdout -> journalctl -u rf-vinculador -f.
 */

require_once("config/rutas.php");
require_once("libs/db.php");
require_once("libs/vinculos.php");

$loop = max(1, (int)CONFIG_VINCULADOR_LOOP);
$backfill_dias = (int)CONFIG_VINCULADOR_BACKFILL_DIAS;
$margen = (int)CONFIG_VINCULO_MARGEN_SEGS;

while (true) {
    $locales = DB::select("SELECT id FROM locales ORDER BY id ASC");
    foreach ($locales as $l) {
        $local_id = (int)$l["id"];

        // Backfill histórico solo si el local aún no tiene ningún vínculo hecho.
        $n = DB::selectOne(
            "SELECT COUNT(*) AS n FROM estancias e
             JOIN camaras c ON c.id = e.camara_id
             WHERE c.local_id = ? AND e.video_id IS NOT NULL",
            [$local_id]
        );
        if ($n && (int)$n["n"] === 0) {
            $n_vid = DB::selectOne("SELECT COUNT(*) AS n FROM videos WHERE local_id = ?", [$local_id]);
            if ($n_vid && (int)$n_vid["n"] > 0) {
                vincular_backfill_local($local_id, $margen);
            }
        }

        vincular_incremental_local($local_id, $margen);
    }
    sleep($loop);
}

/**
 * Pasada completa de vínculos para un local (1ª vez; idempotente).
 */
function vincular_backfill_local(int $local_id, int $margen): void {
    $t = microtime(true);
    $tot = ["estancias" => 0, "cruces" => 0, "personas" => 0];

    $videos = DB::select(
        "SELECT id, camara_id, fecha_ini, fecha_fin FROM videos WHERE local_id = ? ORDER BY fecha_ini ASC",
        [$local_id]
    );
    foreach ($videos as $v) {
        $r = vinculos_vincular_video($v, $margen);
        $tot["estancias"] += $r["estancias"];
        $tot["cruces"] += $r["cruces"];
        $tot["personas"] += $r["personas"];
    }

    // estancias huérfanas (el vídeo se archivó después que la estancia)
    $estancias = DB::select(
        "SELECT e.id, e.camara_id, e.fecha_ini, e.fecha_fin FROM estancias e
         JOIN camaras c ON c.id = e.camara_id
         WHERE c.local_id = ? AND e.video_id IS NULL",
        [$local_id]
    );
    foreach ($estancias as $e) {
        if (vinculos_vincular_estancia($e, $margen) !== null) {
            $tot["estancias"]++;
        }
    }

    // cruces huérfanos
    $cruces = DB::select(
        "SELECT cl.id, cl.linea_id, cl.fecha, cl.video_id, l.camara_id FROM cruces_lineas cl
         JOIN lineas l ON l.id = cl.linea_id
         JOIN camaras c ON c.id = l.camara_id
         WHERE c.local_id = ? AND cl.video_id IS NULL",
        [$local_id]
    );
    foreach ($cruces as $cr) {
        $r = vinculos_vincular_cruce($cr, $margen);
        if ($r["video_id"]) { $tot["cruces"]++; }
        if ($r["persona_id"]) { $tot["personas"]++; }
    }

    // cruces con vídeo pero sin persona todavía
    $tot["personas"] += vincular_cruces_sin_persona($local_id, $margen);

    printf(
        "[backfill] local %d: %d estancias, %d cruces, %d personas (%d ms)\n",
        $local_id, $tot["estancias"], $tot["cruces"], $tot["personas"], (int)((microtime(true) - $t) * 1000)
    );
}

/**
 * Pasada incremental: estancias/cruces huérfanos recientes + vídeos de las últimas 24 h.
 */
function vincular_incremental_local(int $local_id, int $margen): void {
    $tot = ["estancias" => 0, "cruces" => 0, "personas" => 0];

    $estancias = DB::select(
        "SELECT e.id, e.camara_id, e.fecha_ini, e.fecha_fin FROM estancias e
         JOIN camaras c ON c.id = e.camara_id
         WHERE c.local_id = ? AND e.video_id IS NULL
           AND e.fecha_ini >= DATE_SUB(NOW(), INTERVAL 30 DAY)
         ORDER BY e.id DESC LIMIT 100",
        [$local_id]
    );
    foreach ($estancias as $e) {
        if (vinculos_vincular_estancia($e, $margen) !== null) {
            $tot["estancias"]++;
        }
    }

    $cruces = DB::select(
        "SELECT cl.id, cl.linea_id, cl.fecha, cl.video_id, l.camara_id FROM cruces_lineas cl
         JOIN lineas l ON l.id = cl.linea_id
         JOIN camaras c ON c.id = l.camara_id
         WHERE c.local_id = ? AND cl.video_id IS NULL
           AND cl.fecha >= DATE_SUB(NOW(), INTERVAL 30 DAY)
         ORDER BY cl.id DESC LIMIT 100",
        [$local_id]
    );
    foreach ($cruces as $cr) {
        $r = vinculos_vincular_cruce($cr, $margen);
        if ($r["video_id"]) { $tot["cruces"]++; }
        if ($r["persona_id"]) { $tot["personas"]++; }
    }

    // vídeos de las últimas 24 h: enlazan sus estancias y cruces (idempotente)
    $videos = DB::select(
        "SELECT id, camara_id, fecha_ini, fecha_fin FROM videos
         WHERE local_id = ? AND fecha_ini >= DATE_SUB(NOW(), INTERVAL 1 DAY)
         ORDER BY fecha_ini ASC",
        [$local_id]
    );
    foreach ($videos as $v) {
        $r = vinculos_vincular_video($v, $margen);
        $tot["estancias"] += $r["estancias"];
        $tot["cruces"] += $r["cruces"];
        $tot["personas"] += $r["personas"];
    }

    $tot["personas"] += vincular_cruces_sin_persona($local_id, $margen);

    if (array_sum($tot) > 0) {
        printf(
            "[incremental] local %d: +%d estancias, +%d cruces, +%d personas\n",
            $local_id, $tot["estancias"], $tot["cruces"], $tot["personas"]
        );
    }

    // candidatos a re-estudio (solo informativo)
    $sin_estancia = vinculos_videos_sin_estancia($local_id, $margen, 7, 5);
    if ($sin_estancia) {
        $ids = implode(",", array_column($sin_estancia, "id"));
        printf("[reestudio] local %d: %d vídeo(s) sin estancia (id: %s)\n", $local_id, count($sin_estancia), $ids);
    }
}

/**
 * Cruces ya enlazados a vídeo pero sin persona atribuida.
 * @return int nº de cruces con persona asignada
 */
function vincular_cruces_sin_persona(int $local_id, int $margen): int {
    $cruces = DB::select(
        "SELECT cl.id, cl.fecha, cl.video_id, l.camara_id FROM cruces_lineas cl
         JOIN lineas l ON l.id = cl.linea_id
         JOIN camaras c ON c.id = l.camara_id
         WHERE c.local_id = ? AND cl.video_id IS NOT NULL AND cl.persona_id IS NULL
         ORDER BY cl.id DESC LIMIT 100",
        [$local_id]
    );
    $n = 0;
    foreach ($cruces as $cr) {
        if (vinculos_cruce_a_persona((int)$cr["id"], (int)$cr["camara_id"], (int)$cr["video_id"], (string)$cr["fecha"], $margen) !== null) {
            $n++;
        }
    }
    return $n;
}
