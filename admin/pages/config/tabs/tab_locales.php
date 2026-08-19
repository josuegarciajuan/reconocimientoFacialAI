<?php
/* La Forja · Tab Fortalezas (locales)
 * Listado de locales/sedes adaptado de admin/pages/locales/list.php.
 * Solo se renderiza para administradores (el gate vive en index.php/edit.php).
 * Requiere libs/db.php. El lienzo "El Yunque" se oculta en este tab (edit.php).
 */

require_once __DIR__ . "/../../../../libs/db.php";

$fortalezas = DB::select("SELECT * FROM locales ORDER BY id ASC");
?>

<div class="form-section">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">🏰</span>
        <span data-lore="fortalezas">Fortalezas</span>
        <button class="button button--sm text-white bg-theme-1 shadow-md ml-auto"
                onclick="location.href='?page=locales&mode=editar'">Nuevo</button>
    </div>

    <p class="text-xs text-gray-500 dark:text-gray-600 mb-3">
        Cada fortaleza es un local con sus cámaras, su plano, su aforo y su legión. La edición se hace en
        <em>?page=locales</em> (sigue funcionando, solo que ya no está en el menú superior).
    </p>

    <div class="table-wrap">
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
            foreach ($fortalezas as $l) {
                $camaras  = DB::selectOne("SELECT COUNT(*) AS n FROM camaras WHERE local_id = ?", [(int)$l["id"]]);
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
                    <td class="border-b" align="center"><?= (int)$l["aforo_max"]; ?></td>
                    <td class="border-b" align="center"><?= (int)$l["aforo_actual"]; ?></td>
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
            if (!$fortalezas) {
                echo '<tr class="odd"><td class="text-center border-b py-4 text-gray-500 dark:text-gray-500" colspan="7">No hay fortalezas dadas de alta todavía.</td></tr>';
            }
            ?>
            </tbody>
        </table>
    </div>
</div>
