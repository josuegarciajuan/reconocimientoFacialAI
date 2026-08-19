<?php
/* La Forja · Tab Líneas (sabor: Trazos): trazar líneas (sobre la foto de una cámara) + corregir líneas.
 * 2026-08-19:
 *  - "Trazar" muestra una rejilla de miniaturas de cámaras; al clicar una se abre
 *    un lienzo con su snapshot para dibujar las líneas por encima (sin recargar).
 *  - Se elimina "Representar en el plano" y el sub "plano": la representación se
 *    hace en El Yunque arrastrando las líneas al plano.
 * Sub-acciones: Trazar (crear) / Corregir (editar) — resueltas en $sub.
 * Variables disponibles: $camaras, $lineas_edit.
 */
?>

<!-- ---------- Submenú de la pestaña ---------- -->
<div class="forge-submenu" role="tablist" aria-label="Acciones de líneas">
    <a role="tab" aria-selected="<?= $sub === "trazar" ? "true" : "false"; ?>"
       class="forge-sub<?= $sub === "trazar" ? " is-active" : ""; ?>"
       href="?page=config&tab=lineas&sub=trazar" data-lore="trazar">Trazar</a>
    <a role="tab" aria-selected="<?= $sub === "editar" ? "true" : "false"; ?>"
       class="forge-sub<?= $sub === "editar" ? " is-active" : ""; ?>"
       href="?page=config&tab=lineas&sub=editar" data-lore="corregir">Corregir</a>
</div>

<?php if ($sub === "editar"): ?>
<!-- ---------- Corregir (editar líneas de foto) ---------- -->
<div class="form-section" data-panel-forge="editar">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">✏️</span>
        Editar líneas
    </div>

    <div class="form-grid">
        <div class="form-grid__full">
            <label for="editar_linea" class="field-label">Línea a editar</label>
            <select id="editar_linea" name="editar_linea" class="input border w-full" onchange="TrazadorAbrirCorregir(this.value)">
                <option value="-">Selecciona Línea</option>
                <?php foreach ($lineas_edit as $l): ?>
                    <option <?php if (isset($_GET["editar_linea"]) && $_GET["editar_linea"] == $l["id"] . "-" . $l["camara_id"]) { echo "selected='selected'"; } ?> value="<?= (int)$l["id"]; ?>-<?= (int)$l["camara_id"]; ?>"><?= htmlspecialchars($l["nombre"] . " - " . $l["descripcion"]); ?></option>
                <?php endforeach; ?>
            </select>
            <p class="text-xs text-gray-500 dark:text-gray-600 mt-2">
                Al elegir la línea se abre el lienzo con la foto de su cámara para corregirla.
            </p>
        </div>
        <div class="form-grid__full">
            <p class="text-xs text-gray-500 dark:text-gray-600">
                La posición de la línea en el plano 2D se ajusta en «El Yunque» arrastrándola sobre el plano.
            </p>
        </div>
    </div>
</div>

<?php else: ?>
<!-- ---------- Trazar (crear líneas de foto) ---------- -->
<div class="form-section" data-panel-forge="trazar">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">📏</span>
        Líneas
    </div>

    <p class="text-xs text-gray-500 dark:text-gray-600 mb-3">
        Elige una cámara: se abrirá su imagen en directo y podrás trazar las líneas de vigilancia por encima (dos clics por línea: inicio y fin).
    </p>

    <div class="forge-cam-grid">
        <?php foreach ($camaras as $c): ?>
            <button type="button" class="forge-cam-card" onclick="TrazadorAbrir(<?= (int)$c["id"]; ?>)">
                <span class="forge-cam-card__media">
                    <img src="fotos_camara/<?= (int)$c["id"]; ?>.png"
                         onerror="this.onerror=null;this.src=''"
                         alt="Snapshot de <?= htmlspecialchars($c["descripcion"], ENT_QUOTES); ?>" loading="lazy">
                </span>
                <span class="forge-cam-card__name"><?= htmlspecialchars($c["descripcion"], ENT_QUOTES); ?></span>
            </button>
        <?php endforeach; ?>
        <?php if (!$camaras): ?>
            <p class="text-xs text-gray-500 dark:text-gray-600">No hay cámaras dadas de alta todavía.</p>
        <?php endif; ?>
    </div>
</div>
<?php endif; ?>

<!-- ============ Modal: trazador de líneas sobre el snapshot de la cámara ============ -->
<div id="lineaModal" class="modal" role="dialog" aria-modal="true" aria-labelledby="lineaTitulo">
    <div class="modal__content box p-5 modal__content--xl">
        <div class="flex items-center mb-4">
            <h3 id="lineaTitulo" class="media-modal__title mr-auto truncate">Trazar líneas</h3>
            <span class="text-xs text-gray-500 dark:text-gray-600 mr-3" id="lineaSub">—</span>
            <a href="javascript:;" data-dismiss="modal" onclick="TrazadorCerrar()" class="button button--sm text-white bg-theme-6 ml-3">Cerrar</a>
        </div>

        <div class="trazador-hint text-xs text-gray-500 dark:text-gray-600 mb-2" id="lineaHint">
            Dos clics por línea: primer clic = inicio, segundo clic = fin. Escribe el nombre de cada línea en su recuadro.
        </div>

        <div class="plan-wrap">
            <canvas id="canvasLineas" width="<?= CANVAS_WIDTH; ?>" height="<?= CANVAS_HEIGHT; ?>"
                    style="border-style:solid;border-width:1px;border-color:var(--mordor-humo);"></canvas>
        </div>

        <div id="nombres_lineas_capa" class="mt-3 flex flex-col gap-1"></div>

        <div class="mt-4 flex flex-wrap gap-2 items-center">
            <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="TrazadorGuardar()">Guardar líneas</button>
            <a href="javascript:;" data-dismiss="modal" onclick="TrazadorCerrar()" class="button text-white bg-theme-6 shadow-md">Cancelar</a>
        </div>
    </div>
</div>
