"""Contrato del wrapper/puente de re-escaneo (M3)."""
from motor.reprocesar_bridge import build_request, marcador


def test_build_request_contract():
    req = build_request("1", "15", "15_a.mp4", 2, rid="req-r")
    assert req["process"] == "rescan"
    assert req["externalId"] == "rescan:1/15/15_a.mp4"
    assert req["params"] == {"local": "1", "cam": "15", "fichero": "15_a.mp4", "face_every": 2}


def test_marcador_path():
    assert marcador("/p", "1", "15", "15_a.mp4").endswith("motor/reprocesado/1/15/15_a.mp4.done")
