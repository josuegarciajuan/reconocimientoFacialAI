"""Tests del puente de rescan (motor/reprocesar_bridge.py).

Regresión (2026-10-14): `build_request` generaba ids `req-<epoch>-<pid>`, que
colisionaban cuando el bridge enviaba varios rescans en el MISMO segundo
(parallel=6). El dict de "en vuelo" colapsaba a 1 entrada y el reprocesado de
vídeos archivados terminaba tras el primer vídeo. El id debe ser único por
petición.
"""
from __future__ import annotations

from motor.reprocesar_bridge import build_request


def test_build_request_ids_unicos_mismo_segundo():
    a = build_request("1", "14", "14_a.mp4", 2)
    b = build_request("1", "14", "14_b.mp4", 2)   # mismo (epoch, pid) que a
    c = build_request("1", "15", "15_a.mp4", 2)
    ids = {a["id"], b["id"], c["id"]}
    assert len(ids) == 3, f"ids no únicos: {ids}"


def test_build_request_contrato():
    req = build_request("1", "16", "16_x.mp4", 4, fingerprint_val="fp")
    assert req["project"] == "reconocimientoFacial"
    assert req["process"] == "rescan"
    assert req["externalId"] == "rescan:1/16/16_x.mp4"
    assert req["params"] == {"local": "1", "cam": "16", "fichero": "16_x.mp4",
                             "face_every": 4}
    assert req["fingerprint"] == "fp"


def test_build_request_respeta_rid_explicito():
    assert build_request("1", "16", "16_x.mp4", 2, rid="req-fijo")["id"] == "req-fijo"
