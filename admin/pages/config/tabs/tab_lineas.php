<?php
/* La Forja · Tab Líneas (sabor: Trazos): trazar líneas (sobre la foto de una cámara) + corregir líneas.
 * Al elegir cámara, el lienzo (canvasID) se sustituye por la foto capturada sin recargar la página.
 * Sub-acciones: Trazar (crear) / Corregir (editar) / Plano (líneas dibujadas sobre el plano) — resueltas en $sub.
 * Variables disponibles: $camaras, $lineas_edit, $lineas_plano.
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
    <a role="tab" aria-selected="<?= $sub === "plano" ? "true" : "false"; ?>"
       class="forge-sub<?= $sub === "plano" ? " is-active" : ""; ?>"
       href="?page=config&tab=lineas&sub=plano" data-lore="trazos-plano">Plano</a>
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

<?php elseif ($sub === "plano"): ?>
<!-- ---------- Líneas del plano (independientes de los triples de foto) ---------- -->
<div class="form-section" data-panel-forge="plano">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">📐</span>
        Líneas del plano
    </div>

    <div class="form-grid">
        <div class="form-grid__full">
            <label for="filtro_camara_plano" class="field-label">Filtrar por cámara</label>
            <select id="filtro_camara_plano" name="filtro_camara_plano" class="input border w-full" onchange="ForgeLineasPlanoFiltro()">
                <option value="-">Todas</option>
                <?php foreach ($camaras as $c): ?>
                    <option value="<?= (int)$c["id"]; ?>"><?= htmlspecialchars($c["descripcion"]); ?></option>
                <?php endforeach; ?>
            </select>
        </div>

        <div class="form-grid__full">
            <span class="field-label">Líneas creadas</span>
            <div id="lineas_plano_lista" class="forge-lineas-plano">
                <?php if (!$lineas_plano): ?>
                    <p class="text-xs text-gray-500 dark:text-gray-600">Aún no hay líneas en el plano. Crea la primera abajo.</p>
                <?php else: ?>
                    <?php foreach ($lineas_plano as $lp): ?>
                        <div class="forge-linea-plano" data-id="<?= (int)$lp["id"]; ?>">
                            <button type="button" class="forge-linea-plano__boton" data-lp-id="<?= (int)$lp["id"]; ?>"
                                    onclick="ForgeLineaPlanoSeleccionar(<?= (int)$lp["id"]; ?>)">
                                <span class="forge-linea-plano__nombre"><?= htmlspecialchars($lp["nombre"]); ?></span>
                                <span class="forge-linea-plano__camara"><?= htmlspecialchars($lp["camara_nombre"] ?? "—"); ?></span>
                            </button>
                            <a href="javascript:;" class="forge-linea-plano__borrar" title="Borrar línea del plano"
                               onclick="ForgeLineaPlanoBorrar(<?= (int)$lp["id"]; ?>)">(X)</a>
                        </div>
                    <?php endforeach; ?>
                <?php endif; ?>
            </div>
            <p class="text-xs text-gray-500 dark:text-gray-600 mt-2">
                Al pulsar una línea, aparece marcada en el plano junto a su cámara. Puedes redibujarla o borrarla.
            </p>
        </div>
    </div>

    <div class="form-section__title mt-6">
        <span class="form-section__emoji" aria-hidden="true">✏️</span>
        Dibujar línea en el plano
    </div>

    <div class="form-grid">
        <div>
            <label for="nombre_linea_plano" class="field-label">Nombre</label>
            <input type="text" name="nombre_linea_plano" id="nombre_linea_plano" class="input border w-full" placeholder="Nombre de la línea">
        </div>
        <div>
            <label for="camara_linea_plano" class="field-label">Cámara</label>
            <select name="camara_linea_plano" id="camara_linea_plano" class="input border w-full">
                <option value="-">Selecciona Cámara</option>
                <?php foreach ($camaras as $c): ?>
                    <option value="<?= (int)$c["id"]; ?>"><?= htmlspecialchars($c["descripcion"]); ?></option>
                <?php endforeach; ?>
            </select>
        </div>
        <div class="form-grid__full">
            <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="ForgeLineaPlanoNueva()">Dibujar en el plano</button>
            <button type="button" class="button text-white bg-theme-2 shadow-md" id="btn_linea_plano_redibujar" onclick="ForgeLineaPlanoRedibujar()">Redibujar seleccionada</button>
        </div>
        <div class="form-grid__full">
            <p class="text-xs text-gray-500 dark:text-gray-600" id="hint_linea_plano">
                Escribe el nombre, elige la cámara y pulsa «Dibujar en el plano»: dos clics en el lienzo (inicio y fin) crean la línea. Luego arrastra sus extremos para ajustarla.
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
