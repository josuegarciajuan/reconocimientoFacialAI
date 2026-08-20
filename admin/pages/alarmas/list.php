<?php

/*
 * La Almenara — listado de alarmas disparadas (movimiento en inactividad).
 * Muestra: fecha, cámara (enlace), severidad (aviso/asedio), vídeo asociado y
 * estado. El vídeo se enlaza vía video.php?id=<id> (poster como miniatura).
 */

require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/etiquetas.php";
require_once __DIR__ . "/../../../libs/alarmas.php";

$local_id = (int)($_SESSION["local_id"] ?? 0);

$alarmas = alarma_listado($local_id, 100);

// Totales del día para el resumen
$hoy = date("Y-m-d 00:00:00");
$resumen = DB::selectOne(
    "SELECT COUNT(*) AS total,
            SUM(CASE WHEN severidad = 'asedio' THEN 1 ELSE 0 END) AS asedios,
            SUM(CASE WHEN severidad = 'aviso' THEN 1 ELSE 0 END) AS avisos
     FROM alarmas WHERE local_id = ? AND fecha >= ?",
    [$local_id, $hoy]
);
$no_vistas = alarma_no_vistas_count($local_id);

function alarma_severidad_badge(string $sev): string
{
    if ($sev === "asedio") {
        return '<span class="px-2 py-0.5 rounded text-white text-xs font-bold" style="background:#b91c1c">ASEDIO</span>';
    }
    return '<span class="px-2 py-0.5 rounded text-white text-xs font-bold" style="background:#d97706">AVISO</span>';
}
?>

<div class="intro-y flex flex-col sm:flex-row items-center mt-8">
    <h2 class="text-lg font-medium mr-auto">🚨 La Almenara</h2>
    <div class="w-full sm:w-auto flex mt-4 sm:mt-0 text-xs text-gray-500 dark:text-gray-600">
        Alarmas por movimiento en horario de inactividad
    </div>
</div>

<div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-5">
    <div class="box p-4 text-center">
        <div class="text-2xl font-bold"><?= (int)($resumen["total"] ?? 0); ?></div>
        <div class="text-xs text-gray-500 dark:text-gray-600 mt-1">Hoy</div>
    </div>
    <div class="box p-4 text-center">
        <div class="text-2xl font-bold text-yellow-600"><?= (int)($resumen["avisos"] ?? 0); ?></div>
        <div class="text-xs text-gray-500 dark:text-gray-600 mt-1">Avisos</div>
    </div>
    <div class="box p-4 text-center">
        <div class="text-2xl font-bold text-red-600"><?= (int)($resumen["asedios"] ?? 0); ?></div>
        <div class="text-xs text-gray-500 dark:text-gray-600 mt-1">Asedios</div>
    </div>
    <div class="box p-4 text-center">
        <div class="text-2xl font-bold <?= $no_vistas > 0 ? "text-theme-6" : ""; ?>"><?= $no_vistas; ?></div>
        <div class="text-xs text-gray-500 dark:text-gray-600 mt-1">Sin revisar</div>
    </div>
</div>

<div class="intro-y box p-5 mt-5">
    <div class="flex flex-wrap items-center gap-2 mb-4">
        <a href="?page=alarmas&mode=config" class="button text-white bg-theme-1 shadow-md">📞 Teléfonos de aviso</a>
        <a href="?page=config&tab=locales" class="button text-white bg-theme-2 shadow-md">⚒️ Horarios del local</a>
        <?php if ($no_vistas > 0): ?>
        <button type="button" class="button text-white bg-theme-6 shadow-md ml-auto" onclick="alarmas_marcar_leidas()">✓ Marcar todo leído</button>
        <?php endif; ?>
    </div>

    <div class="table-wrap">
        <table class="table table-report table-report--bordered display datatable w-full">
            <thead>
                <tr>
                    <th class="border-b-2 text-center">FECHA</th>
                    <th class="border-b-2 text-center">CÁMARA</th>
                    <th class="border-b-2 text-center">SEVERIDAD</th>
                    <th class="border-b-2 text-center">VÍDEO</th>
                    <th class="border-b-2 text-center">ESTADO</th>
                </tr>
            </thead>
            <tbody>
            <?php
            $par = "odd";
            foreach ($alarmas as $a) {
                $cam_label = $a["camara_id"] ? camara_label($a["camara_desc"] ?? "", (int)$a["camara_id"]) : "Local (cualquier cámara)";
                $cam_html = $a["camara_id"]
                    ? camara_link((int)$a["camara_id"], $cam_label)
                    : htmlspecialchars($cam_label, ENT_QUOTES);
                $video_html = "-";
                if ($a["video_id"]) {
                    $video_id = (int)$a["video_id"];
                    $cam_titulo = $cam_label . " · " . ($a["fecha"] ?? "");
                    $video_html = '<a href="javascript:;" title="Ver vídeo de la alarma" '
                        . 'onclick="rfVideoModal(' . $video_id . ',\'../video.php?id=' . $video_id . '\',\'../video.php?id=' . $video_id . '&amp;poster=1\',\'' . htmlspecialchars($cam_titulo, ENT_QUOTES) . '\',0,0)">'
                        . '<img src="../video.php?id=' . $video_id . '&poster=1" alt="Miniatura del vídeo" class="w-20 h-12 object-cover rounded border border-gray-600" loading="lazy" onerror="this.style.display=\'none\'">'
                        . '</a>';
                }
                $estado = ((int)($a["notificacion_vista"] ?? 0) === 0)
                    ? '<span class="px-2 py-0.5 rounded text-white text-xs font-bold" style="background:#b91c1c">NUEVA</span>'
                    : '<span class="text-xs text-gray-500">Vista</span>';
            ?>
                <tr class="<?= $par; ?>">
                    <td class="text-center border-b whitespace-no-wrap"><?= htmlspecialchars($a["fecha"] ?? ""); ?></td>
                    <td class="text-center border-b"><?= $cam_html; ?></td>
                    <td class="text-center border-b"><?= alarma_severidad_badge((string)($a["severidad"] ?? "aviso")); ?></td>
                    <td class="text-center border-b"><?= $video_html; ?></td>
                    <td class="text-center border-b"><?= $estado; ?></td>
                </tr>
            <?php
                $par = ($par === "odd") ? "pair" : "odd";
            }
            if (!$alarmas) {
                echo '<tr class="odd"><td class="text-center border-b py-6 text-gray-500 dark:text-gray-500" colspan="5">'
                   . 'La Almenara está en calma: ninguna alarma registrada. Configura la vigilancia en «La Forja» → Fortalezas o Cámaras.</td></tr>';
            }
            ?>
            </tbody>
        </table>
    </div>
</div>

<script>
    function alarmas_marcar_leidas() {
        var xhr = new XMLHttpRequest();
        xhr.open("GET", "acciones_ajax.php?a=3", true);
        xhr.onreadystatechange = function () {
            if (xhr.readyState == 4) {
                if (typeof window.comprueba_alarmas === "function") { window.comprueba_alarmas(); }
                location.reload();
            }
        };
        xhr.send(null);
    }
</script>
