<?php
declare(strict_types=1);

require_once __DIR__ . '/../libs/photo_ingest.php';

if (foto_ingestable_nombre('persona.jpg.hq.tmp.jpg')) {
    throw new RuntimeException('El temporal HQ no puede entrar en la ingesta');
}
foreach (['persona.jpg', 'persona.jpg.hq', 'PERSONA.JPG.HQ'] as $name) {
    if (!foto_ingestable_nombre($name)) {
        throw new RuntimeException("La foto final válida fue rechazada: {$name}");
    }
}

echo "photo_ingest_test.php: OK\n";
