<?php

/* 
 * Listado de locales (REFACTOR Fase 4c): PDO (B9).
 */

require_once __DIR__ . "/../../../libs/db.php";

$locales = DB::select("SELECT * FROM locales ORDER BY id ASC");
?>

<div class="intro-y flex flex-col sm:flex-row items-center mt-8">
    <h2 class="text-lg font-medium mr-auto">Listado Locales</h2>
    <div class="w-full sm:w-auto flex mt-4 sm:mt-0">
        <button class="button text-white bg-theme-1 shadow-md mr-2" onclick="location.href='?page=locales&mode=editar'">Nuevo</button>
    </div>
</div>

<div class="intro-y datatable-wrapper box p-5 mt-5">
    <table class="table table-report table-report--bordered display datatable w-full">
        <thead>
            <tr>
                <th class="border-b-2 text-center">LOGO</th>
                <th class="border-b-2 text-center">NOMBRE</th>
                <th class="border-b-2 text-center">AFORO MAX</th>
                <th class="border-b-2 text-center">AFORO ACTUAL</th>
                <th class="border-b-2 text-center">CÁMARAS</th>
                <th class="border-b-2 text-center">PERSONAS</th>
                <th class="border-b-2 text-center">ACCIONES</th>
            </tr>
        </thead>
        <tbody>
        <?php
        $par = "odd";
        foreach ($locales as $l) {
            $camaras = DB::selectOne("SELECT COUNT(*) AS n FROM camaras WHERE local_id = ?", [(int)$l["id"]]);
            $personas = DB::selectOne("SELECT COUNT(*) AS n FROM personas WHERE local_id = ?", [(int)$l["id"]]);
        ?>
            <tr class="<?= $par; ?>">
                <td class="text-center border-b">
                    <div class="flex sm:justify-center">
                        <div class="intro-x w-10 h-10 image-fit">
                            <img alt="" class="rounded-full" src="<?= htmlspecialchars($l["url_logo"]); ?>">
                        </div>
                    </div>
                </td>
                <td class="border-b" align="center"><?= htmlspecialchars($l["nombre"]); ?></td>
                <td class="border-b" align="center"><?= $l["aforo_max"]; ?></td>
                <td class="border-b" align="center"><?= $l["aforo_actual"]; ?></td>
                <td class="border-b" align="center"><?= $camaras ? (int)$camaras["n"] : 0; ?></td>
                <td class="border-b" align="center"><?= $personas ? (int)$personas["n"] : 0; ?></td>
                <td class="border-b w-5">
                    <div class="flex sm:justify-center items-center">
                        <a class="flex items-center mr-3" href="?page=locales&mode=editar&id=<?= (int)$l["id"]; ?>">Editar</a>
                    </div>
                </td>
            </tr>
        <?php
            $par = ($par === "odd") ? "pair" : "odd";
        }
        ?>
        </tbody>
    </table>
</div>
