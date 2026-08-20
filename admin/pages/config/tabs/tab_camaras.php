<?php
/* La Forja · Tab Cámaras (sabor: Forjar): crear cámara + editar cámara.
 * Sub-acciones: Forjar (crear) / Templar (editar) — resueltas en $sub.
 * Variables disponibles: $camaras, $camara_sel, $cfg, $puerta_sel, $salida_sel,
 * $encendida_sel y la función rf_cfg_select_rango() (edit.php).
 *
 * 2026-08-19: se retiran "Alias IPCamlive" y "Origen de vídeo" (no aportan).
 * La posición X/Y ya no se edita aquí: se fija arrastrando la cámara en El Yunque.
 */
require_once __DIR__ . "/../../../../libs/etiquetas.php";
?>

<!-- ---------- Submenú de la pestaña ---------- -->
<div class="forge-submenu" role="tablist" aria-label="Acciones de cámaras">
    <a role="tab" aria-selected="<?= $sub === "crear" ? "true" : "false"; ?>"
       class="forge-sub<?= $sub === "crear" ? " is-active" : ""; ?>"
       href="?page=config&tab=camaras&sub=crear" data-lore="forjar">Forjar</a>
    <a role="tab" aria-selected="<?= $sub === "editar" ? "true" : "false"; ?>"
       class="forge-sub<?= $sub === "editar" ? " is-active" : ""; ?>"
       href="?page=config&tab=camaras&sub=editar" data-lore="templar">Templar</a>
</div>

<?php if ($sub === "editar"): ?>
<!-- ---------- Templar (editar cámara) ---------- -->
<div class="form-section" data-panel-forge="editar">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">✏️</span>
        Editar cámara
    </div>

    <div class="form-grid">
        <div class="form-grid__full">
            <label for="camara" class="field-label">Cámara a editar</label>
            <select id="camara" name="camara" class="input border w-full" onchange="seleccionar_camara()">
                <option value="-" <?php if (!isset($_GET["camara"]) or $_GET["camara"] == "-") { echo "selected='selected'"; } ?>>Selecciona Cámara</option>
                <?php foreach ($camaras as $c): ?>
                    <option <?php if (isset($_GET["camara"]) && $_GET["camara"] == $c["id"]) { echo "selected='selected'"; } ?> value="<?= (int)$c["id"]; ?>"><?= htmlspecialchars(camara_label($c["descripcion"])); ?></option>
                <?php endforeach; ?>
            </select>
        </div>

        <div>
            <label for="nombre" class="field-label">Descripción</label>
            <input type="text" name="nombre" id="nombre" class="input border w-full" placeholder="Descripción" value="<?= htmlspecialchars($camara_sel["descripcion"] ?? ""); ?>">
        </div>
        <div>
            <label for="url_conexion" class="field-label" data-lore="url-conexion">URL de conexión</label>
            <input type="text" name="url_conexion" id="url_conexion" class="input border w-full" placeholder="url_conexion" value="<?= htmlspecialchars($camara_sel["url_conexion"] ?? ""); ?>">
        </div>
        <div>
            <label for="url_desdeserver" class="field-label">URL desde servidor</label>
            <input type="text" name="url_desdeserver" id="url_desdeserver" class="input border w-full" placeholder="url_desdeserver" value="<?= htmlspecialchars($camara_sel["url_desdeserver"] ?? ""); ?>">
        </div>

        <div>
            <span class="field-label">Tipo de acceso</span>
            <div class="flex flex-wrap gap-x-4 gap-y-2 items-center">
                <label for="entrada2" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400" data-lore="puerta-camara">
                    <input type="checkbox" name="eos2_puerta" id="entrada2" value="1" style="accent-color:var(--mordor-oro)" <?= $puerta_sel === 1 ? "checked" : ""; ?>> Puerta
                </label>
                <label for="salida2" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400" data-lore="salida-camara">
                    <input type="checkbox" name="eos2_salida" id="salida2" value="1" style="accent-color:var(--mordor-oro)" <?= $salida_sel === 1 ? "checked" : ""; ?>> Salida
                </label>
            </div>
            <p class="text-xs text-gray-500 dark:text-gray-600 mt-1" data-lore="puerta-y-salida">
                Puedes marcar ambas: la cámara será de entrada y salida a la vez.
            </p>
        </div>

        <div>
            <span class="field-label">Estado</span>
            <label for="encendida" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400" data-lore="encendida">
                <input type="checkbox" name="encendida" id="encendida" value="1" style="accent-color:var(--mordor-oro)" <?= $encendida_sel === 1 ? "checked" : ""; ?>> Encendida
            </label>
        </div>
    </div>

    <!-- ---------- Parámetros de análisis ---------- -->
    <div class="form-section__title mt-6">
        <span class="form-section__emoji" aria-hidden="true">⚙️</span>
        Parámetros de análisis
    </div>
    <p class="text-xs text-gray-500 dark:text-gray-600 mb-4">
        Parámetros que aplica el motor a la cámara seleccionada. Se guardan con el botón «Guardar cámara».
    </p>

    <div class="form-grid">
        <div>
            <label for="segundos_analizar" class="field-label">Segundos a analizar</label>
            <select name="segundos_analizar" id="segundos_analizar" class="input border w-full">
                <?= rf_cfg_select_rango(1, 10, $cfg["segundos_analizar"]); ?>
            </select>
        </div>
        <div>
            <label for="porcentaje_mov" class="field-label">Porcentaje de movimiento</label>
            <select name="porcentaje_mov" id="porcentaje_mov" class="input border w-full">
                <?= rf_cfg_select_rango(1, 100, $cfg["porcentaje_mov"]); ?>
            </select>
        </div>
        <div>
            <label for="dontCare" class="field-label">DontCare</label>
            <select name="dontCare" id="dontCare" class="input border w-full">
                <?= rf_cfg_select_rango(10, 2000, $cfg["dontCare"]); ?>
            </select>
        </div>
        <div>
            <label for="fps" class="field-label">FPS</label>
            <select name="fps" id="fps" class="input border w-full">
                <?= rf_cfg_select_rango(1, 30, $cfg["fps"]); ?>
            </select>
        </div>
        <div>
            <label for="maximo_videos" class="field-label">Máximo de vídeos</label>
            <select name="maximo_videos" id="maximo_videos" class="input border w-full">
                <?= rf_cfg_select_rango(20, 120, $cfg["maximo_videos"]); ?>
            </select>
        </div>
        <div>
            <label for="redimesionframe" class="field-label">Redimensionar frame</label>
            <select name="redimesionframe" id="redimesionframe" class="input border w-full">
                <?= rf_cfg_select_rango(1, 100, $cfg["redimesionframe"]); ?>
            </select>
        </div>
        <div>
            <label for="sensibilidad" class="field-label">Sensibilidad</label>
            <select name="sensibilidad" id="sensibilidad" class="input border w-full">
                <?= rf_cfg_select_rango(1, 15, $cfg["sensibilidad"]); ?>
            </select>
        </div>
    </div>

    <div class="mt-4 flex flex-wrap gap-x-4 gap-y-2 items-center">
        <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="guardar()">Guardar cámara</button>
        <span class="text-xs text-gray-500 dark:text-gray-600" data-lore="posicion-yunque">
            La posición (X/Y) se ajusta arrastrando la cámara en «El Yunque».
        </span>
    </div>
</div>

<?php else: ?>
<!-- ---------- Forjar (crear cámara) ---------- -->
<div class="form-section" data-panel-forge="crear">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">📷</span>
        Crear cámara
    </div>

    <div class="form-grid">
        <div>
            <label for="nombre_nueva" class="field-label">Descripción</label>
            <input type="text" name="nombre_nueva" id="nombre_nueva" class="input border w-full" placeholder="Descripción">
        </div>
        <div>
            <label for="url_conexion_nueva" class="field-label" data-lore="url-conexion">URL de conexión / ID cámara local</label>
            <input type="text" name="url_conexion_nueva" id="url_conexion_nueva" class="input border w-full" placeholder="Url conexion / id camara local">
        </div>

        <div>
            <span class="field-label">Tipo de acceso</span>
            <div class="flex flex-wrap gap-x-4 gap-y-2 items-center">
                <label for="entrada1" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400" data-lore="puerta-camara">
                    <input type="checkbox" name="eos1_puerta" id="entrada1" value="1" style="accent-color:var(--mordor-oro)"> Puerta
                </label>
                <label for="salida1" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400" data-lore="salida-camara">
                    <input type="checkbox" name="eos1_salida" id="salida1" value="1" style="accent-color:var(--mordor-oro)"> Salida
                </label>
            </div>
            <p class="text-xs text-gray-500 dark:text-gray-600 mt-1" data-lore="puerta-y-salida">
                Puedes marcar ambas: la cámara será de entrada y salida a la vez.
            </p>
        </div>

        <div>
            <span class="field-label">Estado</span>
            <label for="encendida_nueva" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400" data-lore="encendida">
                <input type="checkbox" name="encendida_nueva" id="encendida_nueva" value="1" style="accent-color:var(--mordor-oro)"> Encendida
            </label>
        </div>

        <div class="form-grid__full">
            <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="crear()">Crear cámara</button>
            <span class="text-xs text-gray-500 dark:text-gray-600 ml-2" data-lore="posicion-yunque">
                Al crearla quedará sin posición; arrástrala al plano en «El Yunque».
            </span>
        </div>
    </div>
</div>
<?php endif; ?>
