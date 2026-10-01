<?php

declare(strict_types=1);

/*
 * Diagnóstico de encuadre de caras — vista (solo lectura).
 * Pinta el informe cacheado de motor/diagnostics/caras.json.
 */

$diagCriticoPx = 96;
$diagOkPx      = 160;
if (is_array($diagInforme)) {
    $diagCriticoPx = (int)($diagInforme["critico_px"] ?? 96);
    $diagOkPx      = (int)($diagInforme["ok_px"] ?? 160);
}
$diagCriticas  = (is_array($diagInforme) && is_array($diagInforme["criticas"] ?? null))
    ? array_values(array_filter(array_map("strval", $diagInforme["criticas"]), static fn($c): bool => $c !== ""))
    : [];
?>

<?php if ($diagGenerando): ?>
<meta http-equiv="refresh" content="20;url=?page=diagnostico">
<?php endif; ?>

<div class="intro-y flex flex-col sm:flex-row items-center mt-8">
    <h2 class="text-lg font-medium mr-auto">🔬 Diagnóstico de encuadre de caras</h2>
    <div class="w-full sm:w-auto flex mt-4 sm:mt-0">
        <a href="?page=diagnostico" class="button text-gray-700 dark:text-gray-300 border dark:border-dark-5 shadow-md mr-2">↻ Recargar</a>
        <a href="?page=diagnostico&amp;actualizar=1" class="button text-white bg-theme-1 shadow-md">📸 Actualizar</a>
    </div>
</div>

<div class="intro-y box p-5 mt-5">
    <p class="text-sm text-gray-600 dark:text-gray-500">
        Mide el <strong>tamaño de la cara</strong> que ve cada cámara en los vídeos más recientes
        (ancho en píxeles). Sirve para decidir qué cámaras conviene <strong>acercar, reorientar o
        hacer zoom</strong>: por debajo de <?= (int)$diagCriticoPx; ?> px la cara es inutilizable para el
        reconocimiento facial; a partir de <?= (int)$diagOkPx; ?> px se considera correcta. El análisis es
        pesado, por lo que se ejecuta en segundo plano y esta página solo muestra el informe guardado.
    </p>
</div>

<?php if ($diagError !== ""): ?>
<div class="intro-y box p-5 mt-5" style="border-left:4px solid #b91c1c">
    <div class="font-bold text-red-600">No se pudo lanzar el informe</div>
    <div class="text-sm text-gray-600 dark:text-gray-500 mt-1"><?= htmlspecialchars($diagError, ENT_QUOTES); ?></div>
</div>
<?php endif; ?>

<?php if ($diagGenerando): ?>
<div class="intro-y box p-5 mt-5" style="border-left:4px solid #d97706">
    <div class="font-bold text-yellow-600">⏳ Generando informe… recarga en ~1-2 minutos</div>
    <div class="text-sm text-gray-600 dark:text-gray-500 mt-1">
        El motor está analizando los vídeos en segundo plano. Esta página se recargará sola cada 20 segundos
        hasta que el informe esté listo.
    </div>
</div>
<?php endif; ?>

<?php if ($diagInforme === null): ?>
    <?php if (!$diagGenerando): ?>
    <div class="intro-y box p-10 mt-5 text-center">
        <div class="text-4xl mb-3" aria-hidden="true">🗒️</div>
        <div class="font-bold">Sin informe todavía. Pulsa Actualizar.</div>
        <div class="text-sm text-gray-600 dark:text-gray-500 mt-2">
            Cuando termine el análisis aparecerá aquí la tabla de tamaño de cara por cámara.
        </div>
    </div>
    <?php endif; ?>
<?php else: ?>

    <?php
    $diagFilas   = $diagInforme["filas"];
    $diagGenerado = (float)($diagInforme["generado"] ?? 0);
    $diagFecha    = $diagGenerado > 0 ? date("d/m/Y H:i", (int)$diagGenerado) : "—";
    ?>

    <div class="intro-y flex flex-wrap items-center mt-8">
        <h3 class="text-base font-medium mr-auto">
            Informe del <?= htmlspecialchars($diagFecha, ENT_QUOTES); ?>
        </h3>
        <div class="text-xs text-gray-500 dark:text-gray-600">
            <?= (int)($diagInforme["videos"] ?? 0); ?> vídeo(s) · <?= (int)($diagInforme["frames"] ?? 0); ?> frame(s) por vídeo ·
            Local <?= htmlspecialchars((string)($diagInforme["local"] ?? $diagLocalId), ENT_QUOTES); ?>
        </div>
    </div>

    <?php if (count($diagCriticas) > 0): ?>
    <div class="intro-y box p-5 mt-5" style="border-left:4px solid #b91c1c">
        <div class="font-bold text-red-600">
            ⚠ Cámaras críticas (cara &lt; <?= (int)$diagCriticoPx; ?> px):
            <?= htmlspecialchars(implode(", ", $diagCriticas), ENT_QUOTES); ?>
        </div>
        <div class="text-sm text-gray-600 dark:text-gray-500 mt-1">
            → acercar / reorientar / hacer zoom en estas cámaras para que la cara sea utilizable.
        </div>
    </div>
    <?php endif; ?>

    <div class="intro-y box p-5 mt-5">
        <div class="table-wrap">
            <table class="table table-report table-report--bordered w-full">
                <thead>
                    <tr>
                        <th class="border-b-2 text-center">CÁMARA</th>
                        <th class="border-b-2 text-center">#CARAS</th>
                        <th class="border-b-2 text-center">MÁX PX</th>
                        <th class="border-b-2 text-center">MEDIA PX</th>
                        <th class="border-b-2 text-center">DIAGNÓSTICO</th>
                    </tr>
                </thead>
                <tbody>
                <?php if (count($diagFilas) === 0): ?>
                    <tr>
                        <td class="text-center border-b py-6 text-gray-500 dark:text-gray-500" colspan="5">
                            El informe no contiene cámaras con vídeos analizables.
                        </td>
                    </tr>
                <?php else: ?>
                    <?php $diagPar = "odd"; ?>
                    <?php foreach ($diagFilas as $diagFila): ?>
                        <?php
                        $diagMax    = (int)($diagFila["max"] ?? 0);
                        $diagEsCrit = $diagMax < $diagCriticoPx;
                        $diagEsOk   = $diagMax >= $diagOkPx;
                        $diagColor  = $diagEsCrit ? "text-red-600" : ($diagEsOk ? "text-green-600" : "text-yellow-600");
                        ?>
                        <tr class="<?= $diagPar; ?>">
                            <td class="text-center border-b whitespace-no-wrap font-medium">
                                <?= htmlspecialchars((string)($diagFila["camara"] ?? "—"), ENT_QUOTES); ?>
                            </td>
                            <td class="text-center border-b"><?= (int)($diagFila["n"] ?? 0); ?></td>
                            <td class="text-center border-b font-bold <?= $diagColor; ?>"><?= $diagMax; ?></td>
                            <td class="text-center border-b"><?= htmlspecialchars(number_format((float)($diagFila["avg"] ?? 0), 1), ENT_QUOTES); ?></td>
                            <td class="text-center border-b <?= $diagColor; ?>">
                                <?= htmlspecialchars((string)($diagFila["diag"] ?? "—"), ENT_QUOTES); ?>
                            </td>
                        </tr>
                        <?php $diagPar = ($diagPar === "odd") ? "pair" : "odd"; ?>
                    <?php endforeach; ?>
                <?php endif; ?>
                </tbody>
            </table>
        </div>
    </div>

<?php endif; ?>
