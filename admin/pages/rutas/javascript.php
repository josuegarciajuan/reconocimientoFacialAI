<?php
/* 
 * Rutas — JavaScript de dibujado (REFACTOR Fase 3).
 * Consume JSON precalculado (RUTAS + CAMARAS + PLANO_URL), sin PHP-in-JS ni XHR síncrono.
 */
?>

<script>
const PLANO_URL = <?= json_encode($plano_url ?? ""); ?>;
const CAMARAS = <?= $camaras_json; ?>;
const RUTAS = <?= $rutas_json; ?>;

let planoImage = null;
if (PLANO_URL) {
    planoImage = new Image();
    planoImage.src = PLANO_URL;
}

function buscar() {
    const desde = document.getElementById("desde").value;
    const hasta = document.getElementById("hasta").value;
    const persona_id = document.getElementById("persona_id").value;
    location.href = '?page=rutas&buscar=1&desde=' + encodeURIComponent(desde)
        + '&hasta=' + encodeURIComponent(hasta) + '&persona_id=' + encodeURIComponent(persona_id);
}

function ver_ruta(idx) {
    const canvas = document.getElementById("canvasID");
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // plano de fondo
    if (planoImage && planoImage.complete && planoImage.naturalWidth > 0) {
        ctx.drawImage(planoImage, 0, 0, canvas.width, canvas.height);
    }

    // cámaras (marcadores azules)
    ctx.fillStyle = "#D22829";
    ctx.font = "10px Arial";
    CAMARAS.forEach(c => {
        ctx.fillRect(parseInt(c.x), parseInt(c.y), 10, 10);
        ctx.fillText(c.descripcion, parseInt(c.x), parseInt(c.y));
    });

    const ruta = RUTAS[idx];
    if (!ruta || !ruta.puntos || ruta.puntos.length === 0) return;

    ctx.font = "12px Arial";
    ctx.strokeStyle = "#252729";
    ctx.fillStyle = "#252729";

    let prev = null;
    ruta.puntos.forEach((p, i) => {
        const px = parseInt(p.x);
        const py = parseInt(p.y);
        ctx.fillText(p.fecha, px, py + 20);
        if (prev) {
            dibujaSegmento(ctx, prev, { x: px, y: py }, ruta.segmentos[i - 1] || []);
        }
        prev = { x: px, y: py };
    });
}

function dibujaSegmento(ctx, a, b, nodos) {
    ctx.strokeStyle = "#D22829";
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    if (nodos && nodos.length > 0) {
        nodos.forEach(n => ctx.lineTo(parseInt(n[0]), parseInt(n[1])));
    }
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
}
</script>
