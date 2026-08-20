"""Tests del calibrador guiado (F1-F2) — motor/tests/test_calibrador.py

Cubre la lógica pura de recomendación de motor/calibrador.py (rituales A-F):
las funciones devuelven recomendaciones con motivo y dentro de rangos
razonables, y NUNCA aplican nada por sí solas.
"""
from __future__ import annotations

import os
import tempfile

from motor.calibrador import (_ajuste_c, _merge_reco, recomendacion_ritual_a,
                              recomendacion_ritual_b, recomendacion_ritual_d,
                              recomendacion_ritual_f)


# ---------------------------------------------------------------------------
# Ritual A · Alcance (detección de cara)
# ---------------------------------------------------------------------------

def test_ritual_a_con_caras():
    px = [120, 110, 95, 80, 64, 58, 50, 45, 42, 40, 38, 36]
    sharp = [90, 85, 70, 60, 55, 50, 48, 45, 42, 40, 38, 35]
    rec = recomendacion_ritual_a(px, sharp, {
        "RF_DET_SIZE": 1280, "RF_MIN_SHARPNESS": 55, "RF_SR_EMBED_MIN_FACE": 96})
    assert "RF_SR_EMBED_MIN_FACE" in rec
    assert "RF_MIN_SHARPNESS" in rec
    # p25 de px ≈ 41 -> recomienda bajar sr_embed (48 mínimo)
    assert 48 <= rec["RF_SR_EMBED_MIN_FACE"]["recomendado"] <= 96
    assert 20 <= rec["RF_MIN_SHARPNESS"]["recomendado"] <= 55
    assert rec["RF_SR_EMBED_MIN_FACE"]["motivo"]


def test_ritual_a_sin_caras_sugiere_det_size():
    rec = recomendacion_ritual_a([], [], {
        "RF_DET_SIZE": 640, "RF_MIN_SHARPNESS": 55, "RF_SR_EMBED_MIN_FACE": 96})
    assert rec["RF_DET_SIZE"]["recomendado"] >= 1280


# ---------------------------------------------------------------------------
# Ritual B · Paso veloz (FPS)
# ---------------------------------------------------------------------------

def test_ritual_b_paso_ok():
    rec = recomendacion_ritual_b(25.0, 40, 6, 2, {"fps": 14, "sensibilidad": 1})
    assert rec["fps"]["recomendado"] == 25
    assert "sensibilidad" not in rec  # ya era 1: no toca


def test_ritual_b_stream_lento_mantiene_fps():
    rec = recomendacion_ritual_b(7.0, 1, 1, 0, {"fps": 14, "sensibilidad": 1})
    assert rec["fps"]["recomendado"] == 14  # no puede subir por encima del stream


def test_ritual_b_paso_perdido_con_salto_baja_sensibilidad():
    rec = recomendacion_ritual_b(5.0, 1, 1, 0, {"fps": 14, "sensibilidad": 3})
    assert rec["sensibilidad"]["recomendado"] == 1


# ---------------------------------------------------------------------------
# Ritual C · Disparo (fases c1/c2)
# ---------------------------------------------------------------------------

def _actual_c():
    return {"dontCare": 220, "porcentaje_mov": 60, "threshold": 21}


def test_ritual_c_c1_falla_mas_sensible():
    por_camara, glob, _ = _ajuste_c({"c1": {"disparos": 0}}, _actual_c())
    assert por_camara["dontCare"]["recomendado"] < 220
    assert por_camara["porcentaje_mov"]["recomendado"] < 60
    assert glob["RF_MOV_THRESHOLD"]["recomendado"] < 21


def test_ritual_c_c2_falla_menos_sensible():
    por_camara, glob, _ = _ajuste_c(
        {"c1": {"disparos": 2}, "c2": {"disparos": 3}}, _actual_c())
    assert por_camara["dontCare"]["recomendado"] > 220
    assert "RF_MOV_THRESHOLD" not in glob  # c1 ok: no se toca el umbral global


def test_ritual_c_ambas_correctas_mantiene():
    por_camara, glob, _ = _ajuste_c(
        {"c1": {"disparos": 2}, "c2": {"disparos": 0}}, _actual_c())
    assert por_camara["dontCare"]["recomendado"] == 220
    assert glob == {}


def test_ritual_c_una_fase_pendiente():
    por_camara, _, _ = _ajuste_c({"c1": {"disparos": 2}}, _actual_c())
    # c1 ok pero falta c2: la recomendación pide ejecutar la otra fase
    assert "c2" in por_camara["dontCare"]["motivo"]


# ---------------------------------------------------------------------------
# Ritual D · Cruce de línea
# ---------------------------------------------------------------------------

def test_ritual_d_sin_deteccion_baja_area():
    rec = recomendacion_ritual_d(3, 0, 800)
    assert rec["RF_CRUCE_AREA_MIN"]["recomendado"] < 800


def test_ritual_d_ruido_sube_area():
    rec = recomendacion_ritual_d(3, 5, 800)
    assert rec["RF_CRUCE_AREA_MIN"]["recomendado"] > 800


def test_ritual_d_correcto_mantiene():
    rec = recomendacion_ritual_d(3, 3, 800)
    assert rec["RF_CRUCE_AREA_MIN"]["recomendado"] == 800


# ---------------------------------------------------------------------------
# Ritual F · Enfoque (distancia máxima)
# ---------------------------------------------------------------------------

def test_ritual_f_con_caras():
    rec = recomendacion_ritual_f([40, 42, 38], [30, 28, 25],
                                 {"RF_MIN_SHARPNESS": 55, "RF_DET_SIZE": 1280})
    assert "RF_MIN_SHARPNESS" in rec
    assert 20 <= rec["RF_MIN_SHARPNESS"]["recomendado"] <= 55


def test_ritual_f_sin_caras():
    rec = recomendacion_ritual_f([], [], {"RF_MIN_SHARPNESS": 55, "RF_DET_SIZE": 640})
    assert rec["RF_DET_SIZE"]["recomendado"] >= 1280


# ---------------------------------------------------------------------------
# Persistencia de recomendaciones (_merge_reco)
# ---------------------------------------------------------------------------

def test_merge_reco_acumula_rituales():
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "motor/calibrador/recomendaciones"), exist_ok=True)
        _merge_reco(tmp, 13, "A", recomendaciones={"RF_MIN_SHARPNESS": {
            "actual": 55, "recomendado": 45, "motivo": "ritual A"}})
        _merge_reco(tmp, 13, "D", recomendaciones={"RF_CRUCE_AREA_MIN": {
            "actual": 800, "recomendado": 480, "motivo": "ritual D"}},
            por_camara={"dontCare": {"actual": 220, "recomendado": 132, "motivo": "ritual C"}})
        import json
        with open(os.path.join(tmp, "motor/calibrador/recomendaciones/13.json")) as fh:
            data = json.load(fh)
        # ambos rituales conviven en el mismo fichero (badges de Editar + General)
        assert "RF_MIN_SHARPNESS" in data["recomendaciones"]
        assert "RF_CRUCE_AREA_MIN" in data["recomendaciones"]
        assert data["por_camara"]["dontCare"]["recomendado"] == 132
