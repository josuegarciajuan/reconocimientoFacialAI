"""Tests de latencia end-to-end (P0/WS1) — motor/core/embudo.py.

Verifican el contrato de eventos `latencia` y el agregado por percentiles sin
tocar el pipeline: `resumir_latencia` es puro y determinista.
"""
from __future__ import annotations

from motor.core.embudo import (leer_eventos, log_latencia,  # noqa: E402
                               resumir_latencia, _pct)


def test_log_latencia_roundtrip(tmp_path):
    ruta = str(tmp_path)
    log_latencia(ruta, "1", "extract", cam="3", fichero="3_x.mp4",
                 frames=120, dur_s=4.5, espera_s=7.25)
    log_latencia(ruta, "1", "classify", cam="3", n_baterias=2, dur_s=1.2)
    log_latencia(ruta, "1", "bd", cam="3", foto_id=99, frame_ts=1000.0, e2e_s=42.0)

    eventos = leer_eventos(ruta, "1")
    assert len(eventos) == 3
    assert all(e["tipo"] == "latencia" for e in eventos)
    assert {e["etapa"] for e in eventos} == {"extract", "classify", "bd"}


def test_resumir_latencia_percentiles(tmp_path):
    ruta = str(tmp_path)
    for v in (1.0, 2.0, 3.0, 4.0, 100.0):
        log_latencia(ruta, "1", "bd", cam="3", foto_id=1, frame_ts=0.0, e2e_s=v)
    for v in (10.0, 20.0):
        log_latencia(ruta, "1", "extract", cam="3", dur_s=v, espera_s=v / 2)

    lat = resumir_latencia(leer_eventos(ruta, "1"))
    assert lat["e2e_s"]["n"] == 5
    assert lat["e2e_s"]["p50"] == 3.0
    assert lat["e2e_s"]["max"] == 100.0
    # p95 entre el 4º y el 5º valor (interpolado), bastante por encima de 4
    assert 4.0 < lat["e2e_s"]["p95"] <= 100.0
    assert lat["extraccion_s"]["n"] == 2
    assert lat["espera_cola_s"]["p50"] == 7.5  # (5.0 + 10.0) / 2


def test_resumir_latencia_vacio():
    lat = resumir_latencia([])
    for k in ("extraccion_s", "espera_cola_s", "clasificacion_s", "e2e_s"):
        assert lat[k] == {"n": 0, "p50": None, "p95": None, "max": None}


def test_resumir_latencia_un_solo_valor(tmp_path):
    ruta = str(tmp_path)
    log_latencia(ruta, "1", "classify", cam="3", dur_s=2.5)
    lat = resumir_latencia(leer_eventos(ruta, "1"))
    assert lat["clasificacion_s"] == {"n": 1, "p50": 2.5, "p95": 2.5, "max": 2.5}


def test_resumir_latencia_filtra_por_desde(tmp_path):
    ruta = str(tmp_path)
    log_latencia(ruta, "1", "bd", cam="3", e2e_s=5.0)
    assert resumir_latencia(leer_eventos(ruta, "1"), desde="2999-01-01")["e2e_s"]["n"] == 0


def test_ignora_eventos_no_latencia(tmp_path):
    ruta = str(tmp_path)
    from motor.core.embudo import log_evento
    log_evento(ruta, "1", "video", cam="3", frames=10)
    lat = resumir_latencia(leer_eventos(ruta, "1"))
    assert lat["e2e_s"]["n"] == 0


def test_pct_interpolacion():
    assert _pct([], 50) is None
    assert _pct([7.0], 95) == 7.0
    # mediana de [1,2,3,4] por interpolación lineal = 2.5
    assert _pct([1.0, 2.0, 3.0, 4.0], 50) == 2.5
