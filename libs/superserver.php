<?php
/**
 * Integración con SuperServer (M3) — modo del proyecto.
 *
 * El panel escribe `/var/lib/taildeck/projects/reconocimientoFacial.mode` con
 * `local` o `superserver` (pantalla Proyectos de SuperServer).
 *
 *   - `local` (por defecto): nada cambia; `detector.php` ejecuta el
 *     `procesa_video.py` clásico en este servidor.
 *   - `superserver`: `detector.php` lanza `motor/pool_bridge.py`, que pide el
 *     cálculo al pool y aplica aquí los MISMOS efectos (caras, cruces, embudo,
 *     borrado del vídeo y del marker).
 */
function ss_mode(): string {
    $f = '/var/lib/taildeck/projects/reconocimientoFacial.mode';
    $m = @file_get_contents($f);
    return (is_string($m) && trim($m) === 'superserver') ? 'superserver' : 'local';
}
