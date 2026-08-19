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

/* Suavizado de curvas (Catmull-Rom) cuando un segmento tiene >=2 nodos. */
const RUTAS_SUAVIZADO = true;

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

function dibujaCurvaSuave(ctx, pts) {
    // Catmull-Rom → Bézier cúbica, pasando por todos los puntos (pts: [{x,y},...]).
    if (pts.length < 2) return;
    ctx.moveTo(pts[0].x, pts[0].y);
    for (var i = 0; i < pts.length - 1; i++) {
        var p0 = pts[i - 1] || pts[i];
        var p1 = pts[i];
        var p2 = pts[i + 1];
        var p3 = pts[i + 2] || p2;
        ctx.bezierCurveTo(
            p1.x + (p2.x - p0.x) / 6, p1.y + (p2.y - p0.y) / 6,
            p2.x - (p3.x - p1.x) / 6, p2.y - (p3.y - p1.y) / 6,
            p2.x, p2.y
        );
    }
}

/* Dibuja el segmento entre dos cámaras. `cadenas` = [{camino, nodos:[[x,y],...]}, ...].
 * - Sin cadenas → recta discontinua + aviso.
 * - Una o más cadenas → polilínea (suavizada si hay >=2 nodos); las alternativas atenuadas. */
function dibujaSegmento(ctx, a, b, cadenas) {
    var cs = cadenas || [];
    if (!cs.length) {
        ctx.save();
        ctx.strokeStyle = "#D22829";
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = "#b8860b";
        ctx.font = "10px Arial";
        ctx.fillText("⚠ sin nodos", (a.x + b.x) / 2, (a.y + b.y) / 2);
        ctx.restore();
        return;
    }
    cs.forEach(function (cadena, ci) {
        var nodos = cadena.nodos || [];
        var pts = [{ x: a.x, y: a.y }];
        nodos.forEach(function (n) { pts.push({ x: parseInt(n[0]), y: parseInt(n[1]) }); });
        pts.push({ x: b.x, y: b.y });

        ctx.save();
        ctx.strokeStyle = "#D22829";
        if (ci > 0) {
            ctx.globalAlpha = 0.35;       // caminos alternativos atenuados
            ctx.setLineDash([4, 4]);
        }
        ctx.beginPath();
        if (RUTAS_SUAVIZADO && nodos.length >= 2) {
            dibujaCurvaSuave(ctx, pts);
        } else {
            ctx.moveTo(pts[0].x, pts[0].y);
            for (var k = 1; k < pts.length; k++) {
                ctx.lineTo(pts[k].x, pts[k].y);
            }
        }
        ctx.stroke();
        ctx.restore();
    });
}
</script>
