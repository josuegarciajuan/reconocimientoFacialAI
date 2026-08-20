<?php
/* La Forja · Tab Cámaras (sabor: Forjar).
 * Sub-acciones: Forjar (crear) / Editar (datos + parámetros de análisis) /
 * Templar (calibrador guiado) — resueltas en $sub.
 *
 * 2026-08-20:
 *  - Submenú de 3 pasos; "Templar" pasa a ser el calibrador guiado.
 *  - Form "Editar" reorganizado por dominios (movimiento/rendimiento/almacenamiento)
 *    con botón ↺ por campo (restaurar a fábrica) y badges de recomendación del probe.
 *  - Vista "Templar": calibrador con stream anotado en vivo + rituales + restaurar.
 *
 * Variables disponibles: $camaras, $camara_sel, $cfg, $puerta_sel, $salida_sel,
 * $encendida_sel y la función rf_cfg_select_rango() (edit.php).
 */
require_once __DIR__ . "/../../../../libs/etiquetas.php";
require_once __DIR__ . "/../../../../libs/calibracion.php";

$calib_params = calib_parametros();
$reco_cam = $camara_sel ? calib_recomendaciones_camara((int) $camara_sel["id"]) : [];

/* Globales RF_* mostrados en "Configuración general" (fábrica = default del código). */
$globales_ui = [
    "RF_MOV_THRESHOLD"    => ["label" => "Umbral de movimiento", "factory" => "21", "desc" => "Diferencia de píxel para contar movimiento (absdiff)."],
    "RF_MOV_BLUR"         => ["label" => "Blur de movimiento", "factory" => "21", "desc" => "Kernel GaussianBlur aplicado antes del umbral."],
    "RF_MOV_DILATE"       => ["label" => "Dilate de movimiento", "factory" => "2", "desc" => "Iteraciones de dilate para unir el contorno."],
    "RF_DET_SIZE"         => ["label" => "Resolución de detección de cara", "factory" => "1280", "desc" => "det_size del detector RetinaFace sobre el frame completo."],
    "RF_MIN_SHARPNESS"    => ["label" => "Nitidez mínima de cara", "factory" => "55", "desc" => "Varianza de Laplaciano mínima para considerar la cara aprovechable."],
    "RF_SR_EMBED_MIN_FACE"=> ["label" => "Cara mínima para SR antes de embedding", "factory" => "96", "desc" => "Caras con lado mayor menor que esto se super-resuelven antes del embedding."],
    "RF_FACE_EVERY"       => ["label" => "Muestreo de caras en procesa_video", "factory" => "2", "desc" => "Analiza 1 de cada N frames en los vídeos archivados."],
    "RF_VIDEO_SEG_ANTES"  => ["label" => "Pre-roll de vídeo", "factory" => "2", "desc" => "Segundos previos al movimiento que se incluyen en el clip."],
    "RF_VIDEO_SEG_DESPUES"=> ["label" => "Post-roll de vídeo", "factory" => "2", "desc" => "Segundos posteriores al movimiento que se incluyen en el clip."],
];
$reco_glob = $camara_sel ? calib_recomendaciones((int) $camara_sel["id"]) : [];

/* Modo/cámara preseleccionados en Templar. */
$calib_modo = (($_GET["modo"] ?? "") === "general") ? "general" : "camara";
$calib_camara_sel = (int) ($_GET["camara"] ?? 0);
?>

<!-- ---------- Submenú de la pestaña ---------- -->
<div class="forge-submenu" role="tablist" aria-label="Acciones de cámaras">
    <a role="tab" aria-selected="<?= $sub === "crear" ? "true" : "false"; ?>"
       class="forge-sub<?= $sub === "crear" ? " is-active" : ""; ?>"
       href="?page=config&tab=camaras&sub=crear" data-lore="forjar">Forjar</a>
    <a role="tab" aria-selected="<?= $sub === "editar" ? "true" : "false"; ?>"
       class="forge-sub<?= $sub === "editar" ? " is-active" : ""; ?>"
       href="?page=config&tab=camaras&sub=editar" data-lore="editar">Editar</a>
    <a role="tab" aria-selected="<?= $sub === "calibrar" ? "true" : "false"; ?>"
       class="forge-sub<?= $sub === "calibrar" ? " is-active" : ""; ?>"
       href="?page=config&tab=camaras&sub=calibrar" data-lore="templar">Templar</a>
</div>

<?php if ($sub === "editar"): ?>
<!-- ================= Templar · Editar cámara ================= -->
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

    <!-- ---------- Parámetros de análisis (agrupados por dominio) ---------- -->
    <div class="form-section__title mt-6">
        <span class="form-section__emoji" aria-hidden="true">⚙️</span>
        Parámetros de análisis
    </div>
    <p class="text-xs text-gray-500 dark:text-gray-600 mb-4">
        Parámetros que aplica el motor a la cámara seleccionada. El «↺» restaura ese campo a su
        valor de fábrica. Los badges <span style="color:#2e9e44">recomendado</span> llegan del
        calibrador guiado (<a href="?page=config&tab=camaras&sub=calibrar&camara=<?= (int)($camara_sel["id"] ?? 0); ?>" class="underline">Templar</a>).
    </p>

    <?php
    $dominios_ui = [
        "movimiento"   => ["🎯", "Movimiento", "Cómo decide el centinela que hay movimiento (dispara la grabación)."],
        "rendimiento"  => ["⚡", "Rendimiento", "Cadencia y escala de análisis: más exigente = más CPU."],
        "almacenamiento" => ["💾", "Almacenamiento", "Cuánto ocupa cada clip de movimiento."],
    ];
    foreach ($dominios_ui as $dom => $d): ?>
        <div class="form-section__title mt-4" style="font-size:0.9rem">
            <span class="form-section__emoji" aria-hidden="true"><?= $d[0]; ?></span>
            <?= htmlspecialchars($d[1]); ?>
        </div>
        <p class="text-xs text-gray-500 dark:text-gray-600 mb-2"><?= htmlspecialchars($d[2]); ?></p>
        <div class="form-grid">
            <?php foreach ($calib_params as $k => $meta): if ($meta["dominio"] !== $dom) { continue; } ?>
                <?php $tiene_reco = isset($reco_cam[$k]); ?>
                <div>
                    <label for="<?= $k; ?>" class="field-label">
                        <?= htmlspecialchars($meta["label"]); ?>
                        <?php if ($tiene_reco): ?>
                            <a href="?page=config&tab=camaras&sub=editar&accion=calibrar_aplicar&camara=<?= (int)$camara_sel["id"]; ?>&parametro=<?= $k; ?>"
                               class="rf-badge" style="color:#2e9e44;font-weight:600" title="Aplicar recomendación del calibrador">
                                recomendado: <?= (int)$reco_cam[$k]["recomendado"]; ?> ⚡
                            </a>
                        <?php endif; ?>
                    </label>
                    <div class="flex items-center gap-2">
                        <select name="<?= $k; ?>" id="<?= $k; ?>" class="input border w-full" data-default="<?= (int)$meta["factory"]; ?>">
                            <?= rf_cfg_select_rango((int)$meta["rango"][0], (int)$meta["rango"][1], $cfg[$k]); ?>
                        </select>
                        <button type="button" class="button button--sm bg-gray-700 text-white"
                                onclick="RestaurarCampo('<?= $k; ?>')" title="Restaurar a fábrica (<?= (int)$meta["factory"]; ?>)">↺</button>
                    </div>
                    <p class="text-xs text-gray-500 dark:text-gray-600 mt-1"><?= htmlspecialchars($meta["lore"]); ?></p>
                    <?php if ($tiene_reco && !empty($reco_cam[$k]["motivo"])): ?>
                        <p class="text-xs mt-1" style="color:#2e9e44">💡 <?= htmlspecialchars($reco_cam[$k]["motivo"]); ?></p>
                    <?php endif; ?>
                </div>
            <?php endforeach; ?>
        </div>
    <?php endforeach; ?>

    <div class="mt-4 flex flex-wrap gap-x-4 gap-y-2 items-center">
        <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="guardar()">Guardar cámara</button>
        <button type="button" class="button text-white bg-theme-6 shadow-md" onclick="RestaurarFabrica()">Restaurar valores de fábrica</button>
        <?php if ($camara_sel): ?>
            <a href="?page=config&tab=camaras&sub=calibrar&camara=<?= (int)$camara_sel["id"]; ?>"
               class="button text-white bg-theme-2 shadow-md">Ir a Templar →</a>
        <?php endif; ?>
        <span class="text-xs text-gray-500 dark:text-gray-600" data-lore="posicion-yunque">
            La posición (X/Y) se ajusta arrastrando la cámara en «El Yunque».
        </span>
    </div>
</div>

<?php elseif ($sub === "calibrar"): ?>
<!-- ================= Templar · Calibrador guiado ================= -->
<div class="form-section" data-panel-forge="calibrar">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">🔧</span>
        Templar · Calibrador guiado
    </div>
    <p class="text-xs text-gray-500 dark:text-gray-600 mb-4">
        Cada ritual mide la cámara <b>en vivo</b> con el mismo código de producción y propone
        valores con su motivo. Nada se aplica sin tu confirmación: revisa la recomendación y pulsa
        «Aplicar» o descártala. También puedes ejecutar solo el ritual que te interese.
    </p>

    <div class="form-grid">
        <div>
            <span class="field-label">Modo</span>
            <div class="flex flex-wrap gap-x-4 gap-y-2 items-center">
                <label class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                    <input type="radio" name="calib_modo" value="camara" style="accent-color:var(--mordor-oro)"
                           <?= $calib_modo === "camara" ? "checked" : ""; ?> onchange="TemplarModo()"> Esta cámara
                </label>
                <label class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400">
                    <input type="radio" name="calib_modo" value="general" style="accent-color:var(--mordor-oro)"
                           <?= $calib_modo === "general" ? "checked" : ""; ?> onchange="TemplarModo()"> Configuración general
                </label>
            </div>
        </div>
        <div id="calibCamaraWrap">
            <label for="calib_camara" class="field-label">Cámara</label>
            <select id="calib_camara" name="calib_camara" class="input border w-full">
                <?php foreach ($camaras as $c): ?>
                    <option value="<?= (int)$c["id"]; ?>" <?= ($calib_camara_sel === (int)$c["id"]) ? "selected" : ""; ?>><?= htmlspecialchars(camara_label($c["descripcion"])); ?></option>
                <?php endforeach; ?>
            </select>
        </div>
        <div id="calibSegundosWrap">
            <label for="calib_segundos" class="field-label">Duración del ritual (s)</label>
            <input type="number" id="calib_segundos" name="calib_segundos" value="20" min="5" max="60" class="input border w-full">
        </div>
    </div>

    <!-- ---- Modo "Esta cámara" ---- -->
    <div id="calibPanelCamara" <?= $calib_modo === "general" ? 'style="display:none"' : ""; ?>>
        <div class="form-section__title mt-6">
            <span class="form-section__emoji" aria-hidden="true">📹</span>
            Vista del probe (en vivo)
        </div>
        <div class="flex flex-wrap gap-4 mt-2">
            <div class="calib-live" style="position:relative;flex:1 1 420px;min-width:320px">
                <img id="calibImg" src="" alt="Vista del calibrador"
                     style="width:100%;border-radius:8px;border:1px solid #333;background:#000">
                <div id="calibEstadoRitual" class="text-xs mt-2" style="color:#9a9a9a">
                    Elige un ritual y pulsa «Iniciar».
                </div>
            </div>
            <div style="flex:1 1 280px;min-width:240px">
                <div class="form-section__title" style="font-size:0.9rem">
                    <span class="form-section__emoji" aria-hidden="true">📊</span> Métricas en vivo
                </div>
                <div id="calibMetrics" class="text-xs mt-2" style="line-height:1.7">
                    — sin datos todavía —
                </div>
            </div>
        </div>

        <div class="form-section__title mt-6">
            <span class="form-section__emoji" aria-hidden="true">🧪</span> Rituales
        </div>
        <div class="flex flex-wrap gap-2 mt-2">
            <button type="button" class="button text-white bg-theme-2 shadow-md calib-ritual" data-ritual="A"
                    title="Mide a qué distancias/tamaños se detecta la cara">A · Alcance (detección de cara)</button>
            <button type="button" class="button text-white bg-theme-2 shadow-md calib-ritual" data-ritual="B"
                    title="Pasa rápido delante de la cámara: comprueba que el movimiento/captura no se pierde">B · Paso veloz (FPS)</button>
        </div>

        <div class="form-section__title mt-6">
            <span class="form-section__emoji" aria-hidden="true">📋</span> Recomendación
        </div>
        <div id="calibRecomendaciones" class="text-xs mt-2" style="line-height:1.7">
            — ejecuta un ritual para obtener una recomendación —
        </div>

        <div class="mt-4 flex flex-wrap gap-x-4 gap-y-2 items-center">
            <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="TemplarIniciar()">▶ Iniciar ritual</button>
            <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="TemplarAplicar()">Aplicar recomendación</button>
            <button type="button" class="button text-white bg-theme-6 shadow-md" onclick="TemplarRestaurarFabrica()">Restaurar valores de fábrica</button>
        </div>
    </div>

    <!-- ---- Modo "Configuración general" ---- -->
    <div id="calibPanelGeneral" <?= $calib_modo === "general" ? "" : 'style="display:none"'; ?>>
        <div class="form-section__title mt-6">
            <span class="form-section__emoji" aria-hidden="true">🌐</span> Parámetros globales del algoritmo
        </div>
        <p class="text-xs text-gray-500 dark:text-gray-600 mb-2">
            Valores del <code>.env</code> (fuera de git). El «↺» borra la línea para que aplique el
            default del código (fábrica). Los rituales del modo «Esta cámara» también pueden
            recomendar valores globales (RF_*) aquí.
        </p>
        <div class="overflow-x-auto">
            <table class="w-full text-xs">
                <thead>
                    <tr style="text-align:left;border-bottom:1px solid #333">
                        <th class="p-2">Parámetro</th><th class="p-2">Actual</th><th class="p-2">Fábrica</th><th class="p-2">Descripción</th><th class="p-2"></th>
                    </tr>
                </thead>
                <tbody>
                    <?php foreach ($globales_ui as $k => $g):
                        $v_env = getenv($k);
                        $actual = ($v_env !== false && $v_env !== "") ? $v_env : ("default (" . $g["factory"] . ")");
                        $tiene_reco = isset($reco_glob[$k]); ?>
                        <tr style="border-bottom:1px solid #2a2a2a">
                            <td class="p-2" style="font-family:monospace"><?= $k; ?>
                                <?php if ($tiene_reco): ?>
                                    <span style="color:#2e9e44;font-weight:600" title="Recomendado por el calibrador">· recomendado: <?= htmlspecialchars((string)$reco_glob[$k]["recomendado"]); ?></span>
                                <?php endif; ?>
                            </td>
                            <td class="p-2" style="font-family:monospace"><?= htmlspecialchars((string)$actual); ?></td>
                            <td class="p-2" style="font-family:monospace"><?= htmlspecialchars($g["factory"]); ?></td>
                            <td class="p-2"><?= htmlspecialchars($g["desc"]); ?></td>
                            <td class="p-2">
                                <a href="?page=config&tab=camaras&sub=calibrar&accion=calibrar_restaurar_global&parametro=<?= $k; ?>&modo=general"
                                   class="button button--sm bg-gray-700 text-white" title="Restaurar a fábrica">↺</a>
                            </td>
                        </tr>
                    <?php endforeach; ?>
                </tbody>
            </table>
        </div>
        <div class="mt-4 flex flex-wrap gap-x-4 gap-y-2 items-center">
            <a href="?page=config&tab=camaras&sub=calibrar&accion=calibrar_restaurar_globales&modo=general"
               class="button text-white bg-theme-6 shadow-md">Restaurar todos los globales</a>
            <?php if ($camara_sel): ?>
                <a href="?page=config&tab=camaras&sub=calibrar&accion=calibrar_aplicar_global&camara=<?= (int)$camara_sel["id"]; ?>&modo=general"
                   class="button text-white bg-theme-1 shadow-md" title="Aplica las recomendaciones RF_* pendientes (de los rituales) al .env">Aplicar recomendaciones globales</a>
            <?php endif; ?>
            <span class="text-xs text-gray-500 dark:text-gray-600">
                Los barridos offline (matching/cruces/face_every) llegarán en la Fase 2 del calibrador.
            </span>
        </div>
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
