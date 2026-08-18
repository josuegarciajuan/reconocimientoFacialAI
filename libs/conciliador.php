<?php

/*
 * libs/conciliador.php — Lógica de conciliación de fichajes con horario.
 *
 * v1: 100% automático (sin edición manual). El daemon conciliador.php la
 * consume y escribe en la tabla `fichajes`; los listados del panel leen esa
 * tabla.
 *
 * Modelo de eventos
 * -----------------
 * Un "evento de puerta" es una estancia de un trabajador en una cámara
 * marcada como puerta (ENTRY) o salida (EXIT). Un trabajador pasa por la
 * puerta varias veces al día; solo interesan el primero (entrada al trabajo)
 * y el último (salida definitiva) de cada bloque horario. Los pasos
 * intermedios (fumar, recoger, etc.) se ignoran por construcción.
 *
 * Reglas
 * ------
 * 1. Sin horario configurado en el local => 1 bloque:
 *      entrada = primer ENTRY del día, salida = último EXIT del día.
 * 2. Con horario (margen M en minutos; e2_inicio = hora_entrada2 - M):
 *    a. hay_bloque2 = jornada_partida Y existe ENTRY con hora >= e2_inicio
 *       -> detecta que la persona "volvió por la tarde". Cubre la media
 *          jornada (sin ENTRY por la tarde => 1 bloque) y la jornada
 *          continua (nunca sale a comer => 1 bloque).
 *    b. Si hay_bloque2:
 *         entrada1 = primer ENTRY del día
 *         entrada2 = primer ENTRY con hora >= e2_inicio
 *         salida1  = último EXIT anterior a entrada2   (salida a comer)
 *         salida2  = último EXIT del día              (salida definitiva)
 *    c. Si no hay_bloque2:
 *         entrada1 = primer ENTRY del día
 *         salida1  = último EXIT del día
 */

require_once __DIR__ . "/../config/rutas.php";
require_once __DIR__ . "/db.php";

/** Convierte 'H:i[:s]' a segundos desde medianoche. */
function t_hora_a_seg(string $hora): int {
    $p = explode(":", $hora);
    return (int)$p[0] * 3600 + (int)($p[1] ?? 0) * 60 + (int)($p[2] ?? 0);
}

/** Segundos desde medianoche (hora local del servidor) de un datetime 'Y-m-d H:i:s'. */
function t_hora_evento_s(?string $hora): int {
    if (!$hora) {
        return -1;
    }
    $t = strtotime($hora);
    if ($t === false) {
        return -1;
    }
    return (int)date("G", $t) * 3600 + (int)date("i", $t) * 60 + (int)date("s", $t);
}

/**
 * Lógica pura de conciliación (testeable sin BD).
 *
 * @param array $eventos Lista ordenada por hora: [['hora'=>'Y-m-d H:i:s', 'tipo'=>'ENTRY'|'EXIT', ...]]
 * @param array $horario ['jornada_partida'=>bool, 'hora_entrada1'=>, 'hora_salida1'=>,
 *                        'hora_entrada2'=>, 'hora_salida2'=>, 'margen_min'=>int]
 * @return array Bloques: [['bloque'=>1|2, 'entrada'=>evento|null, 'salida'=>evento|null]]
 */
function conciliar_eventos(array $eventos, array $horario = []): array {
    $entradas = array_values(array_filter($eventos, fn($e) => ($e["tipo"] ?? "") === "ENTRY"));
    $salidas  = array_values(array_filter($eventos, fn($e) => ($e["tipo"] ?? "") === "EXIT"));
    $ultima_salida = $salidas ? $salidas[count($salidas) - 1] : null;

    $te1 = $horario["hora_entrada1"] ?? null;
    $te2 = $horario["hora_entrada2"] ?? null;
    $partida = !empty($horario["jornada_partida"]);
    $margen = isset($horario["margen_min"])
        ? max(0, (int)$horario["margen_min"])
        : (int)CONFIG_CONCILIADOR_MARGEN_DEFECTO;

    // 1) Sin horario => legacy de 1 bloque.
    if (!$te1 && !$te2 && empty($horario["hora_salida1"]) && empty($horario["hora_salida2"])) {
        return [["bloque" => 1, "entrada" => $entradas[0] ?? null, "salida" => $ultima_salida]];
    }

    $margen_s = $margen * 60;

    // 2a) ¿Volvió por la tarde? (solo con jornada partida configurada)
    $hay_bloque2 = false;
    if ($partida && $te2 !== null && $te2 !== "") {
        $e2_inicio = t_hora_a_seg($te2) - $margen_s;
        foreach ($entradas as $e) {
            if (t_hora_evento_s($e["hora"]) >= $e2_inicio) {
                $hay_bloque2 = true;
                break;
            }
        }
    }

    if ($hay_bloque2) {
        // 2b) Jornada partida real: 2 bloques.
        $e2_inicio = t_hora_a_seg($te2) - $margen_s;
        $entrada2 = null;
        foreach ($entradas as $e) {
            if (t_hora_evento_s($e["hora"]) >= $e2_inicio) {
                $entrada2 = $e;
                break;
            }
        }
        $salida1 = null;
        if ($entrada2) {
            $t_e2 = t_hora_evento_s($entrada2["hora"]);
            foreach ($salidas as $s) {
                if (t_hora_evento_s($s["hora"]) < $t_e2) {
                    $salida1 = $s;
                }
            }
        }
        return [
            ["bloque" => 1, "entrada" => $entradas[0] ?? null, "salida" => $salida1],
            ["bloque" => 2, "entrada" => $entrada2, "salida" => $ultima_salida],
        ];
    }

    // 2c) Un único bloque.
    return [["bloque" => 1, "entrada" => $entradas[0] ?? null, "salida" => $ultima_salida]];
}

/**
 * Concilia un trabajador en un día y hace upsert en `fichajes`.
 *
 * @param int $local_id
 * @param int $persona_id
 * @param string $fecha 'Y-m-d'
 * @param bool $finalizado true => estado 'conciliado' (día cerrado); false => 'provisional'
 */
function conciliar_dia(int $local_id, int $persona_id, string $fecha, bool $finalizado = false): void {
    $local = DB::selectOne(
        "SELECT jornada_partida, hora_entrada1, hora_salida1, hora_entrada2, hora_salida2, margen_fichaje_min
         FROM locales WHERE id = ?",
        [$local_id]
    );
    $horario = $local ? [
        "jornada_partida" => (int)$local["jornada_partida"] === 1,
        "hora_entrada1"   => $local["hora_entrada1"] ?: null,
        "hora_salida1"    => $local["hora_salida1"] ?: null,
        "hora_entrada2"   => $local["hora_entrada2"] ?: null,
        "hora_salida2"    => $local["hora_salida2"] ?: null,
        "margen_min"      => (int)$local["margen_fichaje_min"],
    ] : [];

    $fin = date("Y-m-d H:i:s", strtotime($fecha . " +1 day"));
    $rows = DB::select(
        "SELECT e.id AS estancia_id, e.camara_id, e.fecha_ini,
                CASE WHEN c.puerta = 1 THEN 'ENTRY' ELSE 'EXIT' END AS tipo
         FROM estancias e
         JOIN camaras c ON c.id = e.camara_id
         WHERE e.persona_id = ? AND c.local_id = ?
           AND (c.puerta = 1 OR c.salida = 1)
           AND e.fecha_ini >= ? AND e.fecha_ini < ?
         ORDER BY e.fecha_ini ASC",
        [$persona_id, $local_id, $fecha . " 00:00:00", $fin]
    );

    $eventos = [];
    foreach ($rows as $r) {
        $eventos[] = [
            "hora"        => $r["fecha_ini"],
            "tipo"        => $r["tipo"],
            "estancia_id" => (int)$r["estancia_id"],
            "camara_id"   => (int)$r["camara_id"],
        ];
    }

    $bloques = conciliar_eventos($eventos, $horario);

    // Upsert idempotente (v1 sin edición manual): reemplaza el día entero.
    DB::execute("DELETE FROM fichajes WHERE persona_id = ? AND fecha = ?", [$persona_id, $fecha]);
    $estado = $finalizado ? "conciliado" : "provisional";
    foreach ($bloques as $b) {
        $en = $b["entrada"] ?? null;
        $sa = $b["salida"] ?? null;
        if (!$en && !$sa) {
            continue;
        }
        DB::insert(
            "INSERT INTO fichajes
               (local_id, persona_id, fecha, bloque,
                entrada_estancia_id, entrada_hora, entrada_camara_id,
                salida_estancia_id, salida_hora, salida_camara_id, estado)
             VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                $local_id, $persona_id, $fecha, (int)$b["bloque"],
                $en ? $en["estancia_id"] : null, $en ? $en["hora"] : null, $en ? $en["camara_id"] : null,
                $sa ? $sa["estancia_id"] : null, $sa ? $sa["hora"] : null, $sa ? $sa["camara_id"] : null,
                $estado,
            ]
        );
    }
}
