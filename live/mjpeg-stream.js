#!/usr/bin/env node
/*
 * RF Live — servidor MJPEG (RTSP → navegador) para la sección "En Directo" del panel.
 *
 * Sustituye al iframe de ipcamlive.com (alias sin configurar -> no cargaba).
 * Para cada cámara lanza `ffmpeg` (RTSP sobre TCP) y sirve el resultado como
 * multipart/x-mixed-replace (MJPEG), que el navegador muestra con un <img> nativo.
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
const TOKEN_WINDOW_S = 300; // validez del token: 5 min (2 ventanas por holgura)

const cameras = new Map(); // id -> fila de ws.php (camaras)
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
/* Stream MJPEG por cámara                                             */
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

  res.writeHead(200, {
    "Content-Type": "multipart/x-mixed-replace; boundary=frame",
    "Cache-Control": "no-store, no-cache, must-revalidate",
    Pragma: "no-cache",
    "X-Accel-Buffering": "no", // desactiva buffering de proxy
  });

  let buf = Buffer.alloc(0);
  const SOI = Buffer.from([0xff, 0xd8]);
  const EOI = Buffer.from([0xff, 0xd9]);

  ff.stdout.on("data", (chunk) => {
    buf = Buffer.concat([buf, chunk]);
    for (;;) {
      const ini = buf.indexOf(SOI);
      if (ini === -1) {
        buf = Buffer.alloc(0); // basura previa al primer JPEG
        break;
      }
      if (ini > 0) buf = buf.subarray(ini);
      const fin = buf.indexOf(EOI, 2);
      if (fin === -1) {
        // frame incompleto: esperar más bytes (descarte si crece demasiado)
        if (buf.length > 5 * 1024 * 1024) buf = Buffer.alloc(0);
        break;
      }
      const frame = buf.subarray(0, fin + 2);
      buf = buf.subarray(fin + 2);
      // backpressure: si el cliente va lento, descartar frames
      if (res.writable && res.writableLength < 1024 * 1024) {
        res.write(frameMjpeg(frame));
      }
    }
  });

  const cerrar = () => {
    try {
      res.end();
    } catch (_) {}
  };

  ff.on("error", (e) => {
    log(`ffmpeg id=${id} error: ${e.message}`);
    cerrar();
  });
  ff.on("close", (code) => {
    if (code !== 0) log(`ffmpeg id=${id} salió con código ${code}`);
    cerrar();
  });
  res.on("close", () => ff.kill("SIGKILL"));
  req.on("close", () => ff.kill("SIGKILL"));
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
    res.end(
      JSON.stringify({
        ok: true,
        cameras: cameras.size,
        lastRefresh: lastRefresh ? lastRefresh.toISOString() : null,
        ids: [...cameras.keys()],
      })
    );
    return;
  }
  res.writeHead(200, { "Content-Type": "text/plain" });
  res.end("RF Live MJPEG — usa /live?id=<camara_id>");
});

server.listen(PORT, HOST, () => {
  log(`escuchando en http://${HOST}:${PORT}`);
  refreshCameras();
  setInterval(refreshCameras, REFRESH_MS);
});

process.on("SIGTERM", () => server.close(() => process.exit(0)));
process.on("SIGINT", () => server.close(() => process.exit(0)));
