"""Contrato del wrapper/puente de avatar (M3)."""
import json

from motor.avatar_bridge import build_request
from motor.avatar_pool import cargar_fotos


def test_cargar_fotos_filtra_invalidos(tmp_path):
    f = tmp_path / "fotos.json"
    f.write_text(json.dumps([{"id": 3, "src": "/a/3.jpg"}, {"id": 0, "src": "/a/x.jpg"},
                             {"id": "5", "src": "/a/5.jpg"}, {"id": 7}]), encoding="utf-8")
    assert cargar_fotos(str(f)) == [(3, "/a/3.jpg"), (5, "/a/5.jpg")]


def test_build_request_contract():
    fotos = [{"id": 3, "src": "/a/3.jpg"}]
    req = build_request(fotos, "/x/12.png", 96, rid="req-a")
    assert req["id"] == "req-a"
    assert req["project"] == "reconocimientoFacial"
    assert req["process"] == "avatar"
    assert req["externalId"] == "avatar:/x/12.png"
    assert req["params"]["fotos"] == fotos
    assert req["params"]["out"] == "/x/12.png"
    assert req["params"]["size"] == 96
