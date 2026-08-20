<?php

/* 
 * Notificaciones (REFACTOR Fase 4b/4c): PDO + esquema actual (estancias/personas).
 */

require_once __DIR__ . "/../libs/db.php";
require_once __DIR__ . "/../libs/etiquetas.php";

$local_id = (int)($_SESSION["local_id"] ?? 0);

$hay_notificaciones = false;
$n = DB::selectOne(
    "SELECT COUNT(*) AS n FROM estancias e
     JOIN camaras c ON c.id = e.camara_id
     WHERE c.local_id = ? AND e.notificacion_vista = 0 AND (c.puerta = 1 OR c.salida = 1)",
    [$local_id]
);
$num_notificaciones = $n ? (int)$n["n"] : 0;
$hay_notificaciones = $num_notificaciones > 0;
?>

<!-- BEGIN: Notifications -->
<div class="intro-x dropdown relative mr-4 sm:mr-6" onclick="notificaciones_leidas()">
    <div id="campanita_notificaciones" class="dropdown-toggle notification notification--light <?php if ($hay_notificaciones) { echo "notification--bullet"; } ?> cursor-pointer">
        <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="feather feather-bell notification__icon dark:text-gray-300"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path><path d="M13.73 21a2 2 0 0 1-3.46 0"></path></svg>
        <?php if ($hay_notificaciones): ?>
            <span class="notification-badge"><?= $num_notificaciones > 9 ? "9+" : $num_notificaciones; ?></span>
        <?php endif; ?>
    </div>

    <div class="notification-content dropdown-box mt-8 absolute top-0 right-0 z-10 -mr-10 sm:mr-0">
        <div class="notification-content__box dropdown-box__content box dark:bg-dark-6" id="capa_notificaciones">
            <div class="notification-content__title">🛎️ Señales de Guerra</div>

            <?php
            $notis = DB::select(
                "SELECT e.id, e.created, e.persona_id, e.camara_id, p.cod_interno, p.nombre, c.descripcion, c.puerta, c.salida
                 FROM estancias e
                 JOIN personas p ON p.id = e.persona_id
                 JOIN camaras c ON c.id = e.camara_id
                 WHERE c.local_id = ? AND (c.puerta = 1 OR c.salida = 1)
                 ORDER BY e.id DESC LIMIT 5",
                [$local_id]
            );
            if (!$notis) {
                ?>
                <div class="flex flex-col items-center py-8 text-center">
                    <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="feather feather-bell-off w-10 h-10 text-gray-400 mb-3"><path d="M13.73 21a2 2 0 0 1-3.46 0"></path><path d="M18.63 13A17.89 17.89 0 0 1 18 8"></path><path d="M6.26 6.26A5.86 5.86 0 0 0 6 8c0 7-3 9-3 9h14"></path><path d="M18 8a6 6 0 0 0-9.33-5"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>
                    <div class="text-sm text-gray-500">Ninguna señal de guerra</div>
                    <div class="text-xs text-gray-400 mt-1">Los movimientos de puerta y salida aparecerán aquí</div>
                </div>
                <?php
            }
            foreach ($notis as $r) {
                $nombre = persona_label($r["nombre"], $r["cod_interno"]);
                $mode_html = "";
                if ((int)$r["puerta"] === 1) {
                    $mode_html = "Entrada al local por " . camara_link((int)$r["camara_id"], $r["descripcion"]);
                } elseif ((int)$r["salida"] === 1) {
                    $mode_html = "Salida del local por " . camara_link((int)$r["camara_id"], $r["descripcion"]);
                }
                $foto = DB::selectOne("SELECT MIN(id) AS mid FROM fotos WHERE estancia_id = ?", [(int)$r["id"]]);
                $imagen = "./caras_procesadas/" . ($foto && $foto["mid"] ? $foto["mid"] : 0) . ".jpg";
            ?>
                <div class="cursor-pointer relative flex items-center">
                    <div class="w-12 h-12 flex-none image-fit mr-1">
                        <img alt="" class="rounded-full" src="<?= htmlspecialchars($imagen); ?>">
                        <div class="w-3 h-3 bg-theme-9 absolute right-0 bottom-0 rounded-full border-2 border-white"></div>
                    </div>
                    <div class="ml-2 overflow-hidden">
                        <div class="flex items-center">
                            <a class="font-medium truncate mr-5 text-theme-1 hover:underline" href="?page=visitantes&mode=editar&id=<?= (int)$r["persona_id"]; ?>" title="Ver la ficha de la persona"><?= htmlspecialchars($nombre); ?></a>
                            <div class="text-xs text-gray-500 ml-auto whitespace-no-wrap"><?= htmlspecialchars($r["created"]); ?></div>
                        </div>
                        <div class="w-full truncate text-gray-600"><?= $mode_html; ?></div>
                    </div>
                </div>
            <?php } ?>
        </div>
    </div>
</div>
<!-- END: Notifications -->
