"""Validador de pose de cara — motor/pose.py

Sustituye a `devuelve_posicion_cara.py` (B1: pruebas geométricas no-op; B2: face_alignment
deprecado). Ahora usa el `pose` (yaw/pitch/roll) que devuelve el modelo (RetinaFace), mucho
más robusto.

Contrato (idéntico al legacy, para no tocar el panel hasta Fase 4):
- Daemon vigilando `<RUTA_PROYECTO>/admin/files/videos_registro/`.
- Por cada imagen `<id>.jpg`, lee la pose objetivo (1..7) de
  `<RUTA_PROYECTO>/admin/files/videos_registro_posiciones/<id>.txt`.
- Escribe la puntuación (0-100) en
  `<RUTA_PROYECTO>/admin/files/videos_registro_resultados/<id>.txt`.
- Elimina imagen y fichero de posición.

Uso: motor/venv/bin/python motor/pose.py <RUTA_PROYECTO> [--debug]
"""
from __future__ import annotations

import os
import sys
import time

import cv2

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.model import analyze  # noqa: E402

# pose_id -> (nombre, yaw_center, yaw_tol, pitch_center, pitch_tol)
# Los signos (izq/der, arriba/abajo) se calibran con cámara real en Fase 2.
POSES = {
    1: ("frente", 0.0, 20.0, 0.0, 20.0),
    2: ("perfil_der_45", 45.0, 20.0, 0.0, 20.0),
    3: ("perfil_der_90", 90.0, 20.0, 0.0, 20.0),
    4: ("perfil_izq_45", -45.0, 20.0, 0.0, 20.0),
    5: ("perfil_izq_90", -90.0, 20.0, 0.0, 20.0),
    6: ("arriba", 0.0, 30.0, 30.0, 25.0),
    7: ("abajo", 0.0, 30.0, -30.0, 25.0),
}

IMG_EXTS = (".jpg", ".jpeg", ".png")


def score_pose(yaw: float, pitch: float, spec) -> int:
    """0-100: 100 = exactamente en la pose pedida; decrece al alejarse."""
    _, yaw_c, yaw_t, pitch_c, pitch_t = spec
    dy = abs(yaw - yaw_c)
    dp = abs(pitch - pitch_c)
    yaw_ok = max(0.0, 1.0 - max(0.0, dy - yaw_t) / (yaw_t * 2))
    pitch_ok = max(0.0, 1.0 - max(0.0, dp - pitch_t) / (pitch_t * 2))
    return int(round(100 * min(yaw_ok, pitch_ok)))


def score_image(image_path: str, pose_id: int) -> int:
    img = cv2.imread(image_path)
    if img is None:
        return 0
    faces = analyze(img, min_score=0.4)
    if not faces:
        return 0
    best = max(faces, key=lambda f: f.det_score)
    spec = POSES.get(pose_id)
    if spec is None:
        return 0
    return score_pose(best.yaw, best.pitch, spec)


def main() -> int:
    ruta = sys.argv[1] if len(sys.argv) > 1 else "."
    debug = "--debug" in sys.argv

    dir_imgs = os.path.join(ruta, "admin/files/videos_registro")
    dir_pos = os.path.join(ruta, "admin/files/videos_registro_posiciones")
    dir_res = os.path.join(ruta, "admin/files/videos_registro_resultados")
    os.makedirs(dir_res, exist_ok=True)

    while True:
        if not os.path.isdir(dir_imgs):
            time.sleep(1)
            continue
        processed = False
        for f in sorted(os.listdir(dir_imgs)):
            if not f.lower().endswith(IMG_EXTS):
                continue
            ident = f.rsplit(".", 1)[0]
            pos_file = os.path.join(dir_pos, f"{ident}.txt")
            if not os.path.exists(pos_file):
                continue  # aún no está lista la posición
            try:
                with open(pos_file) as fh:
                    pose_id = int(fh.read().strip())
            except (ValueError, OSError):
                pose_id = 0

            score = score_image(os.path.join(dir_imgs, f), pose_id)
            with open(os.path.join(dir_res, f"{ident}.txt"), "w") as fh:
                fh.write(str(score))
            if debug:
                print(f"pose {pose_id} ({POSES.get(pose_id, ('?',))[0]}) -> {score}", flush=True)

            for p in (os.path.join(dir_imgs, f), pos_file):
                try:
                    os.remove(p)
                except OSError:
                    pass
            processed = True
            break  # una imagen por iteración (mismo ritmo que el legacy)

        if not processed:
            time.sleep(1)


if __name__ == "__main__":
    sys.exit(main())
