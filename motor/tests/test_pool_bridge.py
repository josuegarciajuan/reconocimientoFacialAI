"""Contrato del puente del pool de SuperServer (M3).

Prueba pura (sin vídeo ni modelos): forma de la petición de spool y rutas del
contrato con el panel.
"""
import json

from motor.pool_bridge import (MODE_FILE, RETURNS_DIR, SPOOL_DIR, _leer_resultado,
                                build_request)


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


def test_lee_resultado_dentro_del_directorio_result_del_executor(tmp_path):
    # El executor de SuperServer entrega outputs como <job>/result/efectos.json.
    result = tmp_path / "result"
    result.mkdir()
    (result / "efectos.json").write_text(json.dumps({"local": "1", "cam": "15"}), encoding="utf-8")
    assert _leer_resultado(str(tmp_path)) == {"local": "1", "cam": "15"}


def test_aplicar_mueve_el_frame_nativo(tmp_path):
    """aplicar() debe traer también <cam>_frame/ (evidencia "Frame original" 1080p)."""
    from motor.pool_bridge import aplicar

    result = tmp_path / "result"
    base = result / "motor" / "caras" / "sinclasificar" / "1"
    for sufijo in ("", "_busto", "_cuerpo", "_frame"):
        d = base / f"21{sufijo}"
        d.mkdir(parents=True)
        (d / "21_x_0.jpg").write_bytes(b"px")

    ruta = tmp_path / "house"
    ruta.mkdir()
    aplicar(str(result), {"local": "1", "cam": "21", "fichero": "v.mp4"},
            "1", "21", "v.mp4", str(ruta))

    for sufijo in ("", "_busto", "_cuerpo", "_frame"):
        assert (ruta / "motor" / "caras" / "sinclasificar" / "1" / f"21{sufijo}" / "21_x_0.jpg").exists()
