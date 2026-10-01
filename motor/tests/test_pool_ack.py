"""Contrato del ack casa→plano y de la huella de entradas (F2)."""
import json
import os

from motor.pool_ack import fingerprint, escribir_ack, job_dir_of, ack_path


def test_fingerprint_cambia_con_el_fichero(tmp_path):
    f = tmp_path / "a.bin"
    f.write_bytes(b"uno")
    h1 = fingerprint([str(f)])
    assert isinstance(h1, str) and len(h1) == 32
    # La huella es (ruta, tamaño, mtime): cambia al cambiar el tamaño.
    f.write_bytes(b"contenido-mas-largo")
    h2 = fingerprint([str(f)])
    assert h1 != h2


def test_fingerprint_estable_y_ordena(tmp_path):
    a = tmp_path / "a"; b = tmp_path / "b"
    a.write_bytes(b"x"); b.write_bytes(b"y")
    assert fingerprint([str(a), str(b)]) == fingerprint([str(b), str(a)])
    assert fingerprint([str(a)]) != fingerprint([str(a), str(b)])


def test_job_dir_of():
    assert job_dir_of("/var/lib/taildeck/returns/reconocimientoFacial/abc-123") == "abc-123"
    assert job_dir_of("/var/lib/taildeck/returns/reconocimientoFacial/abc-123/result/faces.json") == "abc-123"


def test_escribir_ack(tmp_path, monkeypatch):
    monkeypatch.setattr("motor.pool_ack.ACK_DIR", str(tmp_path / "acks"))
    r = escribir_ack("job-9", source="test")
    assert r and os.path.isfile(r)
    data = json.loads(open(r, encoding="utf-8").read())
    assert data["jobId"] == "job-9" and data["status"] == "applied" and data["source"] == "test"
    # atómico: no queda .tmp
    assert not any(n.endswith(".tmp") for n in os.listdir(os.path.dirname(r)))
