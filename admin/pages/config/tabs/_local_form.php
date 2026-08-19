<?php
/* Partial compartido del formulario de fortaleza (crear y editar).
 * Usa $local_edit (array|null): null = alta, array = edición (precarga valores).
 */
$lf = $local_edit ?? null;
$val = function ($k, $d = "") use ($lf) {
    return htmlspecialchars((string)($lf[$k] ?? $d), ENT_QUOTES);
};
?>
<div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
    <div>
        <label for="nombre" class="field-label">Nombre</label>
        <input type="text" name="nombre" id="nombre" value="<?= $val("nombre"); ?>" class="input border w-full" required>
    </div>
    <div>
        <label for="url_logo" class="field-label">URL del logo</label>
        <input type="text" name="url_logo" id="url_logo" value="<?= $val("url_logo"); ?>" class="input border w-full">
    </div>
    <div>
        <label for="usuario" class="field-label">Usuario</label>
        <input type="text" name="usuario" id="usuario" value="<?= $val("usuario"); ?>" class="input border w-full">
    </div>
    <div>
        <label for="passw" class="field-label">Password</label>
        <input type="password" name="passw" id="passw" value="" class="input border w-full" placeholder="<?= $lf ? "Nueva contraseña (opcional)" : "Contraseña"; ?>">
    </div>
    <div>
        <label for="aforo_max" class="field-label">Aforo máximo</label>
        <input type="text" name="aforo_max" id="aforo_max" value="<?= $val("aforo_max"); ?>" class="input border w-full">
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
                <input type="checkbox" name="jornada_partida" id="jornada_partida" value="1" <?php if ((int)($lf["jornada_partida"] ?? 0) === 1) { echo "checked='checked'"; } ?>>
                Jornada partida (entra y sale 2 veces al día)
            </label>
        </div>
        <div>
            <label for="hora_entrada1" class="field-label">Entrada 1</label>
            <input type="time" name="hora_entrada1" id="hora_entrada1" value="<?= $val("hora_entrada1"); ?>" class="input border w-full">
        </div>
        <div>
            <label for="hora_salida1" class="field-label">Salida 1</label>
            <input type="time" name="hora_salida1" id="hora_salida1" value="<?= $val("hora_salida1"); ?>" class="input border w-full">
        </div>
        <div>
            <label for="hora_entrada2" class="field-label">Entrada 2 (tarde)</label>
            <input type="time" name="hora_entrada2" id="hora_entrada2" value="<?= $val("hora_entrada2"); ?>" class="input border w-full">
        </div>
        <div>
            <label for="hora_salida2" class="field-label">Salida 2 (tarde)</label>
            <input type="time" name="hora_salida2" id="hora_salida2" value="<?= $val("hora_salida2"); ?>" class="input border w-full">
        </div>
        <div>
            <label for="margen_fichaje_min" class="field-label">Margen (minutos)</label>
            <input type="number" name="margen_fichaje_min" id="margen_fichaje_min" min="0" step="5" value="<?= (int)($lf["margen_fichaje_min"] ?? 30); ?>" class="input border w-full">
        </div>
    </div>
</div>

<div class="mt-5 flex justify-end">
    <button type="submit" class="button text-white bg-theme-1 shadow-md">Guardar fortaleza</button>
</div>
