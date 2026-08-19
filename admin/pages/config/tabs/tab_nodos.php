<?php
/* La Forja · Tab Nodos: crear nodos + eliminar nodos.
 * Los nodos se marcan haciendo clic sobre el lienzo (canvasID, en edit.php).
 * Variable disponible: $camaras.
 */
?>

<!-- ---------- Crear nodos ---------- -->
<div class="form-section">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">🔗</span>
        Crear nodos
    </div>

    <div class="form-grid">
        <div>
            <label for="camara1" class="field-label">Cámara (1)</label>
            <select id="camara1" name="camara1" class="input border w-full" onchange="meter_nodos()">
                <option value="-">Selecciona Cámara</option>
                <?php foreach ($camaras as $c): ?>
                    <option value="<?= (int)$c["id"]; ?>"><?= htmlspecialchars($c["descripcion"]); ?></option>
                <?php endforeach; ?>
            </select>
        </div>
        <div>
            <label for="camara2" class="field-label">Cámara (2)</label>
            <select id="camara2" name="camara2" class="input border w-full" onchange="meter_nodos()">
                <option value="-">Selecciona Cámara</option>
                <?php foreach ($camaras as $c): ?>
                    <option value="<?= (int)$c["id"]; ?>"><?= htmlspecialchars($c["descripcion"]); ?></option>
                <?php endforeach; ?>
            </select>
        </div>
        <div class="form-grid__full">
            <div class="flex flex-col sm:flex-row sm:items-center gap-2">
                <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="guardar_nodos()">Guardar nodos</button>
                <span class="text-xs text-gray-500 dark:text-gray-600">
                    Selecciona ambas cámaras y haz clic en el lienzo para marcar cada nodo.
                </span>
            </div>
        </div>
    </div>
</div>

<!-- ---------- Eliminar nodos ---------- -->
<div class="form-section">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">🧹</span>
        Eliminar nodos
    </div>

    <div class="form-grid">
        <div>
            <label for="camara1_el" class="field-label">Cámara (1)</label>
            <select id="camara1_el" name="camara1_el" class="input border w-full">
                <option value="-">Selecciona Cámara</option>
                <?php foreach ($camaras as $c): ?>
                    <option value="<?= (int)$c["id"]; ?>"><?= htmlspecialchars($c["descripcion"]); ?></option>
                <?php endforeach; ?>
            </select>
        </div>
        <div>
            <label for="camara2_el" class="field-label">Cámara (2)</label>
            <select id="camara2_el" name="camara2_el" class="input border w-full">
                <option value="-">Selecciona Cámara</option>
                <?php foreach ($camaras as $c): ?>
                    <option value="<?= (int)$c["id"]; ?>"><?= htmlspecialchars($c["descripcion"]); ?></option>
                <?php endforeach; ?>
            </select>
        </div>
        <div class="form-grid__full">
            <button type="button" class="button text-white bg-theme-6 shadow-md" onclick="eliminar_nodos()">Eliminar nodos</button>
        </div>
    </div>
</div>
