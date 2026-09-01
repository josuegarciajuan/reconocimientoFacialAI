<?php

/* 
 * Perfil de persona + galería (REFACTOR Fase 4c): PDO (B9).
 */

require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/avatars.php";
require_once __DIR__ . "/../../../libs/etiquetas.php";

$local_id = (int)($_SESSION["local_id"] ?? 0);
$persona_id = (int)($_GET["id"] ?? 0);

$persona = DB::selectOne('SELECT * FROM personas WHERE id = ?', [$persona_id]);
if (!$persona) {
    echo "Persona no encontrada";
    return;
}
$nombre_pers = ($persona["nombre"] !== "") ? $persona["nombre"] : $persona["cod_interno"];

$foto = DB::selectOne(
    "SELECT f.id AS fid FROM fotos f JOIN estancias e ON e.id = f.estancia_id WHERE e.persona_id = ? ORDER BY f.id ASC LIMIT 1",
    [$persona_id]
);
$imagen_perfil = "./caras_procesadas/" . ($foto ? $foto["fid"] : 0) . ".jpg";
$avatar_url = avatar_url($persona_id);

// cámaras del local + nº de estancias por cámara
$camaras = DB::select("SELECT * FROM camaras WHERE local_id = ?", [$local_id]);
$counts = [];
foreach ($camaras as $c) {
    $cnt = DB::selectOne("SELECT COUNT(*) AS n FROM estancias WHERE camara_id = ? AND persona_id = ?", [(int)$c["id"], $persona_id]);
    $counts[$c["id"]] = $cnt ? (int)$cnt["n"] : 0;
}

// listado de personas para "mover imagen"
$personas_list = DB::select("SELECT id, cod_interno, nombre FROM personas WHERE local_id = ? ORDER BY id ASC", [$local_id]);

// escapado para atributos onclick (patrón ui-common: verFoto('url','titulo'))
$js_quote = function ($s) {
    return htmlspecialchars(str_replace(["\\", "'"], ["\\\\", "\\'"], (string)$s), ENT_QUOTES);
};

// galería de fotos (estancias + fotos)
$galeria = [];  // [{fecha_ini, fecha_fin, fotos: [ids]}]
$audit_by_foto = [];
$audit_rows = DB::select(
    "SELECT fa.foto_id, fa.classification, fa.classification_phase, fa.attributes_json
     FROM foto_audits fa JOIN fotos f ON f.id = fa.foto_id
     JOIN estancias e ON e.id = f.estancia_id WHERE e.persona_id = ? ORDER BY fa.id DESC",
    [$persona_id]
);
foreach ($audit_rows as $ar) {
    $audit_by_foto[(int)$ar["foto_id"]][] = $ar;
}
$audit_events_by_foto = [];
$event_rows = DB::select(
    "SELECT foto_id, event_type, from_person_code, to_person_code, event_at
     FROM foto_audit_events WHERE foto_id IN
     (SELECT f.id FROM fotos f JOIN estancias e ON e.id = f.estancia_id WHERE e.persona_id = ?)
     ORDER BY id ASC", [$persona_id]
);
foreach ($event_rows as $event) {
    $audit_events_by_foto[(int)$event["foto_id"]][] = $event;
}
$estancias = DB::select("SELECT * FROM estancias WHERE persona_id = ? ORDER BY id ASC", [$persona_id]);
foreach ($estancias as $e) {
    $fotos = array_column(DB::select("SELECT id FROM fotos WHERE estancia_id = ? ORDER BY id ASC", [(int)$e["id"]]), "id");
    if ($fotos) {
        $galeria[] = ["fecha_ini" => $e["fecha_ini"], "fecha_fin" => $e["fecha_fin"], "fotos" => $fotos];
    }
}

// vídeos de movimiento vinculados a la persona (vía estancias.video_id)
$videos_persona = DB::select(
    "SELECT DISTINCT v.id, v.camara_id, v.fecha_ini, v.poster, v.nombre, c.descripcion AS camara_nombre
     FROM videos v
     JOIN estancias e ON e.video_id = v.id
     JOIN camaras c ON c.id = v.camara_id
     WHERE e.persona_id = ?
     ORDER BY v.fecha_ini DESC",
    [$persona_id]
);

// cruces de línea atribuidos a la persona (FK nullable)
$cruces_cnt = DB::selectOne("SELECT COUNT(*) AS n FROM cruces_lineas WHERE persona_id = ?", [$persona_id]);
$num_cruces = $cruces_cnt ? (int)$cruces_cnt["n"] : 0;
?>

<div class="intro-y flex items-center mt-8">
    <h2 class="text-lg font-medium mr-auto">Usuario: <?= htmlspecialchars($nombre_pers); ?></h2>
</div>

<div class="intro-y box px-5 pt-5 mt-5">
    <div class="flex flex-col lg:flex-row border-b border-gray-200 dark:border-dark-5 pb-5 -mx-5">
        <div class="flex flex-1 px-5 items-center justify-center lg:justify-start">
            <img alt="Foto de perfil de <?= htmlspecialchars($persona["nombre"]); ?>" class="rounded-full w-32 h-32 object-cover" src="<?= htmlspecialchars($imagen_perfil); ?>">
            <?php if ($avatar_url !== ""): ?>
            <img alt="Avatar (cabeza recortada) de <?= htmlspecialchars($persona["nombre"]); ?>"
                 title="Avatar del monigote (Caminos)"
                 class="ml-3 rounded-full w-16 h-16 object-contain bg-gray-900 dark:bg-gray-800 border border-gray-700"
                 src="<?= htmlspecialchars($avatar_url); ?>">
            <?php endif; ?>
        </div>

        <div class="flex mt-6 lg:mt-0 items-center lg:items-start flex-1 flex-col justify-center text-gray-600 dark:text-gray-300 px-5 border-l border-r border-gray-200 dark:border-dark-5 border-t lg:border-t-0 pt-5 lg:pt-0">
            <div class="truncate sm:whitespace-normal flex items-center">
                &nbsp;ID:&nbsp;<b><?= $persona_id; ?></b>
            </div>
            <div class="truncate sm:whitespace-normal flex items-center">
                &nbsp;Código interno:&nbsp;<b><?= htmlspecialchars($persona["cod_interno"]); ?></b>
            </div>
            <br />
            <div class="truncate sm:whitespace-normal flex items-center">
                &nbsp;Nombre:&nbsp;<input type="text" class="input border w-full" value="<?= htmlspecialchars($persona["nombre"]); ?>" onblur="cambiar_nombre(this.value,<?= $persona_id; ?>)" style="max-width:16rem">
                <span style="display:none" id="cargador<?= $persona_id; ?>"></span>
            </div>
            <div class="truncate sm:whitespace-normal flex items-center">
                &nbsp;Es Trabajador:&nbsp;
                <input type="checkbox" name="trabajador_edit" id="trabajador_edit" value="1" <?php if ((int)$persona["trabajador"] === 1) { echo "checked='checked'"; } ?> onclick="cambiar_trabajador(<?= $persona_id; ?>)">
                <span style="display:none" id="cargador2<?= $persona_id; ?>"></span>
            </div>
        </div>

        <div class="flex mt-6 lg:mt-0 items-center lg:items-start flex-1 flex-col justify-center text-gray-600 px-5 pt-5">
            <?php foreach ($camaras as $c): ?>
                <div class="text-center rounded-md" style="padding:8px">
                    <div class="font-semibold text-theme-1 text-lg"><?= $counts[$c["id"]] ?? 0; ?></div>
                    <div class="text-gray-600"><?= htmlspecialchars(camara_label($c["descripcion"])); ?></div>
                </div>
            <?php endforeach; ?>
        </div>
    </div>

    <div class="nav-tabs flex flex-col sm:flex-row justify-center lg:justify-start">
        <a href="?page=accesos&persona_id=<?= $persona_id; ?>" class="py-4 sm:mr-8 flex items-center active">Ver Movimientos</a>
        <a href="?page=rutas&persona_id=<?= $persona_id; ?>" class="py-4 sm:mr-8 flex items-center">Ver Caminos</a>
        <a href="#videos" class="py-4 sm:mr-8 flex items-center">Ver Vídeos (<?= count($videos_persona); ?>)</a>
        <a href="?page=lineas&persona_id=<?= $persona_id; ?>" class="py-4 sm:mr-8 flex items-center">Ver Cruces (<?= $num_cruces; ?>)</a>
    </div>
</div>

<div class="tab-content mt-5">
    <div class="tab-content__pane active" id="profile">
        <div class="grid grid-cols-12 gap-6">
            <div class="intro-y box col-span-12">
                <div class="flex items-center px-5 py-3 border-b border-gray-200 dark:border-dark-5">
                    <h2 class="font-medium text-base mr-auto">Listado Fotos</h2>
                </div>
                <div class="p-3 sm:p-5">
                    <div class="flex flex-wrap items-center gap-2 mb-3 p-2 rounded bg-gray-100 dark:bg-dark-5">
                        <span class="text-sm font-medium">Mover seleccionadas a:</span>
                        <select id="separar_destino" class="input border">
                            <option value="0">NUEVA PERSONA</option>
                            <?php foreach ($personas_list as $p): ?>
                                <?php $pn = ($p["nombre"] !== "") ? $p["nombre"] : $p["cod_interno"]; ?>
                                <option value="<?= (int)$p["id"]; ?>"><?= htmlspecialchars($pn); ?></option>
                            <?php endforeach; ?>
                        </select>
                        <button class="button text-white bg-theme-1 shadow-md" onclick="rfSepararSeleccionadas()">Mover seleccionadas</button>
                        <span class="text-xs text-gray-600 dark:text-gray-300" id="rf_sel_count"></span>
                    </div>
                    <?php if (!$galeria): ?>
                    <div class="empty-state">
                        <div class="empty-state__title">Sin fotos todavía</div>
                        <div class="empty-state__hint">Este usuario aún no tiene fotos asociadas a ninguna estancia.</div>
                    </div>
                    <?php endif; ?>
                    <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
                    <?php
                    foreach ($galeria as $g) {
                        $primera = true;
                        foreach ($g["fotos"] as $fid) {
                            $fecha = $primera ? $g["fecha_ini"] : $g["fecha_fin"];
                            $primera = false;
                            $img = "./caras_procesadas/" . $fid . ".jpg";
                    ?>
                        <div class="box p-3">
                            <label class="flex items-center gap-1 text-xs mb-1 cursor-pointer">
                                <input type="checkbox" class="rf-foto-check" data-fid="<?= (int)$fid; ?>" onchange="rfActualizarConteo()"> seleccionar
                            </label>
                             <div class="text-xs text-center text-gray-600 dark:text-gray-300 truncate mb-2"><?= htmlspecialchars($fecha); ?></div>
                            <img src="<?= htmlspecialchars($img); ?>" alt="Foto <?= $fid; ?> del <?= htmlspecialchars($fecha); ?>"
                                 onclick="verFoto('<?= $js_quote($img); ?>','<?= $js_quote($fecha); ?>')"
                                 class="w-full object-cover rounded cursor-pointer" style="aspect-ratio:1/1">
                            <?php if (isset($audit_by_foto[(int)$fid]) || isset($audit_events_by_foto[(int)$fid])): ?>
                                <div class="text-xs mt-2 text-gray-600 dark:text-gray-300">
                                    <?php foreach (($audit_by_foto[(int)$fid] ?? []) as $audit): ?>
                                        <div>Clasificación <?= $audit["classification_phase"] === "post_move" ? "post-move" : "original"; ?>: <b><?= htmlspecialchars($audit["classification"]); ?></b></div>
                                        <?php $attrs = json_decode((string)$audit["attributes_json"], true); ?>
                                        <?php if (is_array($attrs) && is_array($attrs["attributes"] ?? null)): ?>
                                            <div class="mt-1">Apariencia visible: <?= htmlspecialchars(json_encode($attrs["attributes"], JSON_UNESCAPED_UNICODE)); ?></div>
                                        <?php endif; ?>
                                    <?php endforeach; ?>
                                    <?php foreach (($audit_events_by_foto[(int)$fid] ?? []) as $event): ?>
                                        <div>Movimiento (append-only): <b><?= htmlspecialchars($event["event_type"]); ?></b>
                                            · <?= htmlspecialchars((string)$event["event_at"]); ?>
                                            · <?= htmlspecialchars((string)$event["from_person_code"]); ?> → <?= htmlspecialchars((string)$event["to_person_code"]); ?></div>
                                    <?php endforeach; ?>
                                </div>
                            <?php endif; ?>
                            <label class="field-label mt-3" for="mover_<?= $fid; ?>">Mover imagen</label>
                            <select id="mover_<?= $fid; ?>" class="input border w-full mt-1" onchange="mover_img(<?= (int)$fid; ?>,this.value)">
                                <option>Mover Imagen</option>
                                <option value="0">NUEVA PERSONA</option>
                                <?php foreach ($personas_list as $p): ?>
                                    <?php $pn = ($p["nombre"] !== "") ? $p["nombre"] : $p["cod_interno"]; ?>
                                    <option value="<?= (int)$p["id"]; ?>"><?= htmlspecialchars($pn); ?></option>
                                <?php endforeach; ?>
                            </select>
                        </div>
                    <?php
                        }
                    }
                    ?>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="grid grid-cols-12 gap-6 mt-5" id="videos">
        <div class="intro-y box col-span-12">
            <div class="flex items-center px-5 py-3 border-b border-gray-200 dark:border-dark-5">
                <h2 class="font-medium text-base mr-auto">Vídeos de movimiento (<?= count($videos_persona); ?>)</h2>
                <a href="?page=accesos&persona_id=<?= $persona_id; ?>" class="text-theme-1 font-medium text-sm hover:underline">Ver en Movimientos</a>
            </div>
            <div class="p-3 sm:p-5">
                <?php if (!$videos_persona): ?>
                <div class="empty-state">
                    <div class="empty-state__title">Sin vídeos vinculados</div>
                    <div class="empty-state__hint">Los vídeos de movimiento de esta persona aparecerán aquí cuando el vinculador los enlace (misma cámara y fecha).</div>
                </div>
                <?php else: ?>
                <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-4">
                    <?php foreach ($videos_persona as $v): ?>
                        <?php $ts_v = strtotime($v["fecha_ini"]); ?>
                        <?php $fecha_v = $ts_v ? date("d/m/Y H:i", $ts_v) : $v["fecha_ini"]; ?>
                        <div class="box p-3">
                            <div class="text-xs text-center text-gray-600 dark:text-gray-300 truncate mb-2"><?= htmlspecialchars($fecha_v); ?> · <?= htmlspecialchars(camara_label($v["camara_nombre"] ?? "")); ?></div>
                            <a href="javascript:;" title="Ver el vídeo del movimiento"
                               onclick="rfVideoModal(<?= (int)$v["id"]; ?>,'../video.php?id=<?= (int)$v["id"]; ?>','<?= $js_quote("../video.php?id=" . (int)$v["id"] . "&poster=1"); ?>','<?= $js_quote($nombre_pers . " · " . ($v["camara_nombre"] ?? "")); ?>',<?= $persona_id; ?>,'<?= $js_quote($nombre_pers); ?>')">
                                <img src="<?= htmlspecialchars("../video.php?id=" . (int)$v["id"] . "&poster=1"); ?>"
                                     alt="Vídeo del <?= htmlspecialchars($fecha_v); ?>"
                                     onerror="this.onerror=null;this.outerHTML='<div class=\'w-full flex items-center justify-center h-24 rounded bg-gray-800 dark:bg-gray-900 text-theme-1 font-medium text-xs\'>▶ Ver vídeo</div>';"
                                     class="w-full object-cover rounded cursor-pointer" style="aspect-ratio:16/9">
                            </a>
                        </div>
                    <?php endforeach; ?>
                </div>
                <?php endif; ?>
            </div>
        </div>
    </div>

    <div class="grid grid-cols-12 gap-6 mt-5">
        <div class="intro-y box col-span-12">
            <div class="flex items-center px-5 py-3 border-b border-gray-200 dark:border-dark-5">
                <h2 class="font-medium text-base mr-auto">Cruces de línea (<?= $num_cruces; ?>)</h2>
                <a href="?page=lineas&persona_id=<?= $persona_id; ?>" class="text-theme-1 font-medium text-sm hover:underline">Ver en Líneas</a>
            </div>
            <div class="p-3 sm:p-5">
                <?php if ($num_cruces === 0): ?>
                <div class="empty-state">
                    <div class="empty-state__title">Sin cruces atribuidos</div>
                    <div class="empty-state__hint">Los cruces de línea de esta persona aparecerán aquí cuando el vinculador los atribuya (estancia del mismo vídeo que cubre el cruce).</div>
                </div>
                <?php else: ?>
                <p class="text-sm text-gray-600 dark:text-gray-300">
                    Esta persona tiene <b><?= $num_cruces; ?></b> cruce(s) de línea atribuido(s).
                    <a class="text-theme-1 font-medium hover:underline" href="?page=lineas&persona_id=<?= $persona_id; ?>">Ver el listado completo</a>.
                </p>
                <?php endif; ?>
            </div>
        </div>
    </div>
</div>
