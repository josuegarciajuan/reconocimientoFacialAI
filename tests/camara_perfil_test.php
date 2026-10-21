<?php

/*
 * Test de detección de cámaras camaraip y fallback del helper de perfil.
 * No toca BD ni el bridge real: usa URLs sintéticas y un endpoint inválido.
 * Ejecutar: php tests/camara_perfil_test.php   (exit 0 = OK)
 */

require_once __DIR__ . "/../libs/camara_perfil.php";

$fallos = 0;
$total = 0;

function ok(bool $cond, string $msg): void
{
    global $fallos, $total;
    $total++;
    if ($cond) {
        echo "PASS  $msg\n";
    } else {
        $fallos++;
        echo "FAIL  $msg\n";
    }
}

ok(rf_camaraip_id("http://127.0.0.1:8111/camaraip/stream?camera=cam-oficina") === "cam-oficina",
    "1. URL local del bridge -> cam-oficina");
ok(rf_camaraip_id("https://josue.ink/camaraip/latest.jpg?camera=esp32-oficina") === "esp32-oficina",
    "2. URL pública /camaraip -> esp32-oficina");
ok(rf_camaraip_id("rtsp://example.invalid/cam/realmonitor?channel=1") === null,
    "3. RTSP sin camera -> null");
ok(rf_camaraip_id("https://josue.ink/ojos/admin/?camera=cam-oficina") === null,
    "4. URL de Ojos sin /camaraip -> null");
ok(rf_camaraip_id("") === null, "5. URL vacía -> null");

ok(rf_camara_perfil_fps("rtsp://example.invalid/cam/realmonitor?channel=1", 14) === 14,
    "6. RTSP conserva el fallback de BD");
ok(rf_camara_perfil_latest_url("http://127.0.0.1:8111/camaraip/stream?camera=cam-oficina")
    === "http://127.0.0.1:8111/camaraip/latest.jpg?camera=cam-oficina",
    "7. latest.jpg se construye para camaraip");
ok(rf_camara_perfil_latest_url("rtsp://example.invalid/cam") === null,
    "8. RTSP no genera latest.jpg");

$old = getenv("RF_CAMARA_PROFILE_URL");
putenv("RF_CAMARA_PROFILE_URL=http://127.0.0.1:9/profile");
ok(rf_camara_perfil("http://127.0.0.1:8111/camaraip/stream?camera=no-existe", 0.1) === null,
    "9. Bridge caído y sin copia guardada -> null");

$saved = rf_camara_perfil("http://127.0.0.1:8111/camaraip/stream?camera=cam-oficina", 0.1);
ok(is_array($saved) && ($saved["config_source"] ?? "") === "saved",
    "10. Bridge caído -> usa la copia guardada de /ojos");
ok(is_array($saved) && ($saved["profile"]["model"] ?? "") === "SiGma Micro USB Web Camera",
    "11. La copia guardada conserva el modelo de la webcam");
ok(is_array($saved) && (int)($saved["profile"]["stream"]["rotation"] ?? 0) === 180,
    "12. La copia guardada conserva la rotación 180°");
ok(rf_camara_perfil_fps("http://127.0.0.1:8111/camaraip/stream?camera=cam-oficina", 14) >= 1,
    "13. La copia guardada aporta un fps válido");
putenv("RF_CAMARA_PROFILE_URL=" . ($old === false ? "" : $old));

echo "\n$total tests, $fallos fallos\n";
exit($fallos ? 1 : 0);
