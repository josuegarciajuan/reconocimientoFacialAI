<?php
/* La Forja · Tab Fortalezas (locales)
 * Listado + crear/editar inline (sin salir de La Forja). Solo admin.
 * Sub-acciones: listar / crear / editar — resueltas en $sub.
 */

require_once __DIR__ . "/../../../../libs/db.php";

/* Local a editar (sub=editar). */
$local_edit = null;
if ($sub === "editar") {
    $lid = (int)($_GET["id"] ?? 0);
    if ($lid > 0) {
        $local_edit = DB::selectOne("SELECT * FROM locales WHERE id = ?", [$lid]);
    }
}
?>

<?php if ($sub === "crear"): ?>
<!-- ---------- Crear fortaleza ---------- -->
<div class="form-section" data-panel-forge="crear">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">🏰</span>
        <span data-lore="fortalezas">Nueva fortaleza</span>
        <a href="?page=config&tab=locales&sub=listar" class="button button--sm text-white bg-theme-6 shadow-md ml-auto">Volver al listado</a>
    </div>

    <form action="?page=config&tab=locales&sub=crear&accion=local_crear" method="POST" class="w-full">
        <?php include __DIR__ . "/_local_form.php"; ?>
    </form>
</div>

<?php elseif ($sub === "editar" && $local_edit): ?>
<!-- ---------- Editar fortaleza ---------- -->
<div class="form-section" data-panel-forge="editar">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">🏰</span>
        <span data-lore="fortalezas">Editar fortaleza: <?= htmlspecialchars($local_edit["nombre"] ?? ""); ?></span>
        <a href="?page=config&tab=locales&sub=listar" class="button button--sm text-white bg-theme-6 shadow-md ml-auto">Volver al listado</a>
    </div>

    <form action="?page=config&tab=locales&sub=editar&accion=local_guardar&id=<?= (int)$local_edit["id"]; ?>" method="POST" class="w-full">
        <?php include __DIR__ . "/_local_form.php"; ?>
    </form>
</div>

<?php elseif ($sub === "editar"): ?>
<div class="form-section">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">⚠️</span>
        Fortaleza no encontrada
    </div>
    <a href="?page=config&tab=locales&sub=listar" class="button text-white bg-theme-2 shadow-md">Volver al listado</a>
</div>

<?php else: ?>
<!-- ---------- Listado de fortalezas ---------- -->
<div class="form-section">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">🏰</span>
        <span data-lore="fortalezas">Fortalezas</span>
        <a href="?page=config&tab=locales&sub=crear" class="button button--sm text-white bg-theme-1 shadow-md ml-auto">Nuevo</a>
    </div>

    <p class="text-xs text-gray-500 dark:text-gray-600 mb-3">
        Cada fortaleza es un local con sus cámaras, su plano, su aforo y su legión. Crea y edita desde aquí sin salir de La Forja.
    </p>

    <div class="table-wrap">
        <table class="table table-report table-report--bordered display datatable w-full" data-ajax="config_locales">
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
            <tbody></tbody>
            <?php if (false) {
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
                            <a class="flex items-center mr-3" href="?page=config&tab=locales&sub=editar&id=<?= (int)$l["id"]; ?>">Editar</a>
                        </div>
                    </td>
                </tr>
            <?php
                $par = ($par === "odd") ? "pair" : "odd";
            }
            if (!$fortalezas) {
                echo '<tr class="odd"><td class="text-center border-b py-4 text-gray-500 dark:text-gray-500" colspan="7">No hay fortalezas dadas de alta todavía.</td></tr>';
            }
            } ?>
        </table>
    </div>
</div>
<?php endif; ?>
