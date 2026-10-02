#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Puente del pool para `classify` (M3 de SuperServer) — split de embeddings.

Lo lanza `detector.php` (en modo `superserver`) en lugar de `clasificador.py`.
Para cada cámara del grupo:

  1. Envía los crops de `motor/caras/sinclasificar/<local>/<cam>/` al pool.
  2. Espera `faces.json` (detección + SR + embedding por crop).
  3. Ejecuta el `clasificador.py` LOCAL con `--once --faces-json <tmp>`: la casa
     decide y escribe la galería (único escritor); solo se evita `analyze` +
     `enhance_embedding` (lo pesado), que ya vino del pool.

Si el modo es `local`, ejecuta `clasificador.py` tal cual (sin cambios).

Uso (lo lanza detector.php; el token final de Jos_Thread se ignora):
    <venv>/python motor/clasificador_bridge.py <local> <cam[,cam2]> --ruta <RUTA> [TOKEN]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.pool_ack import escribir_ack, job_dir_of, fingerprint  # noqa: E402

MODE_FILE = "/var/lib/taildeck/projects/reconocimientoFacial.mode"
SPOOL_DIR = "/var/lib/taildeck/spool"
RETURNS_DIR = "/var/lib/taildeck/returns/reconocimientoFacial"
PROYECTO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
IMG_EXTS = (".jpg", ".jpeg", ".png")
# F18: el stdout del bridge va a /dev/null (Jos_Thread), así que se registra en
# fichero para poder diagnosticar el dispatcher en producción.
BRIDGE_LOG = os.path.join(PROYECTO, "motor/logs/clasificador_bridge.log")


def _blog(*args, **kwargs) -> None:
    try:
        os.makedirs(os.path.dirname(BRIDGE_LOG), exist_ok=True)
        with open(BRIDGE_LOG, "a", encoding="utf-8") as fh:
            fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(a) for a in args) + "\n")
    except OSError:
        pass


def modo() -> str:
    try:
        with open(MODE_FILE, encoding="utf-8") as fh:
            return "superserver" if fh.read().strip() == "superserver" else "local"
    except OSError:
        return "local"


def _batch_id(nombres: list[str]) -> str:
    """Id estable del lote a partir de sus ficheros (mismo contenido → mismo id)."""
    h = hashlib.sha1("\n".join(nombres).encode("utf-8", "replace")).hexdigest()
    return h[:12]


def build_request(local_id: str, camara_id: str, carpeta: str,
                  batch_id: str | None = None, busto_dir: str | None = None,
                  fingerprint_val: str | None = None, rid: str | None = None) -> dict:
    rid = rid or f"req-{int(time.time())}-{os.getpid()}"
    ext = f"classify:{local_id}/{camara_id}" + (f"/{batch_id}" if batch_id else "")
    params = {"local": local_id, "cam": camara_id, "dir": carpeta, "batch": batch_id}
    if busto_dir:
        params["bustoDir"] = busto_dir
    return {
        "id": rid,
        "project": "reconocimientoFacial",
        "process": "classify",
        "params": params,
        "externalId": ext,
        "fingerprint": fingerprint_val,
    }


def escribir_peticion(req: dict) -> str:
    os.makedirs(SPOOL_DIR, exist_ok=True)
    dst = os.path.join(SPOOL_DIR, f"{req['id']}.json")
    tmp = dst + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(req, fh, ensure_ascii=False)
    os.replace(tmp, dst)
    return dst


def _artifact_root(d: str) -> str:
    return os.path.join(d, "result") if os.path.isdir(os.path.join(d, "result")) else d


def _leer_faces(d: str, local_id: str, camara_id: str, batch_id: str | None) -> dict | None:
    root = _artifact_root(d)
    f = os.path.join(root, "faces.json")
    if not os.path.exists(f):
        return None
    try:
        with open(f, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    if str(data.get("local")) != str(local_id) or str(data.get("cam")) != str(camara_id):
        return None
    if batch_id is not None and data.get("batch") != batch_id:
        return None
    # F17a: se devuelve el resultado completo {faces, busto} (compatible con el
    # formato antiguo {filename: faces}).
    return data


def esperar_faces(local_id: str, camara_id: str, batch_id: str | None,
                  timeout_s: float, poll_s: float = 5.0):
    """Espera el faces.json del LOTE y devuelve (faces, job_dir) o None."""
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if os.path.isdir(RETURNS_DIR):
            for d in sorted(os.listdir(RETURNS_DIR)):
                full = os.path.join(RETURNS_DIR, d)
                if not os.path.isdir(full):
                    continue
                faces = _leer_faces(full, local_id, camara_id, batch_id)
                if faces is not None:
                    return faces, full
        time.sleep(poll_s)
    return None


def buscar_faces(local_id: str, camara_id: str, batch_id: str | None):
    """Escanea UNA vez los retornos y devuelve (data, job_dir) si el lote ya está (F18)."""
    if not os.path.isdir(RETURNS_DIR):
        return None
    for d in os.listdir(RETURNS_DIR):
        full = os.path.join(RETURNS_DIR, d)
        if not os.path.isdir(full):
            continue
        data = _leer_faces(full, local_id, camara_id, batch_id)
        if data is not None:
            return data, full
    return None


def _rmtree(path: str) -> None:
    try:
        shutil.rmtree(path, ignore_errors=True)
    except OSError:
        pass


def _aplicar_local(ruta: str, local_id, camara_id, batch_id: str, data: dict, timeout: float) -> int:
    """Aplica el lote con el aplicador persistente si está vivo; si no, `--once`.

    `data` es el resultado del worker: {faces, busto, ...} (o el formato antiguo).
    """
    faces = data.get("faces") if isinstance(data, dict) else None
    busto = data.get("busto") if isinstance(data, dict) else None
    if faces is None:
        faces, busto = data, {}  # formato antiguo: el propio dict son las caras
    try:
        from motor import clasificador_queue as q
        if q.daemon_alive(ruta, local_id):
            if q.write_request(ruta, local_id, batch_id, camara_id, faces, busto):
                got = q.esperar_done(ruta, local_id, batch_id, timeout)
                if got is not None:
                    return int(got.get("rc") or 0)
                _blog("[classify-bridge] timeout del aplicador; fallback a --once", flush=True)
    except Exception as e:  # noqa: BLE001
        _blog(f"[classify-bridge] aplicador persistente no disponible: {e}", flush=True)

    tmp = os.path.join(ruta, "motor/caras", f".faces_{local_id}_{camara_id}_{batch_id}.json")
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        cmd = [sys.executable, os.path.join(PROYECTO, "motor/clasificador.py"),
               str(local_id), str(camara_id), "--ruta", ruta, "--once", "--faces-json", tmp]
        return subprocess.call(cmd)
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass


def _build_batch(local_id: str, camara_id: str, ruta: str, dir_in: str, chunk: list[str]) -> dict:
    """Materializa el lote (enlaces) + bustos y devuelve {batch_id,bdir,bdir_busto,req}."""
    batch_id = _batch_id(chunk)
    bdir = os.path.join(ruta, "motor/caras", f".batch_{local_id}_{camara_id}_{batch_id}")
    _rmtree(bdir)
    os.makedirs(bdir, exist_ok=True)
    for f in chunk:
        src = os.path.join(dir_in, f)
        try:
            os.link(src, os.path.join(bdir, f))       # sin copiar contenido
        except OSError:
            shutil.copy2(src, os.path.join(bdir, f))

    # F17a: bustos compañeros del lote (para delegar la detección de display).
    busto_src = os.path.join(os.path.dirname(dir_in), f"{camara_id}_busto")
    bdir_busto = os.path.join(ruta, "motor/caras", f".batch_{local_id}_{camara_id}_{batch_id}_busto")
    _rmtree(bdir_busto)
    busto_dir = None
    if os.path.isdir(busto_src):
        os.makedirs(bdir_busto, exist_ok=True)
        stems = {f.rsplit(".", 1)[0] for f in chunk}
        n_busto = 0
        try:
            for name in sorted(os.listdir(busto_src)):
                if name.rsplit(".", 1)[0] not in stems:
                    continue
                try:
                    os.link(os.path.join(busto_src, name), os.path.join(bdir_busto, name))
                except OSError:
                    shutil.copy2(os.path.join(busto_src, name), os.path.join(bdir_busto, name))
                n_busto += 1
        except OSError:
            n_busto = 0
        busto_dir = bdir_busto if n_busto else None
        if not n_busto:
            _rmtree(bdir_busto)

    req = build_request(local_id, camara_id, bdir, batch_id=batch_id, busto_dir=busto_dir,
                        fingerprint_val=finger_blog([os.path.join(bdir, f) for f in chunk]))
    return {"batch_id": batch_id, "bdir": bdir, "bdir_busto": bdir_busto, "req": req}


def _limpiar_batch(ruta: str, local_id, camara_id, batch_id: str) -> None:
    base = os.path.join(ruta, "motor/caras")
    _rmtree(os.path.join(base, f".batch_{local_id}_{camara_id}_{batch_id}"))
    _rmtree(os.path.join(base, f".batch_{local_id}_{camara_id}_{batch_id}_busto"))


def _procesar_lote(local_id: str, camara_id: str, ruta: str, dir_in: str,
                   chunk: list[str], timeout: float, poll: float) -> bool:
    """Prepara el lote (enlaces), lo delega y aplica la decisión local. True si ok."""
    b = _build_batch(local_id, camara_id, ruta, dir_in, chunk)
    batch_id, bdir, bdir_busto, req = b["batch_id"], b["bdir"], b["bdir_busto"], b["req"]
    escribir_peticion(req)
    n_busto = len(os.listdir(bdir_busto)) if os.path.isdir(bdir_busto) else 0
    _blog(f"[classify-bridge] petición {req['id']} para {req['externalId']} "
          f"({len(chunk)} crops, {n_busto} bustos)", flush=True)

    got = esperar_faces(local_id, camara_id, batch_id, timeout, poll)
    if not got:
        _blog(f"[classify-bridge] timeout esperando faces de {req['externalId']}", flush=True)
        _limpiar_batch(ruta, local_id, camara_id, batch_id)
        return False
    data, job_dir = got

    rc = _aplicar_local(ruta, local_id, camara_id, batch_id, data, timeout)
    if rc == 0:
        escribir_ack(job_dir_of(job_dir), source="clasificador_bridge")
    _blog(f"[classify-bridge] {camara_id} lote {batch_id}: decisión local aplicada (rc={rc})", flush=True)
    _limpiar_batch(ruta, local_id, camara_id, batch_id)
    return rc == 0


def _cola_aplicador(ruta: str, local_id) -> int:
    """Nº de peticiones pendientes en la cola del aplicador (backpressure F18)."""
    try:
        from motor import clasificador_queue as q
        d = q._paths(ruta, local_id)["in"]
        return len([n for n in os.listdir(d) if n.endswith(".json")])
    except OSError:
        return 0


def _procesar_cam_paralelo(local_id: str, camara_id: str, ruta: str, dir_in: str,
                           chunks: list[list[str]], timeout: float, poll: float,
                           inflight: int, k_queue: int) -> int:
    """F18: hasta `inflight` lotes en vuelo (pool en paralelo) y aplicación FIFO.

    La galería sigue serializándose en el aplicador (escritor único): los
    resultados se aplican en ORDEN de submisión (buffer `ready`), preservando la
    semántica del bridge secuencial.
    """
    from collections import deque  # noqa: E402
    pend = deque(chunks)
    en_vuelo: dict[str, dict] = {}
    ready: dict[str, tuple] = {}
    orden: list[str] = []
    aplicados = 0
    progreso = False
    last_hb = 0.0

    while pend or en_vuelo or ready:
        # 1) Enviar hasta el límite (respetando la cola del aplicador).
        while pend and len(en_vuelo) < inflight and (_cola_aplicador(ruta, local_id) + len(ready)) < k_queue:
            ch = pend.popleft()
            b = _build_batch(local_id, camara_id, ruta, dir_in, ch)
            escribir_peticion(b["req"])
            n_busto = len(os.listdir(b["bdir_busto"])) if os.path.isdir(b["bdir_busto"]) else 0
            _blog(f"[classify-bridge] petición {b['req']['id']} para {b['req']['externalId']} "
                  f"({len(ch)} crops, {n_busto} bustos) [inflight={len(en_vuelo) + 1}/{inflight}]", flush=True)
            en_vuelo[b["batch_id"]] = {"t0": time.time()}
            orden.append(b["batch_id"])

        # 2) Comprobar resultados (no bloqueante).
        for bid in list(en_vuelo):
            got = buscar_faces(local_id, camara_id, bid)
            if got:
                ready[bid] = got
                del en_vuelo[bid]
                progreso = True
            elif time.time() - en_vuelo[bid]["t0"] > timeout:
                _blog(f"[classify-bridge] timeout del lote {bid}", flush=True)
                _limpiar_batch(ruta, local_id, camara_id, bid)
                del en_vuelo[bid]
                if bid in orden:
                    orden.remove(bid)
                progreso = True

        # 3) Aplicar en orden FIFO los que ya estén listos.
        while orden and orden[0] in ready:
            bid = orden.pop(0)
            data, job_dir = ready.pop(bid)
            rc = _aplicar_local(ruta, local_id, camara_id, bid, data, timeout)
            if rc == 0:
                escribir_ack(job_dir_of(job_dir), source="clasificador_bridge")
                aplicados += 1
            _blog(f"[classify-bridge] {camara_id} lote {bid}: aplicado (rc={rc})", flush=True)
            _limpiar_batch(ruta, local_id, camara_id, bid)
            progreso = True

        if not progreso:
            time.sleep(poll)
        progreso = False
        ahora = time.time()
        if ahora - last_hb > 30:
            last_hb = ahora
            _blog(f"[classify-bridge] cam {camara_id} estado: pend={len(pend)} "
                  f"vuelo={len(en_vuelo)} ready={len(ready)} "
                  f"cola={_cola_aplicador(ruta, local_id)} aplicados={aplicados}")

    return aplicados


def procesar_cam(local_id: str, camara_id: str, ruta: str, timeout: float, poll: float,
                 batch_size: int = 50, inflight: int = 1, k_queue: int = 8) -> int:
    dir_in = os.path.join(ruta, "motor/caras/sinclasificar", str(local_id), str(camara_id))
    if not os.path.isdir(dir_in):
        return 0
    crops = [f for f in sorted(os.listdir(dir_in)) if f.lower().endswith(IMG_EXTS)]
    if not crops:
        return 0

    dir_in = os.path.abspath(dir_in)
    root_abs = os.path.abspath(ruta)
    if not dir_in.startswith(root_abs + os.sep):
        return 0

    n = max(1, int(batch_size))
    chunks = [crops[i:i + n] for i in range(0, len(crops), n)]
    _blog(f"[classify-bridge] cam {camara_id}: {len(crops)} crops, {len(chunks)} lotes, "
          f"inflight={inflight} queue_max={k_queue}")

    if int(inflight) > 1:
        aplicados = _procesar_cam_paralelo(local_id, camara_id, ruta, dir_in, chunks,
                                           timeout, poll, max(1, int(inflight)), max(1, int(k_queue)))
    else:
        aplicados = 0
        for ch in chunks:
            if _procesar_lote(local_id, camara_id, ruta, dir_in, ch, timeout, poll):
                aplicados += 1
    _blog(f"[classify-bridge] {camara_id}: {aplicados} lote(s) aplicados", flush=True)
    return aplicados


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("camara_id")
    ap.add_argument("token", nargs="?", default=None, help="token de Jos_Thread (se ignora)")
    ap.add_argument("--ruta", default=PROYECTO)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--timeout", type=float, default=900.0,
                    help="espera máx. por lote/resultado (s); default 900")
    ap.add_argument("--poll", type=float, default=5.0)
    ap.add_argument("--batch", type=int,
                    default=int(os.environ.get("RF_CLASSIFY_BATCH", "50") or 50),
                    help="crops por lote (F4/F18; env RF_CLASSIFY_BATCH, default 50)")
    ap.add_argument("--inflight", type=int,
                    default=int(os.environ.get("RF_CLASSIFY_INFLIGHT", "6") or 6),
                    help="lotes en vuelo por cámara (F18; env RF_CLASSIFY_INFLIGHT, default 6)")
    ap.add_argument("--queue-max", type=int,
                    default=int(os.environ.get("RF_CLASSIFY_QUEUE", "8") or 8),
                    help="profundidad máx. de la cola del aplicador (F18 backpressure, default 8)")
    args, _desconocidos = ap.parse_known_args()  # tolera el token final de Jos_Thread

    cameras = [c.strip() for c in str(args.camara_id).split(",") if c.strip()]

    if modo() != "superserver":
        cmd = [sys.executable, os.path.join(PROYECTO, "motor/clasificador.py"),
               args.local_id, args.camara_id, "--ruta", args.ruta]
        if args.once:
            cmd.append("--once")
        return subprocess.call(cmd)

    # F5: si el aplicador persistente (systemd) está vivo se usa; si no, `--once`.
    try:
        from motor import clasificador_queue as q
        if q.daemon_alive(args.ruta, args.local_id):
            _blog("[classify-bridge] aplicador persistente disponible (F5)", flush=True)
        else:
            _blog("[classify-bridge] aplicador persistente no disponible; se usará --once", flush=True)
    except Exception:  # noqa: BLE001
        pass

    for cam in cameras:
        try:
            procesar_cam(args.local_id, cam, args.ruta, args.timeout, args.poll,
                         args.batch, args.inflight, args.queue_max)
        except Exception as e:  # noqa: BLE001 — nunca rompe el bucle de cámaras
            _blog(f"[classify-bridge] error en cam {cam}: {e}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
