<?php

/*
 * La Almenara — configuración de teléfonos de recepción de alarmas.
 * La lista se guarda en `alarmas_telefonos` y quedará lista para el envío por
 * WhatsApp (canal preparado en libs/notificador.php; hoy el aviso es in-app).
 */

require_once __DIR__ . "/../../../libs/db.php";

$local_id = (int)($_SESSION["local_id"] ?? 0);
$telefonos = DB::select(
    "SELECT * FROM alarmas_telefonos WHERE local_id = ? ORDER BY id ASC",
    [$local_id]
);
?>

<div class="intro-y flex flex-col sm:flex-row items-center mt-8">
    <h2 class="text-lg font-medium mr-auto">📞 Teléfonos de aviso</h2>
    <a href="?page=alarmas" class="button text-white bg-theme-2 shadow-md">← Volver a La Almenara</a>
</div>

<div class="intro-y box p-5 mt-5">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">🚨</span>
        Añadir teléfono de recepción
    </div>
    <p class="text-xs text-gray-500 dark:text-gray-600 mt-1 mb-4">
        Estos números recibirán los avisos de alarma. El envío por WhatsApp está preparado
        en el sistema (canal listo); de momento el aviso se muestra dentro del panel.
    </p>

    <form action="acciones_ajax.php?a=1" method="POST" class="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div>
            <label for="telefono_nombre" class="field-label">Nombre</label>
            <input type="text" name="nombre" id="telefono_nombre" class="input border w-full" placeholder="Ej. Encargado de turno" required>
        </div>
        <div>
            <label for="telefono_numero" class="field-label">Teléfono</label>
            <input type="tel" name="telefono" id="telefono_numero" class="input border w-full" placeholder="+34 600 000 000" required>
        </div>
        <div class="flex items-end">
            <button type="submit" class="button text-white bg-theme-1 shadow-md">Añadir</button>
        </div>
    </form>

    <div class="table-wrap mt-6">
        <table class="table table-report table-report--bordered display datatable w-full">
            <thead>
                <tr>
                    <th class="border-b-2 text-center">NOMBRE</th>
                    <th class="border-b-2 text-center">TELÉFONO</th>
                    <th class="border-b-2 text-center">ESTADO</th>
                    <th class="border-b-2 text-center">ACCIONES</th>
                </tr>
            </thead>
            <tbody>
            <?php
            $par = "odd";
            foreach ($telefonos as $t) {
                $activo = (int)($t["activo"] ?? 1) === 1
                    ? '<span class="text-xs text-theme-9 font-bold">Activo</span>'
                    : '<span class="text-xs text-gray-500">Inactivo</span>';
            ?>
                <tr class="<?= $par; ?>">
                    <td class="text-center border-b"><?= htmlspecialchars($t["nombre"] ?? ""); ?></td>
                    <td class="text-center border-b"><?= htmlspecialchars($t["telefono"]); ?></td>
                    <td class="text-center border-b"><?= $activo; ?></td>
                    <td class="text-center border-b">
                        <a class="text-theme-6 hover:underline" href="acciones_ajax.php?a=2&id=<?= (int)$t["id"]; ?>" onclick="return confirm('¿Quitar este teléfono?');">Quitar</a>
                    </td>
                </tr>
            <?php
                $par = ($par === "odd") ? "pair" : "odd";
            }
            if (!$telefonos) {
                echo '<tr class="odd"><td class="text-center border-b py-6 text-gray-500 dark:text-gray-500" colspan="4">Sin teléfonos configurados todavía.</td></tr>';
            }
            ?>
            </tbody>
        </table>
    </div>
</div>

<div class="intro-y box p-5 mt-5">
    <div class="form-section__title">
        <span class="form-section__emoji" aria-hidden="true">⚒️</span>
        Horarios de inactividad
    </div>
    <p class="text-xs text-gray-500 dark:text-gray-600 mt-1">
        Los horarios se configuran en los formularios de <a class="text-theme-1 hover:underline" href="?page=config&tab=locales">Fortalezas (local)</a>
        y de <a class="text-theme-1 hover:underline" href="?page=config&tab=camaras">Cámaras</a> (sección «Vigilancia»).
        Cada cámara hereda el horario del local salvo que defina el suyo, y «Actividad 24h» desactiva las alarmas.
    </p>
</div>
