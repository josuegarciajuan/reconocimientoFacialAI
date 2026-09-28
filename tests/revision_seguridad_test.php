<?php

/*
 * Test de la validación pura de rutas de la bandeja de revisión (libs/revision.php).
 * No toca BD ni sesión: ejercita rf_revision_* con un árbol sintético.
 * Ejecutar: php tests/revision_seguridad_test.php   (exit 0 = OK)
 */

require_once __DIR__ . "/../libs/revision.php";

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

function rf_rmtree(string $dir): void {
    if (!is_dir($dir)) {
        return;
    }
    foreach (scandir($dir) ?: [] as $e) {
        if ($e === "." || $e === "..") {
            continue;
        }
        $p = $dir . "/" . $e;
        is_dir($p) && !is_link($p) ? rf_rmtree($p) : @unlink($p);
    }
    @rmdir($dir);
}

// --- árbol sintético motor/revision/1/2 ---
$root = sys_get_temp_dir() . "/rf_revision_test_" . getmypid() . "_" . bin2hex(random_bytes(4));
@mkdir($root . "/motor/revision/1/2", 0777, true);
file_put_contents($root . "/motor/revision/1/2/a.jpg", "x");
file_put_contents($root . "/motor/revision/1/2/b.png", "x");
file_put_contents($root . "/motor/revision/1/2/a.txt", "x");
@mkdir($root . "/outside", 0777, true);
file_put_contents($root . "/outside/exterior.jpg", "x");
@symlink($root . "/outside/exterior.jpg", $root . "/motor/revision/1/2/link.jpg");

// --- 1. componentes ---
ok(rf_revision_componente_valido("abc_1.2-3") === true, "1. componente válido");
ok(rf_revision_componente_valido("19_2026-09-25_17:10:03.604617.mp4_1.5_0") === true, "1. componente real con ':' -> válido");
ok(rf_revision_componente_valido("") === false, "1. componente vacío -> inválido");
ok(rf_revision_componente_valido(".") === false, "1. componente '.' -> inválido");
ok(rf_revision_componente_valido("..") === false, "1. componente '..' -> inválido");
ok(rf_revision_componente_valido("a/b") === false, "1. componente con '/' -> inválido");
ok(rf_revision_componente_valido("a b") === false, "1. componente con espacio -> inválido");

// --- 2. extensión ---
ok(rf_revision_es_imagen("a.jpg") === true && rf_revision_es_imagen("a.JPEG") === true, "2. jpg/jpeg -> imagen");
ok(rf_revision_es_imagen("a.png") === true, "2. png -> imagen");
ok(rf_revision_es_imagen("a.gif") === false && rf_revision_es_imagen("a.txt") === false, "2. gif/txt -> no imagen");

// --- 3. ruta válida ---
$esperada = realpath($root . "/motor/revision/1/2/a.jpg");
ok(rf_revision_ruta_segura($root, "1", "2", "a.jpg") === $esperada, "3. ruta válida devuelve realpath");

// --- 4. traversal ---
ok(rf_revision_ruta_segura($root, "1", "2", "../a.jpg") === null, "4. file '../' -> null");
ok(rf_revision_ruta_segura($root, "1", "2", "/tmp/fuera.jpg") === null, "4. file absoluto -> null");
ok(rf_revision_ruta_segura($root, "../1", "2", "a.jpg") === null, "4. local '../' -> null");
ok(rf_revision_ruta_segura($root, "1", "../2", "a.jpg") === null, "4. cam '../' -> null");
ok(rf_revision_ruta_segura($root, "1", "2/3", "a.jpg") === null, "4. cam con '/' -> null");

// --- 5. extensión / inexistente ---
ok(rf_revision_ruta_segura($root, "1", "2", "a.txt") === null, "5. extensión no imagen -> null");
ok(rf_revision_ruta_segura($root, "1", "2", "noexiste.jpg") === null, "5. fichero inexistente -> null");

// --- 6. symlink que escapa -> null ---
if (is_link($root . "/motor/revision/1/2/link.jpg")) {
    ok(rf_revision_ruta_segura($root, "1", "2", "link.jpg") === null, "6. symlink fuera -> null");
} else {
    echo "SKIP  6. symlinks no soportados en este sistema\n";
}

rf_rmtree($root);

echo "\n$total tests, $fallos fallos\n";
exit($fallos ? 1 : 0);
