"""Tests del arreglo "2 caras en la misma foto" (A/B/C).

Cubre:
  A  guardar_cara escribe nombres ÚNICOS por cara (índice en el frame): dos caras
     en el mismo frame muestreado ya NO se sobrescriben (tight/busto/torso).
  B  select_display_face elige la cara del busto por COSENO contra la persona del
     sub-clúster (no por det_score) y devuelve None si no coincide ninguna.
  C  dedup_faces_near_duplicates elimina detecciones casi idénticas del mismo
     rostro dentro de un crop (evita foto duplicada + score 1.0).
"""
import os
from types import SimpleNamespace

import numpy as np

from motor.core.config import Config
from motor.procesa_video import guardar_cara
from motor.clasificador import dedup_faces_near_duplicates, select_display_face


def rnd_emb(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(512)
    return v / np.linalg.norm(v)


def fake_face(bbox, emb) -> SimpleNamespace:
    return SimpleNamespace(bbox=bbox, embedding=emb, det_score=0.9,
                           yaw=0.0, pitch=0.0, pose=(0.0, 0.0, 0.0))


# ------------------------------------------------------------------ A

def test_guardar_cara_dos_caras_mismo_frame_no_se_sobrescriben(tmp_path):
    cfg = Config()
    rng = np.random.default_rng(42)
    frame = rng.integers(0, 255, (720, 1280, 3), dtype=np.uint8)  # textura -> nítida
    fichero = "21_2026-08-27_11:17:39.880558.mp4"
    segs = 2.833333

    cara_a = fake_face((400, 200, 500, 350), rnd_emb(1))
    cara_b = fake_face((700, 220, 790, 360), rnd_emb(2))

    # dos caras en el MISMO frame muestreado (mismo fichero/segs), buffer compartido
    guardar_cara(str(tmp_path), "1", "21", fichero, frame, cara_a, segs, cfg, [], face_idx=0)
    guardar_cara(str(tmp_path), "1", "21", fichero, frame, cara_b, segs, cfg, [], face_idx=1)

    stem = f"{fichero}_{segs:.6f}"
    for suf in ("_0.png", "_1.png"):
        tight = os.path.join(str(tmp_path), "motor/caras/sinclasificar", "1", "21", stem + suf)
        busto = os.path.join(str(tmp_path), "motor/caras/sinclasificar", "1", "21_busto", stem + suf)
        torso = os.path.join(str(tmp_path), "motor/caras/sinclasificar", "1", "21_cuerpo", stem + suf.replace(".png", ".jpg"))
        assert os.path.exists(tight), f"tight {suf} no existe (sobrescrito?)"
        assert os.path.exists(busto), f"busto {suf} no existe"
        assert os.path.exists(torso), f"torso {suf} no existe"


def test_guardar_cara_sin_cara_idx_tiene_sufijo_0(tmp_path):
    cfg = Config()
    rng = np.random.default_rng(7)
    frame = rng.integers(0, 255, (720, 1280, 3), dtype=np.uint8)
    fichero = "13_2026-08-27_10:00:00.000000.mp4"
    cara = fake_face((400, 200, 500, 350), rnd_emb(3))

    guardar_cara(str(tmp_path), "1", "13", fichero, frame, cara, 1.0, cfg, [], face_idx=0)

    tight = os.path.join(str(tmp_path), "motor/caras/sinclasificar", "1", "13",
                         f"{fichero}_1.000000_0.png")
    assert os.path.exists(tight)


# ------------------------------------------------------------------ B

def test_select_display_face_elige_la_cara_correcta_en_busto_con_2():
    ref = rnd_emb(10)
    misma = rnd_emb(11)
    misma += 1.2 * ref                       # alineada con la persona del sub-clúster (cos~0.77)
    misma /= np.linalg.norm(misma)
    otra = rnd_emb(12)
    otra -= ref * float(np.dot(otra, ref))   # ortogonal -> otra persona
    otra /= np.linalg.norm(otra)

    f_correcta = fake_face((100, 100, 200, 250), misma)
    f_equivocada = fake_face((300, 100, 400, 250), otra)

    best = select_display_face([f_equivocada, f_correcta], ref, min_cos=0.6)
    assert best is f_correcta


def test_select_display_face_none_si_ninguna_coincide():
    ref = rnd_emb(20)
    otra = rnd_emb(21)
    otra -= ref * float(np.dot(otra, ref))
    otra /= np.linalg.norm(otra)

    best = select_display_face([fake_face((0, 0, 50, 60), otra)], ref, min_cos=0.6)
    assert best is None


# ------------------------------------------------------------------ C

def test_dedup_caras_casi_identicas_conserva_la_mas_nitida():
    cfg = Config()
    rng = np.random.default_rng(30)
    frame = np.zeros((720, 1280, 3), dtype=np.uint8)
    # región A: ruido (nítida); región B: plana (borrosa)
    frame[200:350, 400:500] = rng.integers(0, 255, (150, 100, 3), dtype=np.uint8)

    emb = rnd_emb(31)                       # mismo rostro (detección duplicada)
    cara_nitida = fake_face((400, 200, 500, 350), emb)
    cara_borrosa = fake_face((400, 200, 500, 350), emb)

    keep = dedup_faces_near_duplicates([cara_borrosa, cara_nitida], frame, cfg)
    assert len(keep) == 1
    assert keep[0].bbox == cara_nitida.bbox   # conserva la más nítida


def test_dedup_caras_distintas_conserva_ambas():
    cfg = Config()
    rng = np.random.default_rng(40)
    frame = rng.integers(0, 255, (720, 1280, 3), dtype=np.uint8)

    a = fake_face((400, 200, 500, 350), rnd_emb(41))
    b = fake_face((700, 220, 790, 360), rnd_emb(42))

    keep = dedup_faces_near_duplicates([a, b], frame, cfg)
    assert len(keep) == 2
