<?php

/*
 * Revisión — listado de caras pendientes (revision-only).
 *
 * El listado lo produce `motor/revision.py listar <local> --json` (mtime desc).
 * Por cada pendiente: miniatura (foto.php), ruta/cámara/fecha y un formulario
 * con Aprobar como nueva / Asignar a existente / Descartar.
 */

require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/security.php";
require_once __DIR__ . "/../../../libs/revision.php";

$local_id = (int)($_SESSION["local_id"] ?? 0);
$limite = 200;

$script = RUTA_PROYECTO . "motor/revision.py";
$cmd = RUTA_PYTHON . " " . $script . " listar " . escapeshellarg((string)$local_id)
     . " --ruta " . RUTA_PROYECTO . " --json 2>&1";
$salida = shell_exec($cmd);
$res = rf_revision_json_ultimo((string)$salida);
$pendientes = (is_array($res) && array_is_list($res)) ? $res : [];
$total = count($pendientes);
$mostrados = array_slice($pendientes, 0, $limite);

// Personas existentes del local para el selector de "asignar".
$personas = DB::select(
    "SELECT id, cod_interno, nombre FROM personas
     WHERE local_id = ? ORDER BY nombre ASC, cod_interno ASC LIMIT 1000",
    [$local_id]
);
?>

<div class="intro-y flex flex-col sm:flex-row items-center mt-8">
    <h2 class="text-lg font-medium mr-auto">Revisión de caras</h2>
    <div class="text-gray-600"><?= (int)$total ?> pendiente(s)</div>
</div>

<?php if ($total === 0): ?>
    <div class="intro-y box p-8 mt-5 text-center text-gray-600">
        No hay caras pendientes de revisión. El clasificador no ha dejado caras dudosas.
    </div>
<?php else: ?>
    <?php if ($total > $limite): ?>
        <div class="intro-y box p-3 mt-5 text-sm">
            Mostrando las <?= (int)$limite ?> más recientes de <?= (int)$total ?> pendientes.
        </div>
    <?php endif; ?>

    <div class="intro-y box p-5 mt-5">
        <?php foreach ($mostrados as $it): ?>
            <?php
            $cam = (string)($it["cam"] ?? "");
            $file = (string)($it["file"] ?? "");
            if (!rf_revision_componente_valido($cam) || !rf_revision_componente_valido($file) || !rf_revision_es_cara($file)) {
                continue;
            }
            $rel = (string)($it["rel"] ?? ($local_id . "/" . $cam . "/" . $file));
            $mtime = (int)($it["mtime"] ?? 0);
            $src = "pages/revision/foto.php?cam=" . urlencode($cam) . "&f=" . urlencode($file);
            ?>
            <div class="rf-rev-item" style="display:flex;gap:16px;align-items:flex-start;border-bottom:1px solid rgba(0,0,0,.08);padding:14px 0;">
                <img src="<?= htmlspecialchars($src, ENT_QUOTES) ?>" alt="Cara pendiente de revisión"
                     loading="lazy"
                     style="width:120px;height:120px;object-fit:cover;border-radius:8px;background:#111;flex:0 0 auto;">

                <div style="flex:1;min-width:0;">
                    <div style="font-weight:600;word-break:break-all;"><?= htmlspecialchars($rel, ENT_QUOTES) ?></div>
                    <div style="font-size:.85rem;color:#666;margin-top:2px;">
                        Cámara <?= htmlspecialchars($cam, ENT_QUOTES) ?>
                        · <?= $mtime > 0 ? htmlspecialchars(date("d/m/Y H:i:s", $mtime), ENT_QUOTES) : "—" ?>
                    </div>

                    <form method="post" action="?page=revision"
                          style="margin-top:10px;display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
                        <input type="hidden" name="csrf" value="<?= htmlspecialchars(rf_csrf_token(), ENT_QUOTES) ?>">
                        <input type="hidden" name="cam" value="<?= htmlspecialchars($cam, ENT_QUOTES) ?>">
                        <input type="hidden" name="file" value="<?= htmlspecialchars($file, ENT_QUOTES) ?>">

                        <input type="text" name="nombre" placeholder="Nombre (opcional)" maxlength="120"
                               class="input border" style="max-width:200px;">

                        <button type="submit" name="action" value="aprobar"
                                class="button text-white bg-theme-1 shadow-md"
                                onclick="return rfRevisionConfirmar('aprobar', this)">Aprobar como nueva</button>

                        <select name="cod_destino" class="input border" style="max-width:280px;">
                            <option value="">— Asignar a persona existente —</option>
                            <?php foreach ($personas as $p): ?>
                                <?php
                                $p_nombre = trim((string)$p["nombre"]);
                                $p_label = ($p_nombre !== "" ? $p_nombre : "(sin nombre)") . " · " . (string)$p["cod_interno"];
                                ?>
                                <option value="<?= htmlspecialchars((string)$p["cod_interno"], ENT_QUOTES) ?>">
                                    <?= htmlspecialchars($p_label, ENT_QUOTES) ?>
                                </option>
                            <?php endforeach; ?>
                        </select>

                        <button type="submit" name="action" value="asignar"
                                class="button text-white bg-theme-2 shadow-md"
                                onclick="return rfRevisionConfirmar('asignar', this)">Asignar</button>

                        <button type="submit" name="action" value="descartar"
                                class="button text-white bg-theme-6 shadow-md"
                                onclick="return rfRevisionConfirmar('descartar', this)">Descartar</button>
                    </form>
                </div>
            </div>
        <?php endforeach; ?>
    </div>
<?php endif; ?>
