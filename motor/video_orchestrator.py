#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Orquestador de vídeo troceado (P1, modo `superserver` distributed).

Lo lanza `detector.php` en lugar de `pool_bridge.py` cuando
`RF_VIDEO_MODE=distributed`. Envía **UNA** petición al motor distribuido de
SuperServer (definición `rf-video-segments`) con los parámetros del clip; el
motor reparte **unidades** (una por segmento de frames) por la flota y devuelve
un resultado combinado (cruces + métricas + crops empaquetados). Aquí se
decodifican los crops y se aplican **exactamente** los efectos del proceso
clásico, reutilizando `pool_bridge.aplicar` (mover caras y fotos de cruce,
`ws.php guarda_cruce`, embudo, borrar vídeo origen + marker).

Fallback: si el canal distribuido no responde/no está disponible, delega en
`pool_bridge` (que a su vez cae al `procesa_video.py` clásico si el modo no es
`superserver`). El resultado final nunca cambia.

Uso (lo lanza detector.php):
    <venv>/python motor/video_orchestrator.py <local> <cam> <fichero> \
        --ruta <RUTA> [--tag "<pg-tag>"] [--timeout 3600]

Contrato con la definición `rf-video-segments` (params):
    {local, cam, fichero, home, home_path, total_frames, segment_frames,
     face_every, lineas:[{id,x1,y1,x2,y2}]}
Resultado combinado esperado (JSON):
    {local, cam, fichero, frames, frame_ini, frame_fin, unidades,
     caras_detect, caras_guard, caras_borroso, caras_dedup, cuerpos,
     cruces:[{linea_id,fecha,direccion,x,y,uid}], crops_tar_b64}
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.pool_bridge import aplicar, lineas_payload, modo  # noqa: E402
from motor.procesa_video import PROYECTO                       # noqa: E402

DEFINITION = "rf-video-segments"


def _env_int(name: str, default: int) -> int:
    try:
        return int(str(os.environ.get(name, "")).strip() or default)
    except (TypeError, ValueError):
        return default


def submit_bin() -> str:
    return os.environ.get("RF_DIST_SUBMIT_BIN", "ss-dist-submit").strip() or "ss-dist-submit"


def _exec_id(local_id: str, camara_id: str, fichero: str) -> str:
    h = hashlib.sha1(fichero.encode("utf-8", "replace")).hexdigest()[:12]
    return f"rfv-{local_id}-{camara_id}-{h}"


def frame_info(video_path: str) -> tuple[int, float]:
    """(total_frames, fps) del vídeo; (0, 10.0) si no se puede leer."""
    try:
        import cv2  # noqa: PLC0415
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return 0, 10.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) or 10.0
        cap.release()
        return total, fps
    except Exception:  # noqa: BLE001
        return 0, 10.0


def build_params(local_id: str, camara_id: str, fichero: str, ruta: str) -> dict:
    video_path = os.path.join(ruta, "motor/videos", local_id, camara_id, fichero)
    total, fps = frame_info(video_path)
    seg_sec = _env_int("RF_DIST_SEGMENT_SEC", 10)
    segment_frames = int(max(1, round(seg_sec * fps))) if total > 0 else 0
    face_every = _env_int("RF_FACE_EVERY", 0)  # 0 => el worker usa su Config
    return {
        "local": str(local_id),
        "cam": str(camara_id),
        "fichero": fichero,
        "home": os.environ.get("RF_DIST_HOME", "").strip() or None,
        "home_path": f"motor/videos/{local_id}/{camara_id}/{fichero}",
        "total_frames": total,
        "segment_frames": segment_frames,
        "fps": fps,
        "face_every": face_every or None,
        "lineas": lineas_payload(camara_id),
    }


def submit(params: dict, exec_id: str, timeout: float) -> dict | None:
    """Lanza `ss-dist-submit ... --wait` y devuelve el JSON combinado (o None)."""
    cmd = [submit_bin(), "--definition", DEFINITION,
           "--params", json.dumps(params, ensure_ascii=False),
           "--id", exec_id, "--wait", "--timeout", str(int(timeout))]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 60)
    except Exception as e:  # noqa: BLE001
        print(f"[orquestador] submit falló: {e}", flush=True)
        return None
    if r.returncode != 0:
        print(f"[orquestador] submit rc={r.returncode}: {r.stderr.strip()[:400]}", flush=True)
        return None
    txt = (r.stdout or "").strip()
    # El canal puede imprimir líneas de progreso; se toma el ÚLTIMO objeto JSON.
    for start in range(len(txt)):
        if txt[start] == "{":
            try:
                return json.loads(txt[start:])
            except ValueError:
                continue
    print("[orquestador] submit sin JSON de resultado", flush=True)
    return None


def decode_crops(b64: str, dest_root: str) -> bool:
    """Decodifica el tar de crops al layout que espera `aplicar` (<root>/motor/...)."""
    if not b64:
        return True
    try:
        raw = base64.b64decode(b64)
    except Exception as e:  # noqa: BLE001
        print(f"[orquestador] crops_tar_b64 inválido: {e}", flush=True)
        return False
    try:
        with tempfile.NamedTemporaryFile(suffix=".tar", delete=False) as fh:
            fh.write(raw)
            tar_path = fh.name
        with tarfile.open(tar_path, "r:*") as tf:
            tf.extractall(dest_root)  # noqa: S202 — tar del propio motor, rutas controladas
        os.remove(tar_path)
        return True
    except Exception as e:  # noqa: BLE001
        print(f"[orquestador] no se pudo extraer crops: {e}", flush=True)
        return False


def fallback(local_id: str, camara_id: str, fichero: str, ruta: str) -> int:
    """Cae al puente del pool (y este al local si el modo no es superserver)."""
    print("[orquestador] fallback a pool_bridge", flush=True)
    cmd = [sys.executable, os.path.join(PROYECTO, "motor/pool_bridge.py"),
           str(local_id), str(camara_id), fichero, "--ruta", ruta]
    return subprocess.call(cmd)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("camara_id")
    ap.add_argument("fichero")
    ap.add_argument("--ruta", default=PROYECTO)
    ap.add_argument("--tag", default="")
    ap.add_argument("--timeout", type=float, default=float(_env_int("RF_DIST_TIMEOUT", 3600)))
    args = ap.parse_args()

    # Solo tiene sentido en modo superserver; en local, comportamiento clásico.
    if modo() != "superserver":
        cmd = [sys.executable, os.path.join(PROYECTO, "motor/procesa_video.py"),
               args.local_id, args.camara_id, args.fichero, "--ruta", args.ruta]
        return subprocess.call(cmd)

    t_ini = time.time()
    params = build_params(args.local_id, args.camara_id, args.fichero, args.ruta)
    exec_id = _exec_id(args.local_id, args.camara_id, args.fichero)
    print(f"[orquestador] {exec_id}: total_frames={params['total_frames']} "
          f"segment_frames={params['segment_frames']} "
          f"({len(params['lineas'])} líneas)", flush=True)

    data = submit(params, exec_id, args.timeout)
    if not data:
        return fallback(args.local_id, args.camara_id, args.fichero, args.ruta)

    tmp = tempfile.mkdtemp(prefix="rf-dist-")
    try:
        if not decode_crops(data.get("crops_tar_b64", ""), tmp):
            return fallback(args.local_id, args.camara_id, args.fichero, args.ruta)
        # `aplicar` mueve crops/fotos, registra cruces, embudo y borra vídeo+marker.
        aplicar(tmp, data, args.local_id, args.camara_id, args.fichero, args.ruta, t_ini)
    finally:
        try:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
        except Exception:  # noqa: BLE001
            pass

    print(f"[orquestador] {exec_id}: aplicado "
          f"({data.get('unidades', '?')} unidades, {data.get('caras_guard', 0)} caras)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
