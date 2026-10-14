"""Contrato del wrapper/puente de re-escaneo (M3) y regresión de ids únicos."""
from motor.reprocesar_bridge import build_request, marcador, recolectar_pendientes


def test_build_request_contract():
    req = build_request("1", "15", "15_a.mp4", 2, rid="req-r")
    assert req["process"] == "rescan"
    assert req["externalId"] == "rescan:1/15/15_a.mp4"
    assert req["params"] == {"local": "1", "cam": "15", "fichero": "15_a.mp4", "face_every": 2}


def test_marcador_path():
    assert marcador("/p", "1", "15", "15_a.mp4").endswith("motor/reprocesado/1/15/15_a.mp4.done")


def test_recolectar_pendientes_salta_marcados(tmp_path):
    base = tmp_path / "motor/videos_archivo/1/15"
    base.mkdir(parents=True)
    (base / "a.mp4").write_bytes(b"x")
    (base / "b.mp4").write_bytes(b"x")
    (base / "c.avi").write_bytes(b"x")  # no-mp4: ignorado
    # b ya está marcado
    m = tmp_path / "motor/reprocesado/1/15/b.mp4.done"
    m.parent.mkdir(parents=True)
    m.write_text("t")
    pend = recolectar_pendientes(str(tmp_path), ["1"], force=False)
    assert pend == [("1", "15", "a.mp4")]
    # force ignora el marker pero sigue filtrando .mp4
    pend_force = recolectar_pendientes(str(tmp_path), ["1"], force=True)
    assert sorted(f for _l, _c, f in pend_force) == ["a.mp4", "b.mp4"]


# ---------------------------------------------------------------------------
# Regresión (2026-10-14): el id `req-<epoch>-<pid>` colisionaba al enviar varios
# rescans en el mismo segundo (parallel=6): el dict "en vuelo" del bridge
# colapsaba a 1 entrada y el reprocesado terminaba tras el primer vídeo.
# ---------------------------------------------------------------------------

def test_build_request_ids_unicos_mismo_segundo():
    a = build_request("1", "14", "14_a.mp4", 2)
    b = build_request("1", "14", "14_b.mp4", 2)   # mismo (epoch, pid) que a
    c = build_request("1", "15", "15_a.mp4", 2)
    ids = {a["id"], b["id"], c["id"]}
    assert len(ids) == 3, f"ids no únicos: {ids}"


def test_build_request_respeta_rid_explicito():
    assert build_request("1", "16", "16_x.mp4", 2, rid="req-fijo")["id"] == "req-fijo"
