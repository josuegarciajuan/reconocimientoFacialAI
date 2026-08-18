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

                <div class="mt-5 flex justify-end">
                    <button type="button" class="button text-white bg-theme-1 shadow-md" onclick="aceptar()">Aceptar</button>
                </div>
            </form>
        </div>
    </div>
</div>
