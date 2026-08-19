<?php

/*
 * Test de la lógica de vínculo línea de cámara ↔ línea del plano (libs/lineas_plano.php).
 * Las partes que tocan BD se ejecutan y luego se LIMPIAN los datos de prueba
 * creados (IDs aislados con prefijo de test). Si no hay BD, se omiten (SKIP).
 * Ejecutar: php tests/lineas_plano_vinculo_test.php   (exit 0 = OK)
 */

require_once __DIR__ . "/../libs/lineas_plano.php";

$fallos = 0;
$total = 0;

function ok(bool $cond, string $msg): void {
    global $fallos, $total;
    $total++;
    if ($cond) {
        echo "PASS  $msg\n";
    } else {
        $fallos++;
        echo "FAIL  $msg\n";
    }
}

// --- 0. UTF-8 (función pura, sin BD) ---
$r = lineas_plano_utf8(["nombre" => "línea café", "x1" => 10]);
ok($r["nombre"] === "línea café" && (int)$r["x1"] === 10, "0. lineas_plano_utf8 conserva UTF-8 válido y enteros");
$r2 = lineas_plano_utf8(["nombre" => "\xE1rea"]);
ok($r2["nombre"] === "área", "0. lineas_plano_utf8 convierte latin1 inválido a UTF-8");

// --- 1. Con BD: filas de prueba aisladas (se borran al final) ---
$hay_bd = false;
try {
    $x = DB::selectOne("SELECT 1 AS uno");
    $hay_bd = ($x !== null);
} catch (Throwable $e) {
    $hay_bd = false;
}

$creados = ["camaras" => [], "lineas" => [], "lineas_plano" => []];
$limpiar = function () use (&$creados): void {
    try {
        foreach ($creados["lineas_plano"] as $id) { DB::execute("DELETE FROM lineas_plano WHERE id = ?", [$id]); }
        foreach ($creados["lineas"] as $id) { DB::execute("DELETE FROM lineas WHERE id = ?", [$id]); }
        foreach ($creados["camaras"] as $id) { DB::execute("DELETE FROM camaras WHERE id = ?", [$id]); }
    } catch (Throwable $e) { /* la limpieza es best-effort */ }
};

if (!$hay_bd) {
    echo "SKIP  (sin BD: se omiten las comprobaciones de vínculo)\n";
} else {
    try {
        $local_id = (int)(DB::selectOne("SELECT COALESCE(MAX(id), 0) + 1000 AS n FROM locales")["n"] ?? 0);
        $cam_id = DB::insert("INSERT INTO camaras (local_id, descripcion, x, y) VALUES (?, 'cam_test_vinculo', 0, 0)", [$local_id]);
        $creados["camaras"][] = $cam_id;
        $linea_id = DB::insert("INSERT INTO lineas (camara_id, nombre, x1, y1, x2, y2) VALUES (?, 'l_test', 0, 0, 10, 10)", [$cam_id]);
        $creados["lineas"][] = $linea_id;
        $plano_id = DB::insert("INSERT INTO lineas_plano (camara_id, nombre, x1, y1, x2, y2) VALUES (?, 'lp_test', 0, 0, 20, 20)", [$cam_id]);
        $creados["lineas_plano"][] = $plano_id;

        // 1. Vincular: asigna linea_id.
        ok(lineas_plano_vincular($plano_id, $linea_id) === true, "1. Vincular línea del plano con línea de cámara");
        $lp = DB::selectOne("SELECT linea_id FROM lineas_plano WHERE id = ?", [$plano_id]);
        ok((int)($lp["linea_id"] ?? 0) === $linea_id, "1. lineas_plano.linea_id queda fijado");

        // 2. 1:1: una segunda línea del plano que vincula la misma línea de cámara la reasigna.
        $plano_id2 = DB::insert("INSERT INTO lineas_plano (camara_id, nombre, x1, y1, x2, y2) VALUES (?, 'lp_test2', 0, 0, 30, 30)", [$cam_id]);
        $creados["lineas_plano"][] = $plano_id2;
        ok(lineas_plano_vincular($plano_id2, $linea_id) === true, "2. Vincular la misma línea de cámara a otra línea del plano");
        $l1 = DB::selectOne("SELECT linea_id FROM lineas_plano WHERE id = ?", [$plano_id]);
        $l2 = DB::selectOne("SELECT linea_id FROM lineas_plano WHERE id = ?", [$plano_id2]);
        ok(($l1["linea_id"] ?? null) === null && (int)($l2["linea_id"] ?? 0) === $linea_id,
            "2. La antigua queda desvinculada (NULL) y la nueva la representa (1:1)");

        // 3. Desvincular: vuelve a NULL.
        ok(lineas_plano_desvincular($plano_id2) === true, "3. Desvincular");
        $l2b = DB::selectOne("SELECT linea_id FROM lineas_plano WHERE id = ?", [$plano_id2]);
        ok(($l2b["linea_id"] ?? null) === null, "3. lineas_plano.linea_id vuelve a NULL");

        // 4. lineas_sin_plano: excluye la ya mapeada, incluye la libre.
        $linea_libre = DB::insert("INSERT INTO lineas (camara_id, nombre, x1, y1, x2, y2) VALUES (?, 'l_libre', 0, 0, 10, 10)", [$cam_id]);
        $creados["lineas"][] = $linea_libre;
        lineas_plano_vincular($plano_id, $linea_id);
        $sin_plano = lineas_sin_plano($cam_id);
        $ids_sin = array_column($sin_plano, "id");
        ok(in_array((int)$linea_libre, $ids_sin, true) && !in_array((int)$linea_id, $ids_sin, true),
            "4. lineas_sin_plano excluye la línea ya representada");

        // 5. linea_plano_de_linea: recupera la representación.
        $lp_de = linea_plano_de_linea($linea_id);
        ok($lp_de && (int)$lp_de["id"] === (int)$plano_id, "5. linea_plano_de_linea recupera la línea del plano");

        // 6. lineas_plano_del_local: enriquecida con el nombre de la línea de cámara.
        $del_local = lineas_plano_del_local($local_id);
        $lp_encontrada = null;
        foreach ($del_local as $f) {
            if ((int)$f["id"] === (int)$plano_id) {
                $lp_encontrada = $f;
            }
        }
        ok($lp_encontrada !== null && ($lp_encontrada["linea_camara_nombre"] ?? "") === "l_test",
            "6. lineas_plano_del_local enriquece con linea_camara_nombre");

        $limpiar();
    } catch (Throwable $e) {
        $limpiar();
        ok(false, "EXCEPCIÓN en bloque BD: " . $e->getMessage());
        echo "\n{$total} comprobaciones, {$fallos} fallos\n";
        exit(1);
    }
}

echo "\n{$total} comprobaciones, {$fallos} fallos\n";
exit($fallos > 0 ? 1 : 0);
