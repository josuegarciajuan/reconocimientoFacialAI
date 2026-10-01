"""Protocolo de la cola del aplicador persistente (F5)."""
import os
import time

from motor import clasificador_queue as q


def test_request_roundtrip(tmp_path):
    ruta = str(tmp_path)
    assert q.write_request(ruta, 1, "b1", "15", {"a.png": []})
    reqs = q.list_requests(ruta, 1)
    assert len(reqs) == 1
    assert reqs[0]["data"]["batch"] == "b1"
    assert reqs[0]["data"]["cam"] == "15"
    assert reqs[0]["data"]["faces"] == {"a.png": []}
    q.remove_request(reqs[0]["path"])
    assert q.list_requests(ruta, 1) == []


def test_done_roundtrip(tmp_path):
    ruta = str(tmp_path)
    assert q.write_done(ruta, 1, "b1", {"batch": "b1", "rc": 0, "n": 3})
    got = q.leer_done(ruta, 1, "b1")
    assert got["rc"] == 0 and got["n"] == 3
    assert q.esperar_done(ruta, 1, "b1", 0.2)["batch"] == "b1"
    assert q.leer_done(ruta, 1, "nope") is None


def test_esperar_done_timeout(tmp_path):
    ruta = str(tmp_path)
    t0 = time.time()
    assert q.esperar_done(ruta, 1, "ausente", 0.3, 0.1) is None
    assert time.time() - t0 >= 0.25


def test_alive_heartbeat(tmp_path):
    ruta = str(tmp_path)
    assert q.daemon_alive(ruta, 1, ttl_s=5.0) is False
    q.heart_beat(ruta, 1)
    assert q.daemon_alive(ruta, 1, ttl_s=5.0) is True
    # envejecer la marca -> no vivo
    alive = os.path.join(q._paths(ruta, 1)["alive"])
    old = time.time() - 100
    os.utime(alive, (old, old))
    assert q.daemon_alive(ruta, 1, ttl_s=5.0) is False
