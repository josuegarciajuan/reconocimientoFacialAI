"""Tests de la evidencia "Frame original" (frame nativo acotado, uno por fotograma).

Cubre:
  - guardar_cara escribe el frame nativo UNA VEZ POR FOTOGRAMA (base sin índice de
    cara), acotado a `cfg.evidence_max_side`, y NO lo escribe si el flag está off.
  - _frame_stem recorta el índice de cara del nombre del crop.
  - _podar_frames_huerfanos elimina frames sin crop pendiente.
  - _evidence_frame prefiere el frame nativo en disco y cae limpiamente a
    select_max_resolution_frame si no existe.
"""
import os
from types import SimpleNamespace

import cv2
import numpy as np

from motor.core.config import Config
from motor.procesa_video import guardar_cara
from motor.clasificador import _evidence_frame, _frame_stem, _podar_frames_huerfanos
from motor.core.image_provenance import select_max_resolution_frame


def rnd_emb(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(512)
    return v / np.linalg.norm(v)


def fake_face(bbox, emb) -> SimpleNamespace:
    return SimpleNamespace(bbox=bbox, embedding=emb, det_score=0.9,
                           yaw=0.0, pitch=0.0, pose=(0.0, 0.0, 0.0))


def _frame_path(tmp_path, cam, base):
    return os.path.join(str(tmp_path), "motor/caras/sinclasificar", "1",
                        f"{cam}_frame", base + ".jpg")


# ------------------------------------------------------- guardar_cara frame

def test_guardar_cara_frame_unico_por_fotograma_y_acotado(tmp_path):
    cfg = Config()
    cfg.save_original_frame = True
    rng = np.random.default_rng(42)
    frame = rng.integers(0, 255, (1080, 1920, 3), dtype=np.uint8)  # 1080p nativo
    fichero = "21_2026-08-27_11:17:39.880558.mp4"
    segs = 2.833333
    base = f"{fichero}_{segs:.6f}"
    cara = fake_face((400, 200, 500, 350), rnd_emb(1))

    # Dos caras del MISMO fotograma -> un solo frame de evidencia (base sin idx).
    guardar_cara(str(tmp_path), "1", "21", fichero, frame, cara, segs, cfg, [], face_idx=0)
    guardar_cara(str(tmp_path), "1", "21", fichero, frame, cara, segs, cfg, [], face_idx=1)

    frame_file = _frame_path(tmp_path, "21", base)
    assert os.path.exists(frame_file), "no se escribió el frame de evidencia"
    dir_frame = os.path.dirname(frame_file)
    assert len([f for f in os.listdir(dir_frame) if f.endswith(".jpg")]) == 1, \
        "dos caras del mismo fotograma deben compartir un único frame"

    saved = cv2.imread(frame_file)
    assert saved is not None
    # Acotado al lado mayor configurado (1280), no 1080p entero.
    assert max(saved.shape[:2]) == cfg.evidence_max_side
    assert saved.shape[0] == 720 and saved.shape[1] == 1280   # 1920x1080 -> 1280x720

    # Con el flag OFF no debe escribirse el frame (comportamiento intacto).
    cfg_off = Config()
    cfg_off.save_original_frame = False
    fichero_off = "22_2026-08-27_11:17:39.880558.mp4"
    guardar_cara(str(tmp_path), "1", "21", fichero_off, frame, cara, segs, cfg_off, [],
                 face_idx=0)
    assert not os.path.exists(_frame_path(tmp_path, "21", f"{fichero_off}_{segs:.6f}"))


def test_guardar_cara_frame_respeta_max_side_menor(tmp_path):
    cfg = Config()
    cfg.evidence_max_side = 640
    rng = np.random.default_rng(7)
    frame = rng.integers(0, 255, (1080, 1920, 3), dtype=np.uint8)  # nitido (pasa el gate)
    cara = fake_face((400, 200, 500, 350), rnd_emb(2))
    guardar_cara(str(tmp_path), "1", "21", "v.mp4", frame, cara, 1.0, cfg, [], face_idx=0)
    saved = cv2.imread(_frame_path(tmp_path, "21", "v.mp4_1.000000"))
    assert saved is not None and max(saved.shape[:2]) == 640


# ------------------------------------------------------- helpers

def test_frame_stem_quita_indice_de_cara():
    assert _frame_stem("16_2026-10-01_11:06:56.260949.mp4_3.200000_0") == \
        "16_2026-10-01_11:06:56.260949.mp4_3.200000"
    # Sin índice numérico final (legacy) se deja igual.
    assert _frame_stem("16_2026-10-01_11:06:56.260949.mp4_3.200000") == \
        "16_2026-10-01_11:06:56.260949.mp4_3.200000"


def test_podar_frames_huerfanos_borra_los_sin_crop(tmp_path):
    d = tmp_path / "21_frame"
    d.mkdir()
    (d / "b1.jpg").write_bytes(b"x")
    (d / "b2.jpg").write_bytes(b"x")
    n = _podar_frames_huerfanos(str(d), {"b1"})
    assert n == 1
    assert (d / "b1.jpg").exists()
    assert not (d / "b2.jpg").exists()
    # Directorio inexistente: no lanza.
    assert _podar_frames_huerfanos(str(tmp_path / "nope"), set()) == 0


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

    out_fallback = _evidence_frame(None, rep_item, [], [])
    assert out_fallback.shape == crop.shape
    assert out_fallback.shape == select_max_resolution_frame(crop, [], []).shape
