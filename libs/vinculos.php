<?php

/*
 * libs/vinculos.php — Lógica de vínculos automáticos vídeos ↔ estancias (personas) ↔ cruces de línea.
 *
 * El daemon vinculador.php la consume y escribe en `estancias.video_id`,
 * `cruces_lineas.video_id` y `cruces_lineas.persona_id` (FK nullable: no siempre
 * es posible el vínculo mutuo).
 *
 * Por qué NO hace falta re-estudiar el vídeo
 * ------------------------------------------
 * Los tres artefactos comparten cámara + timestamp base porque derivan del mismo
 * fichero de movimiento:
 *   - `videos.fecha_ini/fecha_fin`   <- nombre {cam}_{fecha}_{hora}.{micro}.mp4 (archiva_video.py)
 *   - `estancias.fecha_ini/fecha_fin` <- fotos <fichero>_<segs>.jpg (clasificadorV2.php)
 *   - `cruces_lineas.fecha`          <- procesa_video.py (mismo vídeo)
 * El vínculo es, por tanto, solape de intervalos por cámara (barato, sin tocar el MP4
 * ni re-comparar embeddings). Solo si un vídeo no tiene NINGUNA estancia se marca
 * para re-estudio (vinculos_videos_sin_estancia).
 */

require_once __DIR__ . "/db.php";

/**
 * Solape de dos intervalos con margen (función pura, testeable sin BD).
 * [a_ini, a_fin] y [b_ini, b_fin] se consideran vinculables si se solapan o
 * distan menos de $margen segundos.
 */
function vinculos_solapa(string $a_ini, string $a_fin, string $b_ini, string $b_fin, int $margen): bool {
    $ai = strtotime($a_ini);
    $af = strtotime($a_fin);
    $bi = strtotime($b_ini);
    $bf = strtotime($b_fin);
    if ($ai === false || $bi === false) {
        return false;
    }
    $af = ($af === false) ? $ai : $af;
    $bf = ($bf === false) ? $bi : $bf;
    return $ai <= ($bf + $margen) && $bi <= ($af + $margen);
}

/**
 * Índice del intervalo más cercano a un punto (función pura, testeable sin BD).
 * @param int $t        epoch del punto (cruce)
 * @param array $ints   lista de ['ini'=>epoch,'fin'=>epoch]
 * @return int|null     índice en $ints del más cercano dentro de $margen; null si ninguno
 */
function vinculos_mas_cercano(int $t, array $ints, int $margen): ?int {
    $mejor_i = null;
    $mejor_d = $margen;
    foreach ($ints as $i => $iv) {
        $ini = (int)$iv["ini"];
        $fin = (int)($iv["fin"] ?? $ini);
        if ($t < ($ini - $margen) || $t > ($fin + $margen)) {
            continue;
        }
        $d = 0;
        if ($t < $ini) { $d = $ini - $t; }
        elseif ($t > $fin) { $d = $t - $fin; }
        if ($d < $mejor_d) {
            $mejor_d = $d;
            $mejor_i = $i;
        }
    }
    return $mejor_i;
}

/**
 * Enlaza una estancia con su vídeo de movimiento (misma cámara + solape con margen).
 * @return int|null video_id asignado (o null si no hay candidato)
 */
function vinculos_vincular_estancia(array $estancia, int $margen): ?int {
    $camara_id = (int)$estancia["camara_id"];
    $ini = (string)$estancia["fecha_ini"];
    $fin = (string)($estancia["fecha_fin"] ?? $ini);
    $v = DB::selectOne(
        "SELECT id FROM videos
         WHERE camara_id = ?
           AND fecha_ini <= DATE_ADD(?, INTERVAL ? SECOND)
           AND fecha_fin >= DATE_SUB(?, INTERVAL ? SECOND)
         ORDER BY ABS(TIMESTAMPDIFF(SECOND, fecha_ini, ?)) ASC
         LIMIT 1",
        [$camara_id, $fin, $margen, $ini, $margen, $ini]
    );
    if (!$v) {
        return null;
    }
    DB::execute("UPDATE estancias SET video_id = ? WHERE id = ?", [(int)$v["id"], (int)$estancia["id"]]);
    return (int)$v["id"];
}

/**
 * Enlaza todas las estancias sin vídeo de una cámara que solapan con la ventana del vídeo.
 * @return int número de estancias enlazadas
 */
function vinculos_video_a_estancias(array $video, int $margen): int {
    return (int) DB::execute(
        "UPDATE estancias SET video_id = ?
         WHERE video_id IS NULL AND camara_id = ?
           AND fecha_ini <= DATE_ADD(?, INTERVAL ? SECOND)
           AND fecha_fin >= DATE_SUB(?, INTERVAL ? SECOND)",
        [(int)$video["id"], (int)$video["camara_id"],
         (string)$video["fecha_fin"], $margen, (string)$video["fecha_ini"], $margen]
    );
}

/**
 * Enlaza los cruces de línea (de las líneas de la cámara del vídeo) dentro de la
 * ventana temporal del vídeo.
 * @return int número de cruces enlazados
 */
function vinculos_video_a_cruces(array $video, int $margen): int {
    $cruces = DB::select(
        "SELECT cl.id FROM cruces_lineas cl
         JOIN lineas l ON l.id = cl.linea_id
         WHERE cl.video_id IS NULL AND l.camara_id = ?
           AND cl.fecha >= DATE_SUB(?, INTERVAL ? SECOND)
           AND cl.fecha <= DATE_ADD(?, INTERVAL ? SECOND)",
        [(int)$video["camara_id"], (string)$video["fecha_ini"], $margen,
         (string)$video["fecha_fin"], $margen]
    );
    if (!$cruces) {
        return 0;
    }
    foreach ($cruces as $cr) {
        DB::execute("UPDATE cruces_lineas SET video_id = ? WHERE id = ?", [(int)$video["id"], (int)$cr["id"]]);
    }
    return count($cruces);
}

/**
 * Atribuye persona a un cruce (si es posible): la estancia del mismo vídeo (o de la
 * misma cámara) cuya ventana cubre la fecha del cruce; si hay varias, la más cercana.
 * @return int|null persona_id asignado (o null si no hay candidato)
 */
function vinculos_cruce_a_persona(int $cruce_id, ?int $camara_id, ?int $video_id, string $fecha, int $margen): ?int {
    $ints = [];
    if ($video_id) {
        $rows = DB::select(
            "SELECT persona_id, fecha_ini, fecha_fin FROM estancias WHERE video_id = ?",
            [$video_id]
        );
    } elseif ($camara_id) {
        $rows = DB::select(
            "SELECT persona_id, fecha_ini, fecha_fin FROM estancias WHERE camara_id = ?",
            [$camara_id]
        );
    } else {
        return null;
    }
    foreach ($rows as $r) {
        $ini = strtotime($r["fecha_ini"]);
        if ($ini === false) {
            continue;
        }
        $fin = strtotime((string)($r["fecha_fin"] ?? "")) ?: $ini;
        $ints[] = ["ini" => $ini, "fin" => $fin, "persona_id" => (int)$r["persona_id"]];
    }
    $t = strtotime($fecha);
    if ($t === false || !$ints) {
        return null;
    }
    $idx = vinculos_mas_cercano($t, $ints, $margen);
    if ($idx === null) {
        return null;
    }
    $persona_id = $ints[$idx]["persona_id"];
    DB::execute("UPDATE cruces_lineas SET persona_id = ? WHERE id = ?", [$persona_id, $cruce_id]);
    return $persona_id;
}

/**
 * Enlaza un cruce huérfano: primero le busca vídeo (misma cámara + ventana) y luego persona.
 * @return array ['video_id'=>?int, 'persona_id'=>?int]
 */
function vinculos_vincular_cruce(array $cruce, int $margen): array {
    $cruce_id = (int)$cruce["id"];
    $camara_id = (int)($cruce["camara_id"] ?? 0);
    $video_id = (int)($cruce["video_id"] ?? 0);
    $fecha = (string)$cruce["fecha"];

    if (!$video_id && $camara_id) {
        $v = DB::selectOne(
            "SELECT id FROM videos
             WHERE camara_id = ?
               AND fecha_ini <= DATE_ADD(?, INTERVAL ? SECOND)
               AND fecha_fin >= DATE_SUB(?, INTERVAL ? SECOND)
             ORDER BY ABS(TIMESTAMPDIFF(SECOND, fecha_ini, ?)) ASC
             LIMIT 1",
            [$camara_id, $fecha, $margen, $fecha, $margen, $fecha]
        );
        if ($v) {
            $video_id = (int)$v["id"];
            DB::execute("UPDATE cruces_lineas SET video_id = ? WHERE id = ?", [$video_id, $cruce_id]);
        }
    }

    $persona_id = vinculos_cruce_a_persona($cruce_id, $camara_id, $video_id ?: null, $fecha, $margen);

    return ["video_id" => $video_id ?: null, "persona_id" => $persona_id];
}

/**
 * Procesa un vídeo completo: enlaza sus estancias, sus cruces y la persona de cada cruce.
 * @return array ['estancias'=>int, 'cruces'=>int, 'personas'=>int]
 */
function vinculos_vincular_video(array $video, int $margen): array {
    $n_est = vinculos_video_a_estancias($video, $margen);
    $n_cru = vinculos_video_a_cruces($video, $margen);
    $n_per = 0;
    if ($n_cru > 0) {
        $cruces = DB::select(
            "SELECT cl.id, cl.fecha FROM cruces_lineas cl
             JOIN lineas l ON l.id = cl.linea_id
             WHERE cl.video_id = ? AND cl.persona_id IS NULL AND l.camara_id = ?",
            [(int)$video["id"], (int)$video["camara_id"]]
        );
        foreach ($cruces as $cr) {
            if (vinculos_cruce_a_persona((int)$cr["id"], (int)$video["camara_id"], (int)$video["id"], (string)$cr["fecha"], $margen) !== null) {
                $n_per++;
            }
        }
    }
    return ["estancias" => $n_est, "cruces" => $n_cru, "personas" => $n_per];
}

/**
 * Vídeos que NO tienen ninguna estancia asociada (ni por FK ni por solape) en los
 * últimos $dias días: candidatos a re-estudio (movimiento sin cara reconocible).
 * @return array filas de videos
 */
function vinculos_videos_sin_estancia(int $local_id, int $margen, int $dias, int $limite): array {
    return DB::select(
        "SELECT id, local_id, camara_id, nombre, ruta FROM videos
         WHERE local_id = ? AND fecha_ini >= DATE_SUB(NOW(), INTERVAL ? DAY)
           AND NOT EXISTS (
               SELECT 1 FROM estancias e
               WHERE e.camara_id = videos.camara_id
                 AND e.fecha_ini <= DATE_ADD(videos.fecha_fin, INTERVAL ? SECOND)
                 AND e.fecha_fin >= DATE_SUB(videos.fecha_ini, INTERVAL ? SECOND)
           )
         ORDER BY fecha_ini DESC LIMIT ?",
        [$local_id, $dias, $margen, $margen, $limite]
    );
}
