<?php
/* La Forja · Tab Líneas (sabor: Trazos): trazar líneas (sobre la foto de una cámara) + corregir líneas.
 * Al elegir cámara, el lienzo (canvasID) se sustituye por la foto capturada sin recargar la página.
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
<!-- ---------- Corregir (editar líneas) ---------- -->
<div class="form-section" data-panel-forge="editar">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">✏️</span>
        Editar líneas
    </div>

    <div class="form-grid">
        <div class="form-grid__full">
            <label for="editar_linea" class="field-label">Línea a editar</label>
            <select id="editar_linea" name="editar_linea" class="input border w-full" onchange="ForgeCargarFotoLinea(this.value)">
                <option value="-">Selecciona Línea</option>
                <?php foreach ($lineas_edit as $l): ?>
                    <option <?php if (isset($_GET["editar_linea"]) && $_GET["editar_linea"] == $l["id"] . "-" . $l["camara_id"]) { echo "selected='selected'"; } ?> value="<?= (int)$l["id"]; ?>-<?= (int)$l["camara_id"]; ?>"><?= htmlspecialchars($l["nombre"] . " - " . $l["descripcion"]); ?></option>
                <?php endforeach; ?>
            </select>
            <p class="text-xs text-gray-500 dark:text-gray-600 mt-2">
                Al elegir la línea, el lienzo muestra la foto de su cámara. Haz clic para reposicionar y guarda los cambios.
            </p>
        </div>
        <div class="form-grid__full">
            <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="editar_linea1()">Guardar cambios</button>
        </div>
    </div>
</div>

<?php else: ?>
<!-- ---------- Trazar (crear líneas) ---------- -->
<div class="form-section" data-panel-forge="trazar">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">📏</span>
        Líneas
    </div>

    <div class="form-grid">
        <div class="form-grid__full">
            <label for="camara1_linea" class="field-label">Cámara</label>
            <select id="camara1_linea" name="camara1_linea" class="input border w-full" onchange="ForgeCargarFotoCamara(this.value)">
                <option value="-">Selecciona Cámara</option>
                <?php foreach ($camaras as $c): ?>
                    <option <?php if (isset($_GET["mostrar_foto"]) && $_GET["mostrar_foto"] == $c["id"]) { echo "selected='selected'"; } ?> value="<?= (int)$c["id"]; ?>"><?= htmlspecialchars($c["descripcion"]); ?></option>
                <?php endforeach; ?>
            </select>
            <p class="text-xs text-gray-500 dark:text-gray-600 mt-2">
                Selecciona la cámara para capturar su foto y trazar líneas sobre el lienzo. Dos clics por línea: inicio y fin.
            </p>
        </div>

        <div id="nombres_lineas_capa" class="form-grid__full">
        </div>

        <div class="form-grid__full">
            <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="guardar_lineas()">Guardar líneas</button>
        </div>
    </div>
</div>
<?php endif; ?>
