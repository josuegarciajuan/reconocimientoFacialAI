<?php
/* La Forja · Tab Líneas: dibujar líneas (sobre la foto de una cámara) + editar líneas.
 * Al elegir cámara, el lienzo (canvasID) se sustituye por la foto capturada (mostrar_foto).
 * Variables disponibles: $camaras, $lineas_edit.
 */
?>

<!-- ---------- Líneas ---------- -->
<div class="form-section">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">📏</span>
        Líneas
    </div>

    <div class="form-grid">
        <div class="form-grid__full">
            <label for="camara1_linea" class="field-label">Cámara</label>
            <select id="camara1_linea" name="camara1_linea" class="input border w-full" onchange="carga_foto_camara()">
                <option value="-">Selecciona Cámara</option>
                <?php foreach ($camaras as $c): ?>
                    <option <?php if (isset($_GET["mostrar_foto"]) && $_GET["mostrar_foto"] == $c["id"]) { echo "selected='selected'"; } ?> value="<?= (int)$c["id"]; ?>"><?= htmlspecialchars($c["descripcion"]); ?></option>
                <?php endforeach; ?>
            </select>
            <p class="text-xs text-gray-500 dark:text-gray-600 mt-2">
                Selecciona la cámara para capturar su foto y dibujar líneas sobre el lienzo.
            </p>
        </div>

        <div id="nombres_lineas_capa" class="form-grid__full">
        </div>

        <div class="form-grid__full">
            <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="guardar_lineas()">Guardar líneas</button>
        </div>
    </div>
</div>

<!-- ---------- Editar líneas ---------- -->
<div class="form-section">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">✏️</span>
        Editar líneas
    </div>

    <div class="form-grid">
        <div class="form-grid__full">
            <label for="editar_linea" class="field-label">Línea a editar</label>
            <select id="editar_linea" name="editar_linea" class="input border w-full" onchange="carga_foto_linea()">
                <option value="-">Selecciona Línea</option>
                <?php foreach ($lineas_edit as $l): ?>
                    <option <?php if (isset($_GET["editar_linea"]) && $_GET["editar_linea"] == $l["id"] . "-" . $l["camara_id"]) { echo "selected='selected'"; } ?> value="<?= (int)$l["id"]; ?>-<?= (int)$l["camara_id"]; ?>"><?= htmlspecialchars($l["nombre"] . " - " . $l["descripcion"]); ?></option>
                <?php endforeach; ?>
            </select>
        </div>
        <div class="form-grid__full">
            <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="editar_linea1()">Guardar cambios</button>
        </div>
    </div>
</div>
