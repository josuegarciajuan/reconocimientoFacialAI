<?php

/*
 * Movimientos sin clasificar — admin/pages/sin_clasificar/index.php
 *
 * Muestra los VÍDEOS DE MOVIMIENTO archivados que todavía NO tienen persona
 * asignada (identidad diferida). Da visibilidad inmediata: `archiva_video` los
 * publica en segundos (remux + miniatura), así el usuario ve "algo pasó" al
 * instante, sin esperar a que `procesa_video`/`clasificador`/`vinculador` lo
 * asocien a una persona. Cuando se asigna, el movimiento pasa a "Accesos" y
 * desaparece de aquí (mismo criterio de solape temporal que libs/vinculos.php).
 *
 * SOLO LECTURA: no toca el motor ni la BD. Los indicadores muestran además la
 * cola real del detector (ficheros en motor/videos/) y la última clasificación.
 */

require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/etiquetas.php";

$local_id = (int)($_SESSION["local_id"] ?? 0);
$limite = 60;

// Solape temporal vídeo <-> estancia (misma cámara), igual que libs/vinculos.php.
$solape = "EXISTS (SELECT 1 FROM estancias e
                    WHERE e.camara_id = v.camara_id
                      AND e.fecha_ini <= COALESCE(v.fecha_fin, v.fecha_ini)
                      AND e.fecha_fin >= v.fecha_ini)";

$sin = DB::select(
    "SELECT v.id, v.camara_id, v.fecha_ini, v.fecha_fin, v.duracion, v.poster,
            c.descripcion AS camara
       FROM videos v
       JOIN camaras c ON c.id = v.camara_id
      WHERE v.local_id = ? AND NOT $solape
      ORDER BY v.fecha_ini DESC
      LIMIT " . (int)$limite,
    [$local_id]
);
$total_sin = (int)(DB::selectOne(
    "SELECT COUNT(*) AS n FROM videos v WHERE v.local_id = ? AND NOT $solape",
    [$local_id]
)["n"] ?? 0);

// Cola real del detector: ficheros aún sin procesar en motor/videos/.
$cola = 0;
$cola_oldest = null;
$raiz = rtrim(RUTA_PROYECTO, "/");
foreach (glob($raiz . "/motor/videos/*/*/*.mp4") ?: [] as $f) {
    $cola++;
    $m = @filemtime($f);
    if ($m && ($cola_oldest === null || $m < $cola_oldest)) {
        $cola_oldest = $m;
    }
}

// Última clasificación registrada (foto publicada) del local.
$ult = DB::selectOne(
    "SELECT MAX(f.created) AS t FROM fotos f
      JOIN estancias e ON e.id = f.estancia_id
      JOIN camaras c ON c.id = e.camara_id
     WHERE c.local_id = ?",
    [$local_id]
);
$ult_txt = ($ult && !empty($ult["t"])) ? $ult["t"] : "—";

function rf_hace(float|int|null $ts): string {
    if (!$ts) { return "—"; }
    $d = time() - (int)$ts;
    if ($d < 60) { return "hace " . $d . " s"; }
    if ($d < 3600) { return "hace " . intval($d / 60) . " min"; }
    if ($d < 86400) { return "hace " . intval($d / 3600) . " h"; }
    return "hace " . intval($d / 86400) . " d";
}
?>

<div class="intro-y flex flex-col sm:flex-row items-center mt-8">
    <h2 class="text-lg font-medium mr-auto"><?= rf_term_html("nav-sin-clasificar"); ?></h2>
    <div class="text-slate-500 text-xs sm:text-sm">
        <?= htmlspecialchars((string)$total_sin); ?> sin clasificar ·
        <?= htmlspecialchars((string)$cola); ?> en cola ·
        última clasificación: <?= htmlspecialchars((string)$ult_txt); ?>
    </div>
</div>

<?php if ($cola > 0): ?>
<div class="intro-y box p-4 mt-4 border-l-4 border-theme-3">
    <div class="text-sm">
        <strong><?= htmlspecialchars((string)$cola); ?></strong> vídeo(s) de movimiento esperando a ser analizados
        <?php if ($cola_oldest !== null): ?>
            (el más antiguo, <?= htmlspecialchars(rf_hace($cola_oldest)); ?>).
        <?php endif; ?>
        Mientras haya cola, la identidad de los movimientos nuevos puede tardar en asignarse.
    </div>
</div>
<?php endif; ?>

<?php if (!$sin): ?>
    <div class="intro-y box p-8 mt-5 text-center text-slate-500">
        No hay movimientos recientes sin clasificar. Todo lo archivado tiene persona asignada.
    </div>
<?php else: ?>
    <div class="intro-y grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4 mt-5">
        <?php foreach ($sin as $r): ?>
            <div class="box p-2">
                <a href="../video.php?id=<?= (int)$r["id"]; ?>" target="_blank"
                   title="Ver vídeo del movimiento">
                    <img class="w-full h-32 object-cover rounded"
                         loading="lazy"
                         alt="Miniatura del movimiento"
                         onerror="this.style.opacity='0.25'"
                         src="../video.php?id=<?= (int)$r["id"]; ?>&poster=1">
                </a>
                <div class="mt-2 text-xs text-slate-600 truncate"
                     title="<?= htmlspecialchars(camara_label($r["camara"]), ENT_QUOTES); ?>">
                    <?= htmlspecialchars(camara_label($r["camara"])); ?>
                </div>
                <div class="text-xs text-slate-500">
                    <?= htmlspecialchars((string)$r["fecha_ini"]); ?>
                    <?php if ((float)$r["duracion"] > 0): ?>
                        · <?= (int)round((float)$r["duracion"]); ?>s
                    <?php endif; ?>
                </div>
            </div>
        <?php endforeach; ?>
    </div>
    <div class="text-slate-500 text-xs mt-4">
        Mostrando los <?= count($sin); ?> movimientos sin clasificar más recientes.
    </div>
<?php endif; ?>
