<?php

/* 
 * Edición de local (REFACTOR Fase 4c): PDO (B9).
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
        <div class="flex flex-1 px-5 items-center justify-center lg:justify-start">
            <center><img alt="" class="rounded-full" src="<?= htmlspecialchars($local["url_logo"] ?? ""); ?>"></center>
        </div>

        <div class="flex mt-6 lg:mt-0 items-center lg:items-start flex-1 flex-col justify-center text-gray-600 dark:text-gray-300 px-5 border-l border-r border-gray-200 dark:border-dark-5 border-t lg:border-t-0 pt-5 lg:pt-0" style="font-size:25px">
            <form action="?page=locales&mode=editar&id=<?= (int)($_GET["id"] ?? 0); ?>&submit=1" method="POST" id="formu">
                <div class="truncate sm:whitespace-normal flex items-center">
                    &nbsp;<b>Nombre:</b>&nbsp;&nbsp;&nbsp;&nbsp;<input type="text" name="nombre" value="<?= htmlspecialchars($local["nombre"] ?? ""); ?>">
                </div>
                <div class="truncate sm:whitespace-normal flex items-center">
                    &nbsp;<b>URL LOGO:</b>&nbsp;&nbsp;&nbsp;&nbsp;<input type="text" name="url_logo" value="<?= htmlspecialchars($local["url_logo"] ?? ""); ?>">
                </div>
                <div class="truncate sm:whitespace-normal flex items-center">
                    &nbsp;<b>Usuario:</b>&nbsp;&nbsp;&nbsp;&nbsp;<input type="text" name="usuario" value="<?= htmlspecialchars($local["usuario"] ?? ""); ?>">
                </div>
                <div class="truncate sm:whitespace-normal flex items-center">
                    &nbsp;<b>Password:</b>&nbsp;&nbsp;&nbsp;&nbsp;<input type="password" name="passw" value="">
                </div>
                <div class="truncate sm:whitespace-normal flex items-center">
                    &nbsp;<b>Aforo:</b>&nbsp;&nbsp;&nbsp;&nbsp;<input type="text" name="aforo_max" value="<?= htmlspecialchars($local["aforo_max"] ?? ""); ?>">
                </div>
            </form>
            <button class="button text-white bg-theme-1 shadow-md mr-2" onclick="aceptar()">Aceptar</button>
        </div>
    </div>
</div>
