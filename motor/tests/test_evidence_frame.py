"""Tests de la evidencia "Frame original" (frame nativo 1080p por cara).

Cubre:
  - guardar_cara escribe el FRAME COMPLETO (no el recorte) en <cam>_frame/ cuando
    cfg.save_original_frame=True, y NO lo escribe cuando es False.
  - _evidence_frame prefiere el frame nativo en disco y cae limpiamente a
    select_max_resolution_frame si no existe (comportamiento anterior preservado).
"""
import os
from types import SimpleNamespace

import cv2
import numpy as np

from motor.core.config import Config
from motor.procesa_video import guardar_cara
from motor.clasificador import _evidence_frame
from motor.core.image_provenance import select_max_resolution_frame


def rnd_emb(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(512)
    return v / np.linalg.norm(v)


def fake_face(bbox, emb) -> SimpleNamespace:
    return SimpleNamespace(bbox=bbox, embedding=emb, det_score=0.9,
                           yaw=0.0, pitch=0.0, pose=(0.0, 0.0, 0.0))


# ------------------------------------------------------- guardar_cara frame

def test_guardar_cara_escribe_frame_completo(tmp_path):
    cfg = Config()
    cfg.save_original_frame = True
    rng = np.random.default_rng(42)
    frame = rng.integers(0, 255, (1080, 1920, 3), dtype=np.uint8)  # 1080p nativo
    fichero = "21_2026-08-27_11:17:39.880558.mp4"
    segs = 2.833333
    cara = fake_face((400, 200, 500, 350), rnd_emb(1))

    guardar_cara(str(tmp_path), "1", "21", fichero, frame, cara, segs, cfg, [], face_idx=0)

    nombre = f"{fichero}_{segs:.6f}_0"
    frame_file = os.path.join(str(tmp_path), "motor/caras/sinclasificar", "1",
                              "21_frame", nombre + ".jpg")
    assert os.path.exists(frame_file), "no se escribió el frame completo"
    saved = cv2.imread(frame_file)
    assert saved is not None
    assert saved.shape == frame.shape, (
        f"el frame guardado {saved.shape} no es el nativo {frame.shape}")

    # Con el flag OFF no debe escribirse el frame (comportamiento intacto).
    cfg_off = Config()
    cfg_off.save_original_frame = False
    fichero_off = "22_2026-08-27_11:17:39.880558.mp4"
    guardar_cara(str(tmp_path), "1", "21", fichero_off, frame, cara, segs, cfg_off, [],
                 face_idx=0)
    nombre_off = f"{fichero_off}_{segs:.6f}_0"
    frame_file_off = os.path.join(str(tmp_path), "motor/caras/sinclasificar", "1",
                                  "21_frame", nombre_off + ".jpg")
    assert not os.path.exists(frame_file_off), "frame escrito pese a save_original_frame=False"


# ------------------------------------------------------- _evidence_frame

def test_evidence_frame_prefiere_frame_nativo(tmp_path):
    crop = np.zeros((60, 50, 3), dtype=np.uint8)
    native = np.zeros((1080, 1920, 3), dtype=np.uint8)
    crop_path = str(tmp_path / "crop.png")
    native_path = str(tmp_path / "native.jpg")
    cv2.imwrite(crop_path, crop)
    cv2.imwrite(native_path, native)

    rep_item = {"img": crop, "file": "x.jpg"}
    out = _evidence_frame(native_path, rep_item, [], [])
    assert out.shape == native.shape, (
        f"_evidence_frame devolvió {out.shape}, esperado el frame nativo {native.shape}")

    # Sin frame en disco -> fallback al comportamiento anterior (crop mayor).
    out_fallback = _evidence_frame(None, rep_item, [], [])
    assert out_fallback.shape == crop.shape
    assert out_fallback.shape == select_max_resolution_frame(crop, [], []).shape
