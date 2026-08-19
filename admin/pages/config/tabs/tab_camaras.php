<?php
/* La Forja · Tab Cámaras: crear cámara + editar cámara (con parámetros de análisis).
 * El lienzo de trabajo (canvasID) vive en edit.php, siempre visible.
 * Variables disponibles: $camaras, $camara_sel, $cfg, $puerta_sel, $salida_sel,
 * $encendida_sel, $sistema_sel y la función rf_cfg_select_rango() (edit.php).
 */
?>

<!-- ---------- Crear cámara ---------- -->
<div class="form-section">
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
            <label for="url_conexion_nueva" class="field-label">URL de conexión / ID cámara local</label>
            <input type="text" name="url_conexion_nueva" id="url_conexion_nueva" class="input border w-full" placeholder="Url conexion / id camara local">
        </div>
        <div>
            <label for="ipcamlive_alias" class="field-label">Alias IPCamlive</label>
            <input type="text" name="ipcamlive_alias" id="ipcamlive_alias" class="input border w-full" placeholder="ipcamlive_alias">
        </div>

        <div>
            <span class="field-label">Tipo de acceso</span>
            <div class="flex flex-wrap gap-x-4 gap-y-2 items-center">
                <label for="entrada1" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400" data-lore="puerta-camara">
                    <input type="radio" name="eos1" id="entrada1" value="entrada" style="accent-color:var(--mordor-oro)"> Puerta
                </label>
                <label for="salida1" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400" data-lore="salida-camara">
                    <input type="radio" name="eos1" id="salida1" value="salida" style="accent-color:var(--mordor-oro)"> Salida
                </label>
            </div>
        </div>

        <div>
            <span class="field-label">Estado</span>
            <label for="encendida_nueva" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400" data-lore="encendida">
                <input type="checkbox" name="encendida_nueva" id="encendida_nueva" value="1" style="accent-color:var(--mordor-oro)"> Encendida
            </label>
        </div>

        <div>
            <span class="field-label">Origen de vídeo</span>
            <div class="flex flex-wrap gap-x-4 gap-y-2 items-center">
                <label for="tipo_camara_ip" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                    <input type="radio" name="tipo_camara" id="tipo_camara_ip" value="ip" style="accent-color:var(--mordor-oro)"> Cámara IP
                </label>
                <label for="tipo_camara_grabador" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                    <input type="radio" name="tipo_camara" id="tipo_camara_grabador" value="grabador" style="accent-color:var(--mordor-oro)"> Grabador
                </label>
            </div>
        </div>

        <div class="form-grid__full">
            <span class="field-label">Posición en el plano</span>
            <div class="flex flex-wrap gap-x-4 gap-y-2 items-center">
                <div class="flex items-center gap-2">
                    <label for="x_nueva" class="text-sm text-gray-600 dark:text-gray-400">X</label>
                    <input type="text" name="x_nueva" id="x_nueva" class="input border w-24" readonly placeholder="X">
                </div>
                <div class="flex items-center gap-2">
                    <label for="y_nueva" class="text-sm text-gray-600 dark:text-gray-400">Y</label>
                    <input type="text" name="y_nueva" id="y_nueva" class="input border w-24" readonly placeholder="Y">
                </div>
                <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="crear()">Crear cámara</button>
            </div>
        </div>
    </div>
</div>

<!-- ---------- Editar cámara ---------- -->
<div class="form-section">
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
                    <option <?php if (isset($_GET["camara"]) && $_GET["camara"] == $c["id"]) { echo "selected='selected'"; } ?> value="<?= (int)$c["id"]; ?>"><?= htmlspecialchars($c["descripcion"]); ?></option>
                <?php endforeach; ?>
            </select>
        </div>

        <div>
            <label for="nombre" class="field-label">Descripción</label>
            <input type="text" name="nombre" id="nombre" class="input border w-full" placeholder="Descripción" value="<?= htmlspecialchars($camara_sel["descripcion"] ?? ""); ?>">
        </div>
        <div>
            <label for="url_conexion" class="field-label">URL de conexión</label>
            <input type="text" name="url_conexion" id="url_conexion" class="input border w-full" placeholder="url_conexion" value="<?= htmlspecialchars($camara_sel["url_conexion"] ?? ""); ?>">
        </div>
        <div>
            <label for="url_desdeserver" class="field-label">URL desde servidor</label>
            <input type="text" name="url_desdeserver" id="url_desdeserver" class="input border w-full" placeholder="url_desdeserver" value="<?= htmlspecialchars($camara_sel["url_desdeserver"] ?? ""); ?>">
        </div>
        <div>
            <label for="ipcamlive_alias1" class="field-label">Alias IPCamlive</label>
            <input type="text" name="ipcamlive_alias1" id="ipcamlive_alias1" class="input border w-full" placeholder="ipcamlive_alias" value="<?= htmlspecialchars($camara_sel["ipcamlive_alias"] ?? ""); ?>">
        </div>

        <div>
            <span class="field-label">Tipo de acceso</span>
            <div class="flex flex-wrap gap-x-4 gap-y-2 items-center">
                <label for="entrada2" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400" data-lore="puerta-camara">
                    <input type="radio" name="eos2" id="entrada2" value="entrada" style="accent-color:var(--mordor-oro)" <?= $puerta_sel === 1 ? "checked" : ""; ?>> Puerta
                </label>
                <label for="salida2" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400" data-lore="salida-camara">
                    <input type="radio" name="eos2" id="salida2" value="salida" style="accent-color:var(--mordor-oro)" <?= $salida_sel === 1 ? "checked" : ""; ?>> Salida
                </label>
            </div>
        </div>

        <div>
            <span class="field-label">Estado</span>
            <label for="encendida" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400" data-lore="encendida">
                <input type="checkbox" name="encendida" id="encendida" value="1" style="accent-color:var(--mordor-oro)" <?= $encendida_sel === 1 ? "checked" : ""; ?>> Encendida
            </label>
        </div>

        <div>
            <span class="field-label">Origen de vídeo</span>
            <div class="flex flex-wrap gap-x-4 gap-y-2 items-center">
                <label for="tipo_camara_ip_ed" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                    <input type="radio" name="tipo_camara_ed" id="tipo_camara_ip_ed" value="ip" style="accent-color:var(--mordor-oro)" <?= $sistema_sel === 0 ? "checked" : ""; ?>> Cámara IP
                </label>
                <label for="tipo_camara_grabador_ed" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                    <input type="radio" name="tipo_camara_ed" id="tipo_camara_grabador_ed" value="grabador" style="accent-color:var(--mordor-oro)" <?= $sistema_sel === 1 ? "checked" : ""; ?>> Grabador
                </label>
            </div>
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
        <div class="flex items-center gap-2">
            <label for="x_camara" class="text-sm text-gray-600 dark:text-gray-400">X</label>
            <input type="text" name="x_camara" id="x_camara" class="input border w-24" readonly placeholder="X" value="<?= htmlspecialchars($camara_sel["x"] ?? ""); ?>">
        </div>
        <div class="flex items-center gap-2">
            <label for="y_camara" class="text-sm text-gray-600 dark:text-gray-400">Y</label>
            <input type="text" name="y_camara" id="y_camara" class="input border w-24" readonly placeholder="Y" value="<?= htmlspecialchars($camara_sel["y"] ?? ""); ?>">
        </div>
        <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="guardar()">Guardar cámara</button>
    </div>
</div>
