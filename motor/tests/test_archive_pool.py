"""Contrato del wrapper/puente de archivado (M3)."""
from motor.archiva_video_bridge import build_request, nombre_mp4


def test_nombre_mp4():
    assert nombre_mp4("15_2026-09-30_12:38:30.780734.avi") == "15_2026-09-30_12:38:30.780734.mp4"
    assert nombre_mp4("16_x.mp4") == "16_x.mp4"


def test_build_request_contract():
    req = build_request("1", "15", "15_a.avi", 20, 10, "medium", rid="req-z")
    assert req["id"] == "req-z"
    assert req["project"] == "reconocimientoFacial"
    assert req["process"] == "archive"
    assert req["externalId"] == "archive:1/15/15_a.avi"
    assert req["params"] == {"local": "1", "cam": "15", "fichero": "15_a.avi",
                             "crf": 20, "fps": 10, "preset": "medium",
                             "name": "15_a.mp4"}
