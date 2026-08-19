<?php
/* La Forja · Tab Plano: subir imagen, dibujar croquis y elegir cuál se usa como fondo.
 * El lienzo de trabajo (canvasID) está en edit.php, siempre visible.
 * Variables disponibles: $plano_act_cfg, $plano_subida_cfg, $plano_dibujo_cfg.
 */
?>

<div class="form-section">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">🗺️</span>
        Plano del local
    </div>

    <!-- Pestañas: qué plano se usa como fondo (imagen subida o croquis dibujado) -->
    <div class="rf-tabs" role="tablist" aria-label="Plano en uso">
        <a role="tab" aria-selected="<?= $plano_act_cfg === "subida" ? "true" : "false"; ?>"
           class="rf-tab<?= $plano_act_cfg === "subida" ? " is-active" : ""; ?><?= !$plano_subida_cfg ? " is-empty" : ""; ?>"
           href="?page=config&tab=plano&accion=plano_activo&tipo=subida">Imagen subida</a>
        <a role="tab" aria-selected="<?= $plano_act_cfg === "dibujo" ? "true" : "false"; ?>"
           class="rf-tab<?= $plano_act_cfg === "dibujo" ? " is-active" : ""; ?><?= !$plano_dibujo_cfg ? " is-empty" : ""; ?>"
           href="?page=config&tab=plano&accion=plano_activo&tipo=dibujo">Croquis dibujado</a>
    </div>
    <p class="text-xs text-gray-500 dark:text-gray-600 mt-1 mb-3">
        El plano marcado es el que se muestra como fondo en el lienzo y en Caminos. La pestaña sin archivo todavía no puede activarse.
    </p>

    <form action="?page=config&tab=plano&accion=plano" method="POST" enctype="multipart/form-data" name="formplano" id="formplano">
        <label for="plano" class="field-label">Imagen del plano</label>
        <div class="flex flex-col sm:flex-row gap-2 items-stretch sm:items-center">
            <input type="file" name="plano" id="plano" class="input border w-full">
            <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="cargarplano()">Cargar plano</button>
        </div>
    </form>

    <button type="button" class="button text-white bg-theme-1 shadow-md mt-3 w-full sm:w-auto" onclick="abrirDibujo()">
        <?= $plano_dibujo_cfg ? "✏️ Editar croquis a mano alzada" : "✏️ Dibujar croquis a mano alzada"; ?>
    </button>
    <p class="text-xs text-gray-500 dark:text-gray-600 mt-1">
        Abre un editor tipo Paint: dibuja con el ratón y guárdalo como plano del local (se guarda aparte de la imagen subida).
        <?= $plano_dibujo_cfg ? "Ya tienes un croquis: se cargará al abrir para poder retocarlo o borrarlo." : ""; ?>
    </p>
</div>
