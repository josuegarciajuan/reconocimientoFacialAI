<?php
/* La Forja · Tab Plano (El Yunque): pantalla central de disposición.
 *  - Plano grande central (canvasID) con cámaras, líneas y senderos.
 *  - Izquierda: subir imagen / dibujar croquis / elegir activo + modo senderos.
 *  - Derecha: cámaras fuera del plano (arrastrables) + líneas de la cámara seleccionada.
 * Variables disponibles: $plano_act_cfg, $plano_subida_cfg, $plano_dibujo_cfg.
 */
?>

<div class="grid grid-cols-12 gap-6 items-start">

    <!-- ================= Columna izquierda: plano + senderos ================= -->
    <div class="col-span-12 xl:col-span-3 min-w-0 space-y-4">

        <div class="form-section">
            <div class="form-section__title">
                <span class="form-section__emoji" aria-hidden="true">🗺️</span>
                Plano del local
            </div>

            <div class="rf-tabs" role="tablist" aria-label="Plano en uso">
                <a role="tab" aria-selected="<?= $plano_act_cfg === "subida" ? "true" : "false"; ?>"
                   class="rf-tab<?= $plano_act_cfg === "subida" ? " is-active" : ""; ?><?= !$plano_subida_cfg ? " is-empty" : ""; ?>"
                   href="?page=config&tab=plano&accion=plano_activo&tipo=subida">Imagen subida</a>
                <a role="tab" aria-selected="<?= $plano_act_cfg === "dibujo" ? "true" : "false"; ?>"
                   class="rf-tab<?= $plano_act_cfg === "dibujo" ? " is-active" : ""; ?><?= !$plano_dibujo_cfg ? " is-empty" : ""; ?>"
                   href="?page=config&tab=plano&accion=plano_activo&tipo=dibujo">Croquis dibujado</a>
            </div>
            <p class="text-xs text-gray-500 dark:text-gray-600 mt-1 mb-3">
                El plano marcado es el fondo del lienzo. La pestaña sin archivo todavía no puede activarse.
            </p>

            <form action="?page=config&tab=plano&accion=plano" method="POST" enctype="multipart/form-data" name="formplano" id="formplano">
                <label for="plano" class="field-label">Imagen del plano</label>
                <div class="flex flex-col sm:flex-row gap-2 items-stretch sm:items-center">
                    <input type="file" name="plano" id="plano" class="input border w-full">
                    <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="cargarplano()">Cargar</button>
                </div>
            </form>

            <button type="button" class="button text-white bg-theme-1 shadow-md mt-3 w-full sm:w-auto" onclick="abrirDibujo()">
                <?= $plano_dibujo_cfg ? "✏️ Editar croquis" : "✏️ Dibujar croquis"; ?>
            </button>
            <p class="text-xs text-gray-500 dark:text-gray-600 mt-1">
                Abre un editor tipo Paint para dibujar el plano a mano alzada.
                <?= $plano_dibujo_cfg ? "Ya tienes un croquis: se cargará para retocarlo." : ""; ?>
            </p>
        </div>

        <div class="form-section">
            <div class="form-section__title">
                <span class="form-section__emoji" aria-hidden="true">🛤️</span>
                Senderos
            </div>
            <label class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 cursor-pointer" data-lore="senderos">
                <input type="checkbox" id="yunqueModoSenderos" style="accent-color:var(--mordor-oro)"> Modo senderos
            </label>
            <div class="mt-3">
                <label for="yunqueEstilo" class="field-label">Estilo de trazado</label>
                <select id="yunqueEstilo" class="input border w-full">
                    <option value="recto">Recto</option>
                    <option value="ortogonal">Ángulos rectos</option>
                    <option value="curvo">Curvo</option>
                </select>
            </div>
            <p class="text-xs text-gray-500 dark:text-gray-600 mt-2">
                Con el modo senderos activo, haz clic sobre dos nodos para unirlos. Los nodos son cámaras
                <strong>sin</strong> líneas o las <strong>líneas</strong> de cámaras con líneas. Arrastra los puntos
                intermedios para personalizar el trazado (pasillos); Shift+clic sobre un punto lo elimina.
            </p>
        </div>
    </div>

    <!-- ================= Columna central: lienzo ================= -->
    <div class="col-span-12 xl:col-span-6 min-w-0">
        <div class="form-section">
            <div class="form-section__title">
                <span class="form-section__emoji" aria-hidden="true">⚒️</span>
                <span data-lore="el-yunque">El Yunque — Plano del local</span>
                <span id="yunqueEstado" class="yunque-estado yunque-estado--pend ml-auto"></span>
            </div>

            <div class="yunque-leyenda text-xs text-gray-500 dark:text-gray-600 mb-2 flex flex-wrap gap-3">
                <span><span class="yunque-dot" style="background:#2e9e44"></span> cámara completa</span>
                <span><span class="yunque-dot" style="background:#e0563c"></span> cámara con líneas pendientes</span>
                <span><span class="yunque-dot" style="background:#d22829"></span> nodo cámara</span>
                <span><span class="yunque-dot" style="background:#2596be"></span> nodo línea</span>
                <span><span class="yunque-dot" style="background:#ffed00"></span> línea en el plano</span>
                <span><span class="yunque-dot" style="background:#9a6bff"></span> sendero</span>
            </div>

            <div class="plan-wrap">
                <canvas id="canvasID" width="<?= CANVAS_WIDTH; ?>" height="<?= CANVAS_HEIGHT; ?>"
                        style="border-style:solid;border-width:1px;border-color:var(--mordor-humo);"
                        class="yunque-canvas"></canvas>
            </div>
            <p class="text-xs text-gray-500 dark:text-gray-600 mt-2">
                Arrastra las cámaras desde la derecha al plano (se autoguardan al soltar). Clic en una cámara para
                ver y arrastrar sus líneas. Con «modo senderos», clic sobre dos nodos para unirlos.
            </p>
        </div>
    </div>

    <!-- ================= Columna derecha: cámaras + líneas ================= -->
    <div class="col-span-12 xl:col-span-3 min-w-0 space-y-4">
        <div class="form-section">
            <div class="form-section__title">
                <span class="form-section__emoji" aria-hidden="true">📷</span>
                Cámaras fuera del plano
            </div>
            <div id="yunqueCamsFuera" class="yunque-cams-fuera"></div>
            <p class="text-xs text-gray-500 dark:text-gray-600 mt-2">
                Arrastra una cámara al plano para colocarla.
            </p>
        </div>

        <div class="form-section">
            <div class="form-section__title">
                <span class="form-section__emoji" aria-hidden="true">📏</span>
                <span id="yunqueLineasTitulo">Líneas de la cámara</span>
            </div>
            <div id="yunqueLineasPanel" class="yunque-lineas-panel">
                <p class="text-xs text-gray-500 dark:text-gray-600">Haz clic en una cámara del plano para ver sus líneas.</p>
            </div>
        </div>
    </div>
</div>
