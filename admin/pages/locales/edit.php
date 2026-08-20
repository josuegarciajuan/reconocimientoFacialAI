<?php

/* 
 * Edición de local (REFACTOR Fase 4c): PDO (B9).
 * UI: Barad-dûr (Mordor). Solo presentación: la lógica la consume
 * admin/pages/locales/javascript.php (aceptar()) y acciones.php.
 */

require_once __DIR__ . "/../../../libs/db.php";

if (isset($_GET["id"]) and $_GET["id"] !== "") {
    $local = DB::selectOne('SELECT * FROM locales WHERE id = ?', [(int)$_GET["id"]]);
    if (!$local) {
        $local = [];
    }
} else {
    $local = ["nombre" => "", "url_logo" => "", "usuario" => "", "aforo_max" => "", "aforo_actual" => ""];
}
?>

<div class="intro-y flex items-center mt-8">
    <h2 class="text-lg font-medium mr-auto">Local: <?= htmlspecialchars($local["nombre"] ?? ""); ?></h2>
</div>

<div class="intro-y box px-5 pt-5 mt-5">
    <div class="flex flex-col lg:flex-row border-b border-gray-200 dark:border-dark-5 pb-5 -mx-5">
        <div class="flex flex-1 px-5 items-center justify-center lg:justify-start py-5">
            <div class="w-24 h-24 image-fit">
                <img alt="Logo de <?= htmlspecialchars($local["nombre"] ?? ""); ?>" class="rounded-full border border-gray-700" src="<?= htmlspecialchars($local["url_logo"] ?? ""); ?>">
            </div>
        </div>

        <div class="flex mt-6 lg:mt-0 items-center lg:items-start flex-1 flex-col justify-center px-5 border-l border-r border-gray-200 dark:border-dark-5 border-t lg:border-t-0 pt-5 lg:pt-0">
            <form action="?page=locales&mode=editar&id=<?= (int)($_GET["id"] ?? 0); ?>&submit=1" method="POST" id="formu" class="w-full">
                <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                        <label for="nombre" class="field-label">Nombre</label>
                        <input type="text" name="nombre" id="nombre" value="<?= htmlspecialchars($local["nombre"] ?? ""); ?>" class="input border w-full">
                    </div>
                    <div>
                        <label for="url_logo" class="field-label">URL del logo</label>
                        <input type="text" name="url_logo" id="url_logo" value="<?= htmlspecialchars($local["url_logo"] ?? ""); ?>" class="input border w-full">
                    </div>
                    <div>
                        <label for="usuario" class="field-label">Usuario</label>
                        <input type="text" name="usuario" id="usuario" value="<?= htmlspecialchars($local["usuario"] ?? ""); ?>" class="input border w-full">
                    </div>
                    <div>
                        <label for="passw" class="field-label">Password</label>
                        <input type="password" name="passw" id="passw" value="" class="input border w-full" placeholder="Nueva contraseña (opcional)">
                    </div>
                    <div>
                        <label for="aforo_max" class="field-label">Aforo máximo</label>
                        <input type="text" name="aforo_max" id="aforo_max" value="<?= htmlspecialchars($local["aforo_max"] ?? ""); ?>" class="input border w-full">
                    </div>
                </div>

                <div class="mt-5">
                    <h3 class="field-label">Horario de trabajo habitual (fichajes)</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-500 mt-1">
                        La primera captura del día por cámara de puerta es la entrada y la última por cámara de
                        salida es la salida definitiva. Con jornada partida se generan hasta 2 bloques al día.
                        Déjalo vacío para usar la detección simple (1 entrada + 1 salida).
                    </p>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-2">
                        <div class="sm:col-span-2">
                            <label for="jornada_partida" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
                                <input type="checkbox" name="jornada_partida" id="jornada_partida" value="1" <?php if ((int)($local["jornada_partida"] ?? 0) === 1) { echo "checked='checked'"; } ?>>
                                Jornada partida (entra y sale 2 veces al día)
                            </label>
                        </div>
                        <div>
                            <label for="hora_entrada1" class="field-label">Entrada 1</label>
                            <input type="time" name="hora_entrada1" id="hora_entrada1" value="<?= htmlspecialchars($local["hora_entrada1"] ?? ""); ?>" class="input border w-full">
                        </div>
                        <div>
                            <label for="hora_salida1" class="field-label">Salida 1</label>
                            <input type="time" name="hora_salida1" id="hora_salida1" value="<?= htmlspecialchars($local["hora_salida1"] ?? ""); ?>" class="input border w-full">
                        </div>
                        <div>
                            <label for="hora_entrada2" class="field-label">Entrada 2 (tarde)</label>
                            <input type="time" name="hora_entrada2" id="hora_entrada2" value="<?= htmlspecialchars($local["hora_entrada2"] ?? ""); ?>" class="input border w-full">
                        </div>
                        <div>
                            <label for="hora_salida2" class="field-label">Salida 2 (tarde)</label>
                            <input type="time" name="hora_salida2" id="hora_salida2" value="<?= htmlspecialchars($local["hora_salida2"] ?? ""); ?>" class="input border w-full">
                        </div>
                        <div>
                            <label for="margen_fichaje_min" class="field-label">Margen (minutos)</label>
                            <input type="number" name="margen_fichaje_min" id="margen_fichaje_min" min="0" step="5" value="<?= (int)($local["margen_fichaje_min"] ?? 30); ?>" class="input border w-full">
                        </div>
                    </div>
                </div>

                <div class="mt-5">
                    <h3 class="field-label">Vigilancia (alarmas de inactividad)</h3>
                    <p class="text-xs text-gray-500 dark:text-gray-500 mt-1">
                        Si está activa, cualquier movimiento fuera de este horario dispara una alarma en
                        «La Almenara». Marca «Actividad 24h» para que el local nunca alerte (todos los
                        casos quedan cubiertos). Las cámaras heredan este horario salvo que definan el suyo.
                    </p>
                    <div class="grid grid-cols-1 sm:grid-cols-2 gap-4 mt-2">
                        <div class="sm:col-span-2 flex flex-wrap gap-x-4 gap-y-2">
                            <label for="alarma_activa" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
                                <input type="checkbox" name="alarma_activa" id="alarma_activa" value="1" <?php if ((int)($local["alarma_activa"] ?? 0) === 1) { echo "checked='checked'"; } ?>>
                                Vigilancia activada
                            </label>
                            <label for="alarma_24h" class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
                                <input type="checkbox" name="alarma_24h" id="alarma_24h" value="1" <?php if ((int)($local["alarma_24h"] ?? 0) === 1) { echo "checked='checked'"; } ?>>
                                Actividad 24h (nunca alarmar)
                            </label>
                        </div>
                        <div>
                            <label for="alarma_hora_inicio" class="field-label">Inicio inactividad</label>
                            <input type="time" name="alarma_hora_inicio" id="alarma_hora_inicio" value="<?= htmlspecialchars($local["alarma_hora_inicio"] ?? ""); ?>" class="input border w-full">
                        </div>
                        <div>
                            <label for="alarma_hora_fin" class="field-label">Fin inactividad</label>
                            <input type="time" name="alarma_hora_fin" id="alarma_hora_fin" value="<?= htmlspecialchars($local["alarma_hora_fin"] ?? ""); ?>" class="input border w-full">
                        </div>
                        <div>
                            <label for="alarma_margen_min" class="field-label">Margen tras el cierre (min)</label>
                            <input type="number" name="alarma_margen_min" id="alarma_margen_min" min="0" step="5" value="<?= (int)($local["alarma_margen_min"] ?? 0); ?>" class="input border w-full">
                            <p class="text-xs text-gray-500 dark:text-gray-500 mt-1">Gracia para el último en salir.</p>
                        </div>
                    </div>
                </div>

                <div class="mt-5 flex justify-end">
                    <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="aceptar()">Aceptar</button>
                </div>
            </form>
        </div>
    </div>
</div>
