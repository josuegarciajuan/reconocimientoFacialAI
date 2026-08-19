<?php
/*
 * Caminos — JavaScript del player (rediseño de Rutas).
 * Reproduce el camino de una persona sobre el plano con un monigote animado:
 *   - Play/Pausa + velocidad (1x..600x) + "ver jornada en X min" (auto ×).
 *   - Scrub por la línea temporal + marcadores de pasos con vídeo ("Ver").
 *   - Cabeza del monigote = avatar PNG recortado transparente (best frontal).
 * Consume el JSON de a=3 (ruta resuelta + líneas del plano) sin recargar.
 */
?>

<script>
const PLANO_URL = <?= json_encode($plano_url ?? ""); ?>;
const CAMARAS = <?= $camaras_json; ?>;
const LINEAS_PLANO = <?= $lineas_plano_json; ?>;

/* Colores del mapa */
const CAM_COLOR = "#D22829";
const LINEA_PLANO_COLOR = "#ffed00";
const RAYO_COLOR = "#ff9500";
const CAMINO_COLOR = "#2596be";
const MONIGOTE_COLOR = "#252729";

let planoImage = null;
if (PLANO_URL) {
    planoImage = new Image();
    planoImage.src = PLANO_URL;
}

/* ------------------------------------------------------------------ */
/* Búsqueda del listado                                                */
/* ------------------------------------------------------------------ */
function buscar() {
    const desde = document.getElementById("desde").value;
    const hasta = document.getElementById("hasta").value;
    const persona_id = document.getElementById("persona_id").value;
    location.href = '?page=rutas&buscar=1&desde=' + encodeURIComponent(desde)
        + '&hasta=' + encodeURIComponent(hasta) + '&persona_id=' + encodeURIComponent(persona_id);
}

/* ------------------------------------------------------------------ */
/* Estado del player                                                   */
/* ------------------------------------------------------------------ */
const Player = {
    ruta: null,          // ruta resuelta (a=3)
    jugando: false,
    velocidad: 10,       // multiplicador (1..600)
    tReal: 0,            // epoch real del recorrido en el que está el monigote
    duracion: 1,         // duración real (s)
    raf: null,
    lastTs: 0,
    fase: 0,             // fase de la animación de caminar
    ultPos: null,        // {x,y} posición previa (para saber si se mueve)
    avatarImg: null,
    canvas: null,
    ctx: null,
    baseCache: null,     // off-screen: plano + cámaras + líneas + camino (estático)
};

/* ------------------------------------------------------------------ */
/* Utilidades                                                          */
/* ------------------------------------------------------------------ */
function PlayerEsc(s) {
    return String(s == null ? "" : s)
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
}

function PlayerCamCoord(id) {
    for (let i = 0; i < CAMARAS.length; i++) {
        if (String(CAMARAS[i].id) === String(id)) return { x: CAMARAS[i].x, y: CAMARAS[i].y };
    }
    return null;
}

/* Polilínea del tramo i (punto i -> i+1) incluyendo los nodos del camino. */
function PlayerTramoPolilinea(i) {
    const pts = Player.ruta.puntos;
    const a = pts[i], b = pts[i + 1];
    const segs = (Player.ruta.segmentos && Player.ruta.segmentos[i]) || [];
    const nodos = (segs[0] && segs[0].nodos) || [];
    const poly = [{ x: a.x, y: a.y }];
    nodos.forEach(function (n) { poly.push({ x: parseInt(n[0], 10), y: parseInt(n[1], 10) }); });
    poly.push({ x: b.x, y: b.y });
    return poly;
}

/* Punto sobre la polilínea a fracción f (0..1) por distancia acumulada. */
function PlayerPuntoEnTramo(poly, f) {
    if (poly.length < 2) return { x: poly[0].x, y: poly[0].y };
    const lens = [], total = (function () {
        let acc = 0;
        for (let i = 0; i < poly.length - 1; i++) {
            const dx = poly[i + 1].x - poly[i].x, dy = poly[i + 1].y - poly[i].y;
            const l = Math.sqrt(dx * dx + dy * dy);
            lens.push(l);
            acc += l;
        }
        return acc;
    })();
    let target = (total <= 0) ? 0 : f * total;
    let acc = 0;
    for (let i = 0; i < lens.length; i++) {
        if (acc + lens[i] >= target || i === lens.length - 1) {
            const t = lens[i] > 0 ? (target - acc) / lens[i] : 0;
            return {
                x: poly[i].x + (poly[i + 1].x - poly[i].x) * t,
                y: poly[i].y + (poly[i + 1].y - poly[i].y) * t
            };
        }
        acc += lens[i];
    }
    const last = poly[poly.length - 1];
    return { x: last.x, y: last.y };
}

/* ------------------------------------------------------------------ */
/* Dibujo del mapa estático (baseCache)                                */
/* ------------------------------------------------------------------ */
function dibujaCurvaSuave(ctx, pts) {
    if (pts.length < 2) return;
    ctx.moveTo(pts[0].x, pts[0].y);
    for (let i = 0; i < pts.length - 1; i++) {
        const p0 = pts[i - 1] || pts[i];
        const p1 = pts[i];
        const p2 = pts[i + 1];
        const p3 = pts[i + 2] || p2;
        ctx.bezierCurveTo(
            p1.x + (p2.x - p0.x) / 6, p1.y + (p2.y - p0.y) / 6,
            p2.x - (p3.x - p1.x) / 6, p2.y - (p3.y - p1.y) / 6,
            p2.x, p2.y
        );
    }
}

function PlayerPintarBase() {
    const W = Player.canvas.width, H = Player.canvas.height;
    if (!Player.baseCache) {
        Player.baseCache = document.createElement("canvas");
        Player.baseCache.width = W;
        Player.baseCache.height = H;
    }
    const ctx = Player.baseCache.getContext("2d");
    ctx.clearRect(0, 0, W, H);

    const dibujar = function () {
        // cámaras
        ctx.fillStyle = CAM_COLOR;
        ctx.font = "10px Arial";
        CAMARAS.forEach(function (c) {
            ctx.fillRect(parseInt(c.x, 10), parseInt(c.y, 10), 10, 10);
            ctx.fillText(c.desc, parseInt(c.x, 10), parseInt(c.y, 10));
        });
        // líneas del plano + rayo de enfoque
        LINEAS_PLANO.forEach(function (L) {
            ctx.strokeStyle = LINEA_PLANO_COLOR;
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(L.x1, L.y1);
            ctx.lineTo(L.x2, L.y2);
            ctx.stroke();
            ctx.fillStyle = LINEA_PLANO_COLOR;
            ctx.fillRect(L.x1 - 3, L.y1 - 3, 6, 6);
            ctx.fillRect(L.x2 - 3, L.y2 - 3, 6, 6);
            ctx.fillText(L.nombre, L.x1, L.y1 - 6);
            if (L.linea_id) {
                const cc = PlayerCamCoord(L.camara_id);
                if (cc) {
                    ctx.save();
                    ctx.strokeStyle = RAYO_COLOR;
                    ctx.lineWidth = 1;
                    ctx.setLineDash([4, 4]);
                    ctx.beginPath();
                    ctx.moveTo(cc.x + 5, cc.y + 5);
                    ctx.lineTo((L.x1 + L.x2) / 2, (L.y1 + L.y2) / 2);
                    ctx.stroke();
                    ctx.restore();
                }
            }
        });
        // camino de la ruta (tramos con nodos, suavizado)
        if (Player.ruta && Player.ruta.puntos) {
            const pts = Player.ruta.puntos;
            for (let i = 0; i < pts.length - 1; i++) {
                const poly = PlayerTramoPolilinea(i);
                ctx.save();
                ctx.strokeStyle = CAMINO_COLOR;
                ctx.lineWidth = 2;
                ctx.beginPath();
                if (poly.length > 2) {
                    dibujaCurvaSuave(ctx, poly);
                } else {
                    ctx.moveTo(poly[0].x, poly[0].y);
                    ctx.lineTo(poly[poly.length - 1].x, poly[poly.length - 1].y);
                }
                ctx.stroke();
                ctx.restore();
            }
            // marcadores de pasos (círculos con hora)
            pts.forEach(function (p, i) {
                ctx.fillStyle = "#ffffff";
                ctx.beginPath();
                ctx.arc(p.x, p.y, 5, 0, Math.PI * 2);
                ctx.fill();
                ctx.strokeStyle = CAMINO_COLOR;
                ctx.lineWidth = 1.5;
                ctx.stroke();
                ctx.fillStyle = "#252729";
                ctx.font = "10px Arial";
                ctx.fillText(p.desc, p.x + 7, p.y + 4);
            });
        }
    };

    if (!PLANO_URL) {
        dibujar();
        return;
    }
    if (planoImage && planoImage.complete && planoImage.naturalWidth > 0) {
        ctx.drawImage(planoImage, 0, 0, W, H);
        dibujar();
        return;
    }
    const img = new Image();
    img.onload = function () { ctx.drawImage(img, 0, 0, W, H); dibujar(); };
    img.onerror = function () { dibujar(); };
    img.src = PLANO_URL;
}

/* ------------------------------------------------------------------ */
/* Monigote (cabeza = avatar transparente)                             */
/* ------------------------------------------------------------------ */
function PlayerDibujarMonigote(ctx, x, y, moviendo) {
    const cabezaR = 13;
    const cy = y - cabezaR - 14;   // centro de la cabeza
    // sombra sutil bajo los pies
    ctx.save();
    ctx.fillStyle = "rgba(0,0,0,0.18)";
    ctx.beginPath();
    ctx.ellipse(x, y + 2, 9, 3, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();

    // cabeza (clip circular + avatar)
    ctx.save();
    ctx.beginPath();
    ctx.arc(x, cy, cabezaR, 0, Math.PI * 2);
    ctx.clip();
    if (Player.avatarImg && Player.avatarImg.complete && Player.avatarImg.naturalWidth > 0) {
        ctx.drawImage(Player.avatarImg, x - cabezaR, cy - cabezaR, cabezaR * 2, cabezaR * 2);
    } else {
        ctx.fillStyle = "#e8c39e";
        ctx.fill();
        ctx.fillStyle = "#252729";
        ctx.font = "10px Arial";
        ctx.textAlign = "center";
        ctx.fillText("👤", x, cy + 4);
        ctx.textAlign = "left";
    }
    ctx.restore();
    ctx.strokeStyle = MONIGOTE_COLOR;
    ctx.lineWidth = 1.4;
    ctx.beginPath();
    ctx.arc(x, cy, cabezaR, 0, Math.PI * 2);
    ctx.stroke();

    // cuerpo (trazos)
    ctx.strokeStyle = MONIGOTE_COLOR;
    ctx.lineWidth = 2.5;
    ctx.lineCap = "round";
    const sw = moviendo ? Math.sin(Player.fase) : 0;
    // torso
    ctx.beginPath(); ctx.moveTo(x, cy + cabezaR); ctx.lineTo(x, cy + cabezaR + 16); ctx.stroke();
    // brazos
    ctx.beginPath(); ctx.moveTo(x, cy + cabezaR + 4); ctx.lineTo(x - 10, cy + cabezaR + 11 + sw * 5); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x, cy + cabezaR + 4); ctx.lineTo(x + 10, cy + cabezaR + 11 - sw * 5); ctx.stroke();
    // piernas
    ctx.beginPath(); ctx.moveTo(x, cy + cabezaR + 16); ctx.lineTo(x - 7, cy + cabezaR + 30 + sw * 4); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(x, cy + cabezaR + 16); ctx.lineTo(x + 7, cy + cabezaR + 30 - sw * 4); ctx.stroke();
}

/* ------------------------------------------------------------------ */
/* Bucle de reproducción                                               */
/* ------------------------------------------------------------------ */
function PlayerRender() {
    const ctx = Player.ctx;
    const W = Player.canvas.width, H = Player.canvas.height;
    ctx.clearRect(0, 0, W, H);
    if (Player.baseCache) {
        ctx.drawImage(Player.baseCache, 0, 0);
    }
    if (!Player.ruta || !Player.ruta.puntos || Player.ruta.puntos.length === 0) return;

    const pos = (function () {
        const pts = Player.ruta.puntos;
        const n = pts.length;
        const t0 = pts[0].t, tn = pts[n - 1].t;
        let i = 0, f = 0;
        if (Player.tReal <= t0) { i = 0; f = 0; }
        else if (Player.tReal >= tn) { i = n - 2; f = 1; }
        else {
            for (let k = 0; k < n - 1; k++) {
                if (Player.tReal >= pts[k].t && Player.tReal <= pts[k + 1].t) {
                    i = k;
                    const dt = pts[k + 1].t - pts[k].t;
                    f = dt > 0 ? (Player.tReal - pts[k].t) / dt : 0;
                    break;
                }
            }
        }
        return { i: i, f: f };
    })();

    const poly = PlayerTramoPolilinea(pos.i);
    const p = PlayerPuntoEnTramo(poly, pos.f);
    const moviendo = !Player.ultPos || Math.abs(p.x - Player.ultPos.x) + Math.abs(p.y - Player.ultPos.y) > 0.5;
    if (moviendo) Player.fase += 0.35 * Math.max(1, Player.velocidad / 10);
    Player.ultPos = p;
    PlayerDibujarMonigote(ctx, p.x, p.y, moviendo);
}

function PlayerStep(ts) {
    if (!Player.jugando) return;
    if (!Player.lastTs) Player.lastTs = ts;
    const dt = (ts - Player.lastTs) / 1000;
    Player.lastTs = ts;
    if (dt > 0 && dt < 1) {
        Player.tReal += dt * Player.velocidad;
        if (Player.tReal >= Player.ruta.puntos[Player.ruta.puntos.length - 1].t) {
            Player.tReal = Player.ruta.puntos[Player.ruta.puntos.length - 1].t;
            PlayerPausar();
        }
        PlayerActualizarUI();
    }
    PlayerRender();
    if (Player.jugando) {
        Player.raf = requestAnimationFrame(PlayerStep);
    }
}

function PlayerActualizarUI() {
    // hora actual
    const el = document.getElementById("caminoHora");
    if (el && Player.ruta && Player.ruta.puntos.length) {
        const d = new Date(Player.tReal * 1000);
        const f = d.toLocaleDateString("es-ES") + " " + d.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
        el.textContent = "🕐 " + f;
    }
    // scrub
    const scrub = document.getElementById("caminoScrub");
    if (scrub && Player.ruta && Player.ruta.puntos.length) {
        const t0 = Player.ruta.puntos[0].t, tn = Player.ruta.puntos[Player.ruta.puntos.length - 1].t;
        scrub.value = Math.round(((Player.tReal - t0) / Math.max(1, tn - t0)) * 1000);
    }
    // botón play
    const btn = document.getElementById("caminoPlay");
    if (btn) btn.textContent = Player.jugando ? "⏸ Pausa" : "▶ Play";
}

function PlayerPlay() {
    if (!Player.ruta) return;
    Player.jugando = true;
    Player.lastTs = 0;
    PlayerActualizarUI();
    Player.raf = requestAnimationFrame(PlayerStep);
}

function PlayerPausar() {
    Player.jugando = false;
    if (Player.raf) cancelAnimationFrame(Player.raf);
    Player.raf = null;
    PlayerActualizarUI();
}

function PlayerToggle() {
    if (Player.jugando) PlayerPausar();
    else PlayerPlay();
}

/* ------------------------------------------------------------------ */
/* Controles                                                           */
/* ------------------------------------------------------------------ */
function PlayerVelocidad(v) {
    Player.velocidad = parseInt(v, 10) || 10;
    const obj = document.getElementById("caminoObjetivo");
    if (obj) obj.value = "0"; // manual
}

function PlayerObjetivo(min) {
    min = parseInt(min, 10) || 0;
    if (min <= 0 || !Player.ruta) return;
    const duracion = (Player.ruta.puntos[Player.ruta.puntos.length - 1].t - Player.ruta.puntos[0].t);
    const vel = Math.max(1, Math.round(duracion / (min * 60)));
    Player.velocidad = vel;
    const sel = document.getElementById("caminoVelocidad");
    if (sel) {
        // si no existe la opción exacta, la añade
        if (![...sel.options].some(o => o.value === String(vel))) {
            const opt = document.createElement("option");
            opt.value = vel;
            opt.textContent = "×" + vel;
            sel.appendChild(opt);
        }
        sel.value = String(vel);
    }
    if (typeof rfToast === "function") {
        rfToast("Jornada (" + Math.round(duracion / 3600 * 10) / 10 + " h) en " + min + " min → ×" + vel, "ok");
    }
}

function PlayerScrub(pct) {
    if (!Player.ruta || !Player.ruta.puntos.length) return;
    const t0 = Player.ruta.puntos[0].t, tn = Player.ruta.puntos[Player.ruta.puntos.length - 1].t;
    Player.tReal = t0 + (parseInt(pct, 10) / 1000) * (tn - t0);
    PlayerActualizarUI();
    PlayerRender();
}

function PlayerVerVideo(videoId, camaraDesc, fecha, personaId, personaNombre) {
    PlayerPausar();
    if (typeof rfVideoModal === "function") {
        rfVideoModal(
            videoId,
            "../video.php?id=" + videoId,
            "../video.php?id=" + videoId + "&poster=1",
            "Camino · " + camaraDesc + " · " + fecha,
            personaId,
            personaNombre
        );
    } else {
        window.open("../video.php?id=" + videoId, "_blank");
    }
}

function PlayerRegenerarAvatar() {
    if (!Player.ruta) return;
    const personaId = Player.ruta.persona_id;
    if (typeof rfToast === "function") rfToast("Generando avatar…", "ok");
    fetch("acciones_ajax.php?a=4", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ persona_id: personaId })
    })
    .then(function (res) { return res.json(); })
    .then(function (data) {
        if (data && data.png) {
            PlayerCargarAvatar(data.png);
        } else {
            setTimeout(function () { abrirCamino(Player.ruta.inicio_id, true); }, 6000);
        }
    })
    .catch(function () {});
}

function PlayerCargarAvatar(url) {
    if (!url) return;
    const img = new Image();
    img.onload = function () { Player.avatarImg = img; PlayerRender(); };
    img.src = url;
}

function PlayerRenderPasos() {
    const cont = document.getElementById("caminoPasos");
    if (!cont || !Player.ruta) return;
    const pts = Player.ruta.puntos;
    let html = "";
    pts.forEach(function (p, i) {
        const fecha = new Date(p.t * 1000);
        const hora = fecha.toLocaleTimeString("es-ES", { hour: "2-digit", minute: "2-digit" });
        const tiene = p.video_id ? 1 : 0;
        html += '<button type="button" class="camino-paso button button--sm ' + (tiene ? "bg-theme-1 text-white" : "bg-gray-800 text-gray-400")
            + '" onclick="if(' + tiene + '){PlayerVerVideo(' + p.video_id + ',\'' + PlayerEsc(p.desc).replace(/'/g, "\\'")
            + '\',\'' + hora + '\',' + Player.ruta.persona_id + ',\'' + PlayerEsc(Player.ruta.nombre).replace(/'/g, "\\'") + '\');}else{PlayerScrub('
            + Math.round(((p.t - pts[0].t) / Math.max(1, pts[pts.length - 1].t - pts[0].t)) * 1000) + ');}"'
            + ' title="' + (tiene ? "Ver el vídeo de este paso" : "Saltar a este paso") + '">'
            + hora + " · " + PlayerEsc(p.desc)
            + (tiene ? " ▶" : "")
            + '</button>';
    });
    cont.innerHTML = html;
}

/* ------------------------------------------------------------------ */
/* Carga del camino (AJAX a=3)                                         */
/* ------------------------------------------------------------------ */
function abrirCamino(inicioId, recargarAvatar) {
    fetch("acciones_ajax.php?a=3&inicio_id=" + inicioId)
        .then(function (res) {
            if (!res.ok) throw new Error("HTTP " + res.status);
            return res.json();
        })
        .then(function (data) {
            if (!data || !data.ok || !data.ruta) throw new Error("ruta inválida");
            PlayerPausar();
            Player.ruta = data.ruta;
            Player.velocidad = 10;
            const sel = document.getElementById("caminoVelocidad");
            if (sel) sel.value = "10";
            const t0 = Player.ruta.puntos[0].t;
            Player.tReal = t0;
            Player.ultPos = null;
            Player.fase = 0;
            const titulo = document.getElementById("caminoTitulo");
            if (titulo) titulo.textContent = "Camino · " + Player.ruta.nombre + " · " + Player.ruta.num_camaras + " cámaras";
            // avatar
            Player.avatarImg = null;
            if (Player.ruta.avatar) PlayerCargarAvatar(Player.ruta.avatar);
            PlayerPintarBase();
            PlayerRenderPasos();
            PlayerActualizarUI();
            PlayerRender();
            if (recargarAvatar) PlayerPlay();
        })
        .catch(function (err) {
            if (typeof rfToast === "function") rfToast("No se pudo cargar el camino: " + err.message, "err");
            else alert("No se pudo cargar el camino: " + err.message);
        });
}

/* Inicialización al cargar la página */
document.addEventListener("DOMContentLoaded", function () {
    const canvas = document.getElementById("canvasID");
    if (!canvas) return;
    Player.canvas = canvas;
    Player.ctx = canvas.getContext("2d");
    PlayerPintarBase();
    // deep-link desde la ficha de persona: autoplay de su último camino
    const urlParams = new URLSearchParams(window.location.search);
    const personaAuto = urlParams.get("persona_id");
    if (personaAuto) {
        const tabla = document.querySelector("table tbody");
        const primeraFila = tabla ? tabla.querySelector("tr") : null;
        if (primeraFila) {
            const btn = primeraFila.querySelector('[onclick*="abrirCamino"]');
            if (btn) {
                const m = btn.getAttribute("onclick").match(/abrirCamino\((\d+)/);
                if (m) abrirCamino(parseInt(m[1], 10));
            }
        }
    }
});
</script>
