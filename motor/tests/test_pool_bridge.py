"""Contrato del puente del pool de SuperServer (M3).

Prueba pura (sin vídeo ni modelos): forma de la petición de spool y rutas del
contrato con el panel.
"""
from motor.pool_bridge import (MODE_FILE, RETURNS_DIR, SPOOL_DIR, build_request)


def test_build_request_contract():
    lineas = [{"id": "7", "x1": 1, "y1": 2, "x2": 3, "y2": 4}]
    req = build_request("1", "15", "15_x.mp4", lineas, rid="req-test")
    assert req["id"] == "req-test"
    assert req["project"] == "reconocimientoFacial"
    assert req["process"] == "video_faces"
    assert req["externalId"] == "video:1/15/15_x.mp4"
    assert req["params"]["local"] == "1"
    assert req["params"]["cam"] == "15"
    assert req["params"]["fichero"] == "15_x.mp4"
    assert req["params"]["lineas"] == lineas


def test_rutas_del_contrato():
    assert SPOOL_DIR == "/var/lib/taildeck/spool"
    assert RETURNS_DIR == "/var/lib/taildeck/returns/reconocimientoFacial"
    assert MODE_FILE == "/var/lib/taildeck/projects/reconocimientoFacial.mode"
