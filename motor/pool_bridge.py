#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Puente del pool para `procesa_video` (M3 de SuperServer).

Lo lanza `detector.php` por vídeo cuando el proyecto está en modo `superserver`,
con la MISMA vida que el `procesa_video.py` clásico (el detector lo vigila con su
marker + `pgrep`). Hace tres cosas:

  1. Consulta las líneas de la cámara en la BD (la casa sí puede) y deja una
     petición en el spool de SuperServer (`/var/lib/taildeck/spool`).
  2. Espera el resultado del pool en
     `/var/lib/taildeck/returns/reconocimientoFacial/<job>/`.
  3. Aplica EXACTAMENTE los efectos del proceso clásico: mueve caras y fotos de
     cruce a su sitio, registra los cruces con `ws.php guarda_cruce`, escribe el
     embudo, borra el vídeo origen y el marker.

Si el modo es `local` (o el flag no existe), ejecuta el `procesa_video.py`
clásico tal cual (comportamiento actual, sin cambios).

Uso (lo lanza detector.php):
    <venv>/python motor/pool_bridge.py <local> <cam> <fichero> \
        --ruta <RUTA_PROYECTO> [--tag "<pg-tag>"] [--timeout 21600]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.embudo import log_evento                      # noqa: E402
from motor.pool_ack import escribir_ack, job_dir_of            # noqa: E402
from motor.procesa_video import PROYECTO, cargar_lineas, php_ws  # noqa: E402

MODE_FILE = "/var/lib/taildeck/projects/reconocimientoFacial.mode"
SPOOL_DIR = "/var/lib/taildeck/spool"
RETURNS_DIR = "/var/lib/taildeck/returns/reconocimientoFacial"


def modo() -> str:
    try:
        with open(MODE_FILE, encoding="utf-8") as fh:
            return "superserver" if fh.read().strip() == "superserver" else "local"
    except OSError:
        return "local"


def lineas_payload(camara_id: str) -> list[dict]:
    """Líneas de la cámara en el mismo formato que espera `procesa_video_pool.py`."""
    out = []
    for ln in cargar_lineas(camara_id):
        out.append({"id": ln.line_id, "x1": ln.x1, "y1": ln.y1, "x2": ln.x2, "y2": ln.y2})
    return out


def build_request(local_id: str, camara_id: str, fichero: str, lineas: list[dict],
                  rid: str | None = None) -> dict:
    rid = rid or f"req-{int(time.time())}-{os.getpid()}"
    return {
        "id": rid,
        "project": "reconocimientoFacial",
        "process": "video_faces",
        "params": {"local": local_id, "cam": camara_id, "fichero": fichero, "lineas": lineas},
        "externalId": f"video:{local_id}/{camara_id}/{fichero}",
    }


def escribir_peticion(req: dict) -> str:
    os.makedirs(SPOOL_DIR, exist_ok=True)
    dst = os.path.join(SPOOL_DIR, f"{req['id']}.json")
    tmp = dst + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(req, fh, ensure_ascii=False)
    os.replace(tmp, dst)
    return dst


def _leer_resultado(d: str) -> dict | None:
    if os.path.exists(os.path.join(d, ".aplicado")):
        return None
    # El executor entrega el output declarado como `<job>/result/...`.
    # Se admite también la forma directa por compatibilidad con pruebas/manuales.
    f = os.path.join(d, "efectos.json")
    if not os.path.exists(f):
        f = os.path.join(d, "result", "efectos.json")
    if not os.path.exists(f):
        return None
    try:
        with open(f, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def _artifact_root(d: str) -> str:
    """Raíz de artefactos del output (el executor usa `<job>/result/`)."""
    return os.path.join(d, "result") if os.path.isdir(os.path.join(d, "result")) else d


def esperar_resultado(local_id: str, camara_id: str, fichero: str,
                      timeout_s: float, poll_s: float = 5.0) -> tuple[str, dict] | None:
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        if os.path.isdir(RETURNS_DIR):
            for name in sorted(os.listdir(RETURNS_DIR)):
                d = os.path.join(RETURNS_DIR, name)
                if not os.path.isdir(d):
                    continue
                data = _leer_resultado(d)
                if not data:
                    continue
                if (data.get("local") == local_id and str(data.get("cam")) == str(camara_id)
                        and data.get("fichero") == fichero):
                    return d, data
        time.sleep(poll_s)
    return None


def _mover_archivos(src_dir: str, dst_dir: str) -> int:
    """Mueve recursivamente los ficheros de src a dst conservando rutas. Devuelve nº."""
    n = 0
    if not os.path.isdir(src_dir):
        return 0
    for root, _dirs, files in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        target = dst_dir if rel == "." else os.path.join(dst_dir, rel)
        os.makedirs(target, exist_ok=True)
        for f in files:
            shutil.move(os.path.join(root, f), os.path.join(target, f))
            n += 1
    return n


def aplicar(result_dir: str, data: dict, local_id: str, camara_id: str, fichero: str,
            ruta: str) -> None:
    """Aplica los efectos del proceso clásico sobre la casa (idéntico resultado final)."""
    artifacts = _artifact_root(result_dir)
    caras = 0
    # ORDEN CRÍTICO: "_frame" (evidencia "Frame original" 1080p) va PRIMERO. El
    # clasificador vigila el dir de caras "" y puede consumir los crops en cuanto
    # aparecen; si los frames se movieran después, esa pasada los perdería y las
    # fotos quedarían con el crop. Con los frames en su sitio antes que los crops,
    # el clasificador siempre los empareja.
    for sufijo in ("_frame", "", "_busto", "_cuerpo"):
        src = os.path.join(artifacts, "motor/caras/sinclasificar", local_id, f"{camara_id}{sufijo}")
        dst = os.path.join(ruta, "motor/caras/sinclasificar", local_id, f"{camara_id}{sufijo}")
        caras += _mover_archivos(src, dst)

    cruces = 0
    for ev in data.get("cruces", []) or []:
        linea_id = str(ev.get("linea_id", ""))
        uid = str(ev.get("uid", ""))
        if linea_id and uid:
            src = os.path.join(artifacts, "motor/fotos_lineas", linea_id, uid + ".jpg")
            dst_dir = os.path.join(ruta, "motor/fotos_lineas", linea_id)
            os.makedirs(dst_dir, exist_ok=True)
            if os.path.exists(src):
                shutil.move(src, os.path.join(dst_dir, uid + ".jpg"))
            php_ws("guarda_cruce", linea_id, ev.get("fecha", ""), str(ev.get("direccion", 0)),
                   str(ev.get("x", 0)), str(ev.get("y", 0)), uid)
            cruces += 1

    log_evento(ruta, local_id, "video", cam=camara_id, fichero=fichero,
               frames=data.get("frames", 0), caras_detect=data.get("caras_detect", 0),
               caras_guard=data.get("caras_guard", 0), caras_borroso=data.get("caras_borroso", 0),
               caras_dedup=data.get("caras_dedup", 0), cuerpos=data.get("cuerpos", 0),
               cruces=data.get("cruces_count", cruces))

    video_path = os.path.join(ruta, "motor/videos", local_id, camara_id, fichero)
    if os.path.exists(video_path):
        os.remove(video_path)
    marker = os.path.join(ruta, "aux", fichero + ".txt")
    if os.path.exists(marker):
        os.remove(marker)

    try:
        with open(os.path.join(result_dir, ".aplicado"), "w", encoding="utf-8") as fh:
            fh.write(str(time.time()))
    except OSError:
        pass

    print(f"[pool-bridge] aplicado {local_id}/{camara_id} {fichero}: "
          f"{caras} caras, {cruces} cruces, vídeo y marker borrados", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("camara_id")
    ap.add_argument("fichero")
    ap.add_argument("--ruta", default=PROYECTO)
    ap.add_argument("--tag", default="", help="texto extra en la cmdline para que pgrep lo vea vivo")
    ap.add_argument("--timeout", type=float, default=21600.0)
    ap.add_argument("--poll", type=float, default=5.0)
    args = ap.parse_args()

    if modo() != "superserver":
        # Fallback sin cambios: modo local clásico.
        cmd = [sys.executable, os.path.join(PROYECTO, "motor/procesa_video.py"),
               args.local_id, args.camara_id, args.fichero, "--ruta", args.ruta]
        return subprocess.call(cmd)

    lineas = lineas_payload(args.camara_id)
    req = build_request(args.local_id, args.camara_id, args.fichero, lineas)
    escribir_peticion(req)
    print(f"[pool-bridge] petición {req['id']} para {req['externalId']} "
          f"({len(lineas)} líneas)", flush=True)

    got = esperar_resultado(args.local_id, args.camara_id, args.fichero, args.timeout, args.poll)
    if not got:
        print(f"[pool-bridge] timeout esperando el resultado de {req['externalId']}", flush=True)
        return 1
    result_dir, data = got
    aplicar(result_dir, data, args.local_id, args.camara_id, args.fichero, args.ruta)
    escribir_ack(job_dir_of(result_dir), source="pool_bridge")
    return 0


if __name__ == "__main__":
    sys.exit(main())
