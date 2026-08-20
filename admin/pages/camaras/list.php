<?php

/* 
 * Cámaras en directo (REFACTOR Fase 4c + live MJPEG).
 * - Rejilla: snapshots `fotos_camara/<id>.png` refrescados en segundo plano
 *   (dofoto.py async, con caché de 15s). Antes cada carga bloqueaba ~60s
 *   (exec + sleep(2) síncrono por cámara) -> la sección "no cargaba".
 * - Vista (clic en tarjeta): modal Midone con streaming local RTSP->MJPEG
 *   vía live/mjpeg-stream.js y proxy Apache /reconocimientoFacial/live,
 *   en lugar del iframe de ipcamlive.com (alias sin configurar -> no cargaba).
 * - Enlaces antiguos (?page=camaras&id=X): abren automáticamente el modal.
 */

require_once __DIR__ . "/../../../libs/db.php";
require_once __DIR__ . "/../../../libs/etiquetas.php";

$local_id = (int)($_SESSION["local_id"] ?? 0);
$camaras = DB::select("SELECT * FROM camaras WHERE local_id = ? AND sistema = 0 AND encendida = 1 ORDER BY orden ASC, descripcion ASC", [$local_id]);

/**
 * Lanza dofoto.py en segundo plano si el snapshot es antiguo o no existe.
 * Máximo 1 refresco por cámara cada 15s (evita golpear el RTSP en cada F5).
 */
function refrescar_snapshot(int $camara_id, string $url_conexion): void
{
    $foto = RUTA_PROYECTO . "admin/fotos_camara/" . $camara_id . ".png";
    if (is_file($foto) && (time() - filemtime($foto)) < 15) {
        return;
    }
    $url_limpia = str_replace("'", "", $url_conexion);
    $cmd = RUTA_PYTHON . " " . RUTA_PROYECTO . "motor/dofoto.py " . $camara_id
         . " '" . $url_limpia . "' '" . RUTA_PROYECTO . "'";
    exec($cmd . " > /dev/null 2>&1 &");
}

/**
 * Token HMAC de corta validez para el stream MJPEG de una cámara
 * (valida el servicio rf-live). Misma fórmula, secreto y ventana de
 * 5 minutos que el token original; la única diferencia es que ahora se
 * firma por cámara, para que el modal de cada tarjeta pueda autenticar
 * su propio stream aunque la página se cargue sin ?id=.
 */
function token_live_camara(int $camara_id): string
{
    $secret = getenv("RF_LIVE_TOKEN");
    if ($secret === false || $secret === "") {
        return "";
    }
    $ventana = (int)floor(time() / 300);
    return hash_hmac("sha256", "live:" . $camara_id . ":" . $ventana, $secret);
}

/* Token para el auto-apertura del modal por enlaces antiguos (?id=X). */
$live_token = token_live_camara((int)($_GET["id"] ?? 0));

/**
 * Normaliza a UTF-8 el texto que viene de la BD (la conexión PDO usa
 * latin1): sin esto, json_encode() falla con bytes latin1 y el onclick
 * del modal saldría vacío. ASCII puro pasa intacto.
 */
function rf_utf8_normalizar(string $s): string
{
    if (mb_check_encoding($s, "UTF-8")) {
        return $s;
    }
    return mb_convert_encoding($s, "UTF-8", "ISO-8859-1");
}

/* Placeholder SVG oscuro (proporción 16:10) para snapshots aún no generados. */
$ph_uri = "data:image/svg+xml;base64," . base64_encode(
    "<svg xmlns='http://www.w3.org/2000/svg' width='640' height='400'>"
    . "<rect width='640' height='400' fill='#161219'/>"
    . "</svg>"
);
?>

<div class="intro-y flex flex-col sm:flex-row items-center mt-8">
    <h2 class="text-lg font-medium mr-auto">Cámaras en Directo</h2>
    <div class="w-full sm:w-auto flex mt-4 sm:mt-0"></div>
</div>

<?php if (empty($camaras)): ?>
    <div class="empty-state box mt-5">
        <span class="empty-state__icon" aria-hidden="true">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                <path d="M16 16v1a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h2m5.66 0H14a2 2 0 0 1 2 2v3.34l1 1L23 7v10"></path>
                <line x1="1" y1="1" x2="23" y2="23"></line>
            </svg>
        </span>
        <span class="empty-state__title">Ninguna cámara en directo</span>
        <span class="empty-state__hint">Activa y enciende una cámara desde la configuración: sus snapshots aparecerán aquí automáticamente.</span>
    </div>
<?php else: ?>
<div class="cam-grid mt-5" id="cam-grid">
    <?php foreach ($camaras as $c):
        $camara_id = (int)$c["id"];
        $descripcion = camara_label(rf_utf8_normalizar((string)($c["descripcion"] ?? "Cámara " . $camara_id)));
        $url_conexion = (string)($c["url_conexion"] ?? "");

        refrescar_snapshot($camara_id, $url_conexion);

        $foto = RUTA_PROYECTO . "admin/fotos_camara/" . $camara_id . ".png";
        $existe = is_file($foto);
        $ts = $existe ? (int)filemtime($foto) : 0;

        $snapshot_base = "fotos_camara/" . $camara_id . ".png";
        $snapshot_uri = $snapshot_base . "?t=" . $ts;

        $stream_url = "../live?id=" . $camara_id;
        $token = token_live_camara($camara_id);
        if ($token !== "") {
            $stream_url .= "&token=" . urlencode($token);
        }

        /* Argumentos JS del modal: [id, stream, snapshot, título] */
        $js_args = json_encode(
            [$camara_id, $stream_url, $snapshot_uri, $descripcion],
            JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT
        );
        $alt = "Snapshot de " . $descripcion;
    ?>
    <button type="button" class="cam-card box text-left w-full"
            draggable="true"
            data-camara-id="<?= $camara_id; ?>"
            aria-label="Cámara en directo: <?= htmlspecialchars($descripcion, ENT_QUOTES); ?>"
            onclick="rfCamModal(...<?= htmlspecialchars($js_args, ENT_QUOTES); ?>)">
        <span class="cam-card__media block">
            <?php if (!$existe): ?>
            <span class="cam-card__placeholder absolute inset-0 flex items-center justify-center empty-state__hint">Cargando…</span>
            <?php endif; ?>
            <img class="cam-card__img" data-snapshot="<?= $snapshot_base; ?>"
                 src="<?= $existe ? $snapshot_uri : $ph_uri; ?>"
                 data-ph-uri="<?= $ph_uri; ?>"
                 draggable="false"
                 alt="<?= htmlspecialchars($alt, ENT_QUOTES); ?>">
            <span class="cam-card__status"><span class="live-dot" aria-hidden="true"></span> EN VIVO</span>
        </span>
        <span class="cam-card__body">
            <span class="cam-card__grip" aria-hidden="true" title="Arrastra para reordenar">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="9" cy="6" r="1"></circle><circle cx="15" cy="6" r="1"></circle>
                    <circle cx="9" cy="12" r="1"></circle><circle cx="15" cy="12" r="1"></circle>
                    <circle cx="9" cy="18" r="1"></circle><circle cx="15" cy="18" r="1"></circle>
                </svg>
            </span>
            <span class="cam-card__name"><?= htmlspecialchars($descripcion, ENT_QUOTES); ?></span>
            <span class="cam-card__cta">Ver
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                    <path d="M5 12h14"></path><path d="m12 5 7 7-7 7"></path>
                </svg>
            </span>
        </span>
    </button>
    <?php endforeach; ?>
</div>

<script>
    /* Placeholder "Cargando…": visible mientras el snapshot aún no existe;
       se oculta cuando llega la imagen real (dofoto.py o el refresco de 15s). */
    $(function () {
        document.querySelectorAll(".cam-card__media .cam-card__img[data-snapshot]").forEach(function (img) {
            var media = img.closest(".cam-card__media");
            var ph = media ? media.querySelector(".cam-card__placeholder") : null;
            var phUri = img.getAttribute("data-ph-uri") || "";
            if (!ph && !phUri) {
                return;
            }
            img.addEventListener("load", function () {
                if (ph && img.src !== phUri) {
                    ph.style.display = "none";
                }
            });
            img.addEventListener("error", function () {
                if (phUri) {
                    img.src = phUri;
                }
                if (ph) {
                    ph.style.display = "flex";
                }
            });
        });
    });
</script>

<script>
    /* Reordenar la rejilla arrastrando y soltando (HTML5 drag & drop).
       Al soltar, se persiste el orden en camaras.orden vía orden_ajax.php.
       Un clic simple sigue abriendo el modal (el click no se dispara tras un drag real). */
    $(function () {
        var grid = document.getElementById("cam-grid");
        if (!grid) {
            return;
        }
        var arrastrada = null;

        function tarjetas() {
            return Array.prototype.slice.call(grid.querySelectorAll(".cam-card[data-camara-id]"));
        }

        /* Devuelve la tarjeta ANTES de la cual hay que insertar la arrastrada,
           según la posición vertical del cursor; null = insertar al final. */
        function tarjetaInsertar(y) {
            var objetivo = null;
            var mejor = Number.NEGATIVE_INFINITY;
            tarjetas().forEach(function (card) {
                if (card === arrastrada) {
                    return;
                }
                var box = card.getBoundingClientRect();
                var off = y - box.top - box.height / 2;
                if (off < 0 && off > mejor) {
                    mejor = off;
                    objetivo = card;
                }
            });
            return objetivo;
        }

        function marcarInsercion(y) {
            tarjetas().forEach(function (c) { c.classList.remove("is-drop-before"); });
            grid.classList.remove("is-drop-end");
            var objetivo = tarjetaInsertar(y);
            if (objetivo) {
                objetivo.classList.add("is-drop-before");
            } else {
                grid.classList.add("is-drop-end");
            }
        }

        function limpiarIndicadores() {
            tarjetas().forEach(function (c) { c.classList.remove("is-drop-before"); });
            grid.classList.remove("is-drop-end");
        }

        function persistir() {
            var ids = tarjetas().map(function (c) { return c.getAttribute("data-camara-id"); });
            $.post("pages/camaras/orden_ajax.php", { ids: ids.join(",") }, "json")
                .done(function (r) {
                    if (r && r.ok && typeof window.rfToast === "function") {
                        window.rfToast("Orden de cámaras guardado", "ok");
                    }
                })
                .fail(function () {
                    if (typeof window.rfToast === "function") {
                        window.rfToast("No se pudo guardar el orden", "error");
                    }
                });
        }

        grid.addEventListener("dragstart", function (e) {
            var card = e.target && e.target.closest ? e.target.closest(".cam-card[data-camara-id]") : null;
            if (!card) {
                return;
            }
            arrastrada = card;
            e.dataTransfer.effectAllowed = "move";
            try { e.dataTransfer.setData("text/plain", card.getAttribute("data-camara-id")); } catch (_) {}
            window.setTimeout(function () { card.classList.add("is-dragging"); }, 0);
        });

        grid.addEventListener("dragend", function () {
            if (arrastrada) {
                arrastrada.classList.remove("is-dragging");
            }
            arrastrada = null;
            limpiarIndicadores();
        });

        grid.addEventListener("dragover", function (e) {
            if (!arrastrada) {
                return;
            }
            e.preventDefault();
            e.dataTransfer.dropEffect = "move";
            marcarInsercion(e.clientY);
        });

        grid.addEventListener("dragleave", function (e) {
            if (!arrastrada) {
                return;
            }
            /* dragleave burbujea desde los hijos: solo limpia al salir de la rejilla */
            if (e.relatedTarget && grid.contains(e.relatedTarget)) {
                return;
            }
            limpiarIndicadores();
        });

        grid.addEventListener("drop", function (e) {
            if (!arrastrada) {
                return;
            }
            e.preventDefault();
            var objetivo = tarjetaInsertar(e.clientY);
            if (objetivo) {
                grid.insertBefore(arrastrada, objetivo);
            } else {
                grid.appendChild(arrastrada);
            }
            arrastrada.classList.remove("is-dragging");
            arrastrada = null;
            limpiarIndicadores();
            persistir();
        });
    });
</script>
<?php endif; ?>

<?php if (isset($_GET["id"]) && $_GET["id"] !== ""): ?>
<?php
$detalle = DB::selectOne("SELECT * FROM camaras WHERE id = ?", [(int)$_GET["id"]]);
if ($detalle):
    $det_id = (int)$detalle["id"];
    $det_stream = "../live?id=" . $det_id;
    if ($live_token !== "") {
        $det_stream .= "&token=" . urlencode($live_token);
    }
    $det_snap = "fotos_camara/" . $det_id . ".png";
    $det_titulo = camara_label(rf_utf8_normalizar((string)($detalle["descripcion"] ?? "Cámara")));
    $det_args = json_encode(
        [$det_id, $det_stream, $det_snap, $det_titulo],
        JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_HEX_TAG | JSON_HEX_AMP | JSON_HEX_APOS | JSON_HEX_QUOT
    );
?>
<script>
    /* Enlaces antiguos (?page=camaras&id=X): abrir el modal al cargar. */
    $(function () {
        if (typeof window.rfCamModal === "function") {
            window.rfCamModal(...<?= $det_args; ?>);
        }
    });
</script>
<?php endif; ?>
<?php endif; ?>
