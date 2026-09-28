#!/usr/bin/env node
/*
 * RF Live — servidor MJPEG (RTSP → navegador) para la sección "En Directo" del panel.
 *
 * Sustituye al iframe de ipcamlive.com (alias sin configurar -> no cargaba).
 * Para cada cámara lanza UN solo `ffmpeg` (RTSP sobre TCP) y sirve el resultado
 * como multipart/x-mixed-replace (MJPEG) a TODOS los espectadores a la vez.
 *
 * F5 (rendimiento): antes cada espectador lanzaba su propio ffmpeg (decodificación
 * RTSP completa por pestaña/cliente) -> con varias pestañas abiertas el coste se
 * multiplicaba. Ahora hay un único ffmpeg por cámara con fan-out a N clientes; el
 * proceso se mantiene IDLE_MS tras quedarse sin espectadores (tolera reconexiones)
 * y se mata al agotarse. La salida por cliente es idéntica.
 *
 * Uso:
 *   node live/mjpeg-stream.js
 *
 * Variables de entorno (opcionales):
 *   LIVE_PORT        puerto de escucha            (def: 8084, solo 127.0.0.1)
 *   RF_WS_URL        endpoint ws.php para listar cámaras (def: 127.0.0.1:8090)
 *   RF_LIVE_TOKEN    secreto HMAC para validar el token del panel (si vacío, sin auth)
 *   LIVE_FFMPEG      binario ffmpeg                (def: ffmpeg)
 *   LIVE_FPS         fps del stream                (def: 5)
 *   LIVE_SCALE       escala (ffmpeg -vf)           (def: 640:-2)
 *   LIVE_QUALITY     calidad JPEG (-q:v)           (def: 6)
 *   LIVE_IDLE_MS     ms que se mantiene el ffmpeg sin espectadores (def: 5000)
 *
 * Nota de seguridad: no se registran las URL RTSP (contienen credenciales); solo
 * el id de cámara y códigos de salida.
 */

const http = require("http");
const { spawn } = require("child_process");
const { createHmac, timingSafeEqual } = require("crypto");

const PORT = parseInt(process.env.LIVE_PORT || "8084", 10);
const HOST = "127.0.0.1"; // solo local; Apache expone el flujo vía proxy
const WS_URL =
  process.env.RF_WS_URL ||
  "http://127.0.0.1:8090/reconocimientoFacial/ws.php";
const SECRET = process.env.RF_LIVE_TOKEN || process.env.LIVE_SECRET || "";
const FFMPEG = process.env.LIVE_FFMPEG || "ffmpeg";
const FPS = parseInt(process.env.LIVE_FPS || "5", 10);
const SCALE = process.env.LIVE_SCALE || "640:-2";
const QUALITY = process.env.LIVE_QUALITY || "6";
const REFRESH_MS = parseInt(process.env.LIVE_REFRESH_MS || "10000", 10);
const IDLE_MS = parseInt(process.env.LIVE_IDLE_MS || "5000", 10);
const TOKEN_WINDOW_S = 300; // validez del token: 5 min (2 ventanas por holgura)
const MAX_BUFFER = 5 * 1024 * 1024; // descarte de un frame incompleto gigante
const MAX_CLIENT_BACKLOG = 1024 * 1024; // backpressure por cliente

const cameras = new Map(); // id -> fila de ws.php (camaras)
const streams = new Map(); // id -> { proc, subs:Set<res>, buf, idle }
let lastRefresh = null;

function log(...args) {
  const ts = new Date().toISOString();
  console.error(`[live ${ts}]`, ...args);
}

/* ------------------------------------------------------------------ */
/* Caché de cámaras (misma fuente que capturador.php: ws.php)          */
/* ------------------------------------------------------------------ */

function refreshCameras() {
  const url =
    `${WS_URL}?accion=consultar&tabla=camaras` +
    `&condicion=${encodeURIComponent("sistema=0 and encendida=1")}` +
    `&orden=${encodeURIComponent("id asc")}`;
  http
    .get(url, (res) => {
      let body = "";
      res.setEncoding("utf8");
      res.on("data", (c) => (body += c));
      res.on("end", () => {
        try {
          const data = JSON.parse(body);
          if (data.cod === "200" && Array.isArray(data.valores)) {
            cameras.clear();
            for (const c of data.valores) {
              cameras.set(String(c.id), c);
            }
            lastRefresh = new Date();
            log(`caché de cámaras: ${cameras.size}`);
          }
        } catch (e) {
          log(`error parseando ws.php: ${e.message}`);
        }
      });
    })
    .on("error", (e) => log(`error consultando ws.php: ${e.message}`));
}

/* ------------------------------------------------------------------ */
/* Token HMAC (válido ~5 min) — evita que el flujo se consuma sin      */
/* pasar por el panel autenticado.                                     */
/* ------------------------------------------------------------------ */

function tokenValido(id, token) {
  if (!SECRET) return true; // sin secreto configurado: modo compatible
  if (!token) return false;
  const ahora = Math.floor(Date.now() / 1000);
  const ventana = Math.floor(ahora / TOKEN_WINDOW_S);
  for (const w of [ventana, ventana - 1]) {
    const esperado = createHmac("sha256", SECRET)
      .update(`live:${id}:${w}`)
      .digest("hex");
    try {
      const a = Buffer.from(token, "utf8");
      const b = Buffer.from(esperado, "utf8");
      if (a.length === b.length && timingSafeEqual(a, b)) return true;
    } catch (_) {
      /* token malformado */
    }
  }
  return false;
}

/* ------------------------------------------------------------------ */
/* Stream MJPEG compartido por cámara                                  */
/* ------------------------------------------------------------------ */

function urlDeLaCamara(cam) {
  const desdeServer = (cam.url_desdeserver || "").trim();
  return desdeServer !== "" ? desdeServer : (cam.url_conexion || "").trim();
}

function frameMjpeg(frame) {
  const header = Buffer.from(
    `--frame\r\nContent-Type: image/jpeg\r\nContent-Length: ${frame.length}\r\n\r\n`
  );
  return Buffer.concat([header, frame, Buffer.from("\r\n")]);
}

const SOI = Buffer.from([0xff, 0xd8]);
const EOI = Buffer.from([0xff, 0xd9]);

/** Reparte un frame JPEG a todos los espectadores (con backpressure por cliente). */
function fanout(st, frame) {
  if (st.subs.size === 0) return;
  const packet = frameMjpeg(frame);
  for (const res of st.subs) {
    if (res.writable && res.writableLength < MAX_CLIENT_BACKLOG) {
      try {
        res.write(packet);
      } catch (_) {
        /* el cliente se fue: su handler close lo limpiará */
      }
    }
  }
}

/** Cierra el stream y termina a todos los espectadores (proceso muerto). */
function teardown(id, code) {
  const st = streams.get(id);
  if (!st) return;
  streams.delete(id);
  if (st.idle) clearTimeout(st.idle);
  for (const res of st.subs) {
    try {
      res.end();
    } catch (_) {}
  }
  st.subs.clear();
  if (code !== undefined && code !== 0) {
    log(`ffmpeg id=${id} salió con código ${code}`);
  }
}

function killStream(id) {
  const st = streams.get(id);
  if (!st) return;
  streams.delete(id);
  if (st.idle) clearTimeout(st.idle);
  try {
    st.proc.kill("SIGKILL");
  } catch (_) {}
}

/** Lanza (o reutiliza) el ffmpeg de una cámara y devuelve su entrada de stream. */
function getStream(id, url) {
  let st = streams.get(id);
  if (st) return st;

  const args = [
    "-rtsp_transport", "tcp",
    "-loglevel", "error",
    "-i", url,
    "-vf", `fps=${FPS},scale=${SCALE}`,
    "-q:v", String(QUALITY),
    "-f", "mjpeg",
    "-",
  ];
  const ff = spawn(FFMPEG, args, { stdio: ["ignore", "pipe", "ignore"] });
  st = { proc: ff, subs: new Set(), buf: Buffer.alloc(0), idle: null };
  streams.set(id, st);

  ff.stdout.on("data", (chunk) => {
    st.buf = Buffer.concat([st.buf, chunk]);
    for (;;) {
      const ini = st.buf.indexOf(SOI);
      if (ini === -1) {
        st.buf = Buffer.alloc(0); // basura previa al primer JPEG
        break;
      }
      if (ini > 0) st.buf = st.buf.subarray(ini);
      const fin = st.buf.indexOf(EOI, 2);
      if (fin === -1) {
        if (st.buf.length > MAX_BUFFER) st.buf = Buffer.alloc(0);
        break;
      }
      const frame = st.buf.subarray(0, fin + 2);
      st.buf = st.buf.subarray(fin + 2);
      fanout(st, frame);
    }
  });

  ff.on("error", (e) => {
    log(`ffmpeg id=${id} error: ${e.message}`);
    teardown(id);
  });
  ff.on("close", (code) => teardown(id, code));
  return st;
}

function handleLive(req, res) {
  const u = new URL(req.url, `http://${HOST}:${PORT}`);
  const id = u.searchParams.get("id");
  const token = u.searchParams.get("token");

  if (!id) {
    res.writeHead(400, { "Content-Type": "text/plain" });
    res.end("id requerido");
    return;
  }
  if (!tokenValido(id, token)) {
    res.writeHead(403, { "Content-Type": "text/plain" });
    res.end("token inválido");
    return;
  }

  const cam = cameras.get(String(id));
  if (!cam) {
    res.writeHead(404, { "Content-Type": "text/plain" });
    res.end("cámara no disponible");
    return;
  }
  const url = urlDeLaCamara(cam);
  if (!url) {
    res.writeHead(404, { "Content-Type": "text/plain" });
    res.end("cámara sin URL de conexión");
    return;
  }

  res.writeHead(200, {
    "Content-Type": "multipart/x-mixed-replace; boundary=frame",
    "Cache-Control": "no-store, no-cache, must-revalidate",
    Pragma: "no-cache",
    "X-Accel-Buffering": "no", // desactiva buffering de proxy
  });

  const st = getStream(String(id), url);
  // Si el stream estaba en periodo de gracia, cancelar el cierre.
  if (st.idle) {
    clearTimeout(st.idle);
    st.idle = null;
  }
  st.subs.add(res);

  let cerrado = false;
  const cerrar = () => {
    if (cerrado) return;
    cerrado = true;
    st.subs.delete(res);
    try {
      res.end();
    } catch (_) {}
    // último espectador: mantener ffmpeg IDLE_MS por si vuelve a conectarse
    if (st.subs.size === 0 && streams.get(String(id)) === st) {
      st.idle = setTimeout(() => killStream(String(id)), IDLE_MS);
    }
  };
  res.on("close", cerrar);
  req.on("close", cerrar);
}

/* ------------------------------------------------------------------ */
/* HTTP server                                                         */
/* ------------------------------------------------------------------ */

const server = http.createServer((req, res) => {
  const u = new URL(req.url, `http://${HOST}:${PORT}`);
  if (u.pathname === "/live") {
    handleLive(req, res);
    return;
  }
  if (u.pathname === "/status") {
    res.writeHead(200, { "Content-Type": "application/json" });
    const detalle = {};
    for (const [id, st] of streams) {
      detalle[id] = { espectadores: st.subs.size, idle: st.idle !== null };
    }
    res.end(
      JSON.stringify({
        ok: true,
        cameras: cameras.size,
        streams: streams.size,
        lastRefresh: lastRefresh ? lastRefresh.toISOString() : null,
        ids: [...cameras.keys()],
        detalle,
      })
    );
    return;
  }
  res.writeHead(200, { "Content-Type": "text/plain" });
  res.end("RF Live MJPEG — usa /live?id=<camara_id>");
});

server.listen(PORT, HOST, () => {
  log(`escuchando en http://${HOST}:${PORT} (fan-out: 1 ffmpeg por cámara)`);
  refreshCameras();
  setInterval(refreshCameras, REFRESH_MS);
});

process.on("SIGTERM", () => {
  for (const id of [...streams.keys()]) killStream(id);
  server.close(() => process.exit(0));
});
process.on("SIGINT", () => {
  for (const id of [...streams.keys()]) killStream(id);
  server.close(() => process.exit(0));
});
