"""F18: dispatcher en paralelo con aplicación FIFO (sin red)."""
import motor.clasificador_bridge as B


def test_paralelo_aplica_en_orden_de_submision(monkeypatch):
    chunks = [["a.png"], ["b.png"], ["c.png"]]
    aplicados = []

    def fake_build(local, cam, ruta, dir_in, chunk):
        bid = chunk[0]
        return {"batch_id": bid, "bdir": "/x/" + bid, "bdir_busto": "/x/", "req": {"id": "r-" + bid, "externalId": bid}}

    # resultados listos en orden INVERSO (c, b, a) para probar el FIFO
    listos = {"c.png", "b.png", "a.png"}
    orden_entrega = ["c.png", "b.png", "a.png"]

    def fake_buscar(local, cam, bid):
        if bid in orden_entrega:
            orden_entrega.remove(bid)
            return ({"faces": {}, "busto": {}}, "/ret/" + bid)
        return None

    monkeypatch.setattr(B, "_build_batch", fake_build, raising=False)
    monkeypatch.setattr(B, "escribir_peticion", lambda req: None, raising=False)
    monkeypatch.setattr(B, "_cola_aplicador", lambda ruta, local: 0, raising=False)
    monkeypatch.setattr(B, "buscar_faces", fake_buscar, raising=False)
    monkeypatch.setattr(B, "_limpiar_batch", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(B, "escribir_ack", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(B, "job_dir_of", lambda p: "job", raising=False)

    def fake_aplicar(ruta, local, cam, bid, data, timeout):
        aplicados.append(bid)
        return 0

    monkeypatch.setattr(B, "_aplicar_local", fake_aplicar, raising=False)

    n = B._procesar_cam_paralelo("1", "15", "/ruta", "/dir", chunks, 10, 0.01, 2, 8)
    assert n == 3
    # Aplicado en ORDEN de submisión aunque los resultados lleguen al revés.
    assert aplicados == ["a.png", "b.png", "c.png"]


def test_cola_no_supera_el_limite(monkeypatch):
    chunks = [["a.png"], ["b.png"], ["c.png"], ["d.png"]]
    vistos = {"max": 0}

    def fake_build(local, cam, ruta, dir_in, chunk):
        bid = chunk[0]
        return {"batch_id": bid, "bdir": "/x/" + bid, "bdir_busto": "/x/", "req": {"id": "r-" + bid, "externalId": bid}}

    # nunca hay resultados: solo comprobamos que no se envían más de `inflight`.
    enviados = {"n": 0}

    def fake_escribir(req):
        enviados["n"] += 1
        vistos["max"] = max(vistos["max"], enviados["n"] - 0)

    monkeypatch.setattr(B, "_build_batch", fake_build, raising=False)
    monkeypatch.setattr(B, "escribir_peticion", fake_escribir, raising=False)
    monkeypatch.setattr(B, "_cola_aplicador", lambda ruta, local: 0, raising=False)
    monkeypatch.setattr(B, "buscar_faces", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(B, "_limpiar_batch", lambda *a, **k: None, raising=False)

    # con inflight=2 y sin resultados, solo se envían 2 lotes y luego se espera:
    # cortamos el bucle lanzándolo en un hilo con timeout corto.
    import threading
    done = {"v": False}

    def run():
        try:
            B._procesar_cam_paralelo("1", "15", "/ruta", "/dir", chunks, 10.0, 0.01, 2, 8)
        except Exception:
            pass
        done["v"] = True

    t = threading.Thread(target=run, daemon=True)
    t.start()
    t.join(1.5)
    assert enviados["n"] == 2  # nunca supera inflight cuando no hay resultados
