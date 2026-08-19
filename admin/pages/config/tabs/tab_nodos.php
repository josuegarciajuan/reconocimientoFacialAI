<?php
/* La Forja · Tab Nodos (sabor: Cadenas): crear nodos + eliminar nodos.
 * Los nodos se marcan haciendo clic sobre el lienzo (canvasID, en edit.php).
 * Sub-acciones: Unir (crear) / Romper (eliminar) — resueltas en $sub.
 * Variable disponible: $camaras.
 */
?>

<!-- ---------- Submenú de la pestaña ---------- -->
<div class="forge-submenu" role="tablist" aria-label="Acciones de nodos">
    <a role="tab" aria-selected="<?= $sub === "crear" ? "true" : "false"; ?>"
       class="forge-sub<?= $sub === "crear" ? " is-active" : ""; ?>"
       href="?page=config&tab=nodos&sub=crear" data-lore="unir-nodos">Unir</a>
    <a role="tab" aria-selected="<?= $sub === "editar" ? "true" : "false"; ?>"
       class="forge-sub<?= $sub === "editar" ? " is-active" : ""; ?>"
       href="?page=config&tab=nodos&sub=editar" data-lore="mover-nodos">Mover</a>
    <a role="tab" aria-selected="<?= $sub === "eliminar" ? "true" : "false"; ?>"
       class="forge-sub<?= $sub === "eliminar" ? " is-active" : ""; ?>"
       href="?page=config&tab=nodos&sub=eliminar" data-lore="romper">Romper</a>
</div>

<?php if ($sub === "eliminar"): ?>
<!-- ---------- Romper (eliminar nodos) ---------- -->
<div class="form-section" data-panel-forge="eliminar">
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
        <div>
            <label for="camino_el" class="field-label">Camino</label>
            <select id="camino_el" name="camino_el" class="input border w-full">
                <option value="0">Principal (0)</option>
                <option value="1">Alternativo 1</option>
                <option value="2">Alternativo 2</option>
            </select>
        </div>
        <div class="form-grid__full">
            <button type="button" class="button text-white bg-theme-6 shadow-md" onclick="eliminar_nodos()">Eliminar nodos</button>
        </div>
    </div>
</div>

<?php elseif ($sub === "editar"): ?>
<!-- ---------- Mover (editar nodos individuales) ---------- -->
<div class="form-section" data-panel-forge="editar">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">✋</span>
        Mover nodos
    </div>

    <div class="form-grid">
        <div>
            <label for="camara1_ed" class="field-label">Cámara (1)</label>
            <select id="camara1_ed" name="camara1_ed" class="input border w-full">
                <option value="-">Selecciona Cámara</option>
                <?php foreach ($camaras as $c): ?>
                    <option value="<?= (int)$c["id"]; ?>"><?= htmlspecialchars($c["descripcion"]); ?></option>
                <?php endforeach; ?>
            </select>
        </div>
        <div>
            <label for="camara2_ed" class="field-label">Cámara (2)</label>
            <select id="camara2_ed" name="camara2_ed" class="input border w-full">
                <option value="-">Selecciona Cámara</option>
                <?php foreach ($camaras as $c): ?>
                    <option value="<?= (int)$c["id"]; ?>"><?= htmlspecialchars($c["descripcion"]); ?></option>
                <?php endforeach; ?>
            </select>
        </div>
        <div>
            <label for="camino_ed" class="field-label">Camino</label>
            <select id="camino_ed" name="camino_ed" class="input border w-full">
                <option value="0">Principal (0)</option>
                <option value="1">Alternativo 1</option>
                <option value="2">Alternativo 2</option>
            </select>
        </div>
        <div class="form-grid__full">
            <div class="flex flex-col sm:flex-row sm:items-center gap-2">
                <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="ForgeCargarEditar()">Cargar camino</button>
                <span class="text-xs text-gray-500 dark:text-gray-600">
                    Carga el camino y arrastra sus nodos para recolocarlos. Clic derecho sobre un nodo para eliminarlo.
                </span>
            </div>
        </div>
    </div>
</div>

<?php else: ?>
<!-- ---------- Unir (crear nodos) ---------- -->
<div class="form-section" data-panel-forge="crear">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">🔗</span>
        Crear nodos
    </div>

    <div class="form-grid">
        <div>
            <label for="camara1" class="field-label">Cámara (1)</label>
            <select id="camara1" name="camara1" class="input border w-full">
                <option value="-">Selecciona Cámara</option>
                <?php foreach ($camaras as $c): ?>
                    <option value="<?= (int)$c["id"]; ?>"><?= htmlspecialchars($c["descripcion"]); ?></option>
                <?php endforeach; ?>
            </select>
        </div>
        <div>
            <label for="camara2" class="field-label">Cámara (2)</label>
            <select id="camara2" name="camara2" class="input border w-full">
                <option value="-">Selecciona Cámara</option>
                <?php foreach ($camaras as $c): ?>
                    <option value="<?= (int)$c["id"]; ?>"><?= htmlspecialchars($c["descripcion"]); ?></option>
                <?php endforeach; ?>
            </select>
        </div>
        <div>
            <label for="camino" class="field-label">Camino</label>
            <select id="camino" name="camino" class="input border w-full">
                <option value="0">Principal (0)</option>
                <option value="1">Alternativo 1</option>
                <option value="2">Alternativo 2</option>
            </select>
        </div>
        <div class="form-grid__full">
            <div class="flex flex-col sm:flex-row sm:items-center gap-2">
                <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="guardar_nodos()">Guardar nodos</button>
                <span class="text-xs text-gray-500 dark:text-gray-600">
                    Selecciona ambas cámaras (y el camino) y haz clic en el lienzo para marcar cada nodo.
                </span>
            </div>
        </div>
    </div>
</div>
<?php endif; ?>
