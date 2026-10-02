"""F17b: la caché evita re-leer el pickle cuando somos el único escritor."""
import numpy as np

import motor.core.store as storemod
from motor.core.store import FaceStore


def _emb(v):
    a = np.zeros(8, dtype=np.float32)
    a[0] = v
    return a


def test_transacciones_reutilizan_cache(tmp_path, monkeypatch):
    s = FaceStore(str(tmp_path / "g.pkl"), max_per_person=50)
    s.add("a", [_emb(1.0)], [1.0], ["frontal"])
    assert s.count("a") == 1

    calls = {"n": 0}
    orig = storemod.pickle.load

    def counting(fh):
        calls["n"] += 1
        return orig(fh)

    monkeypatch.setattr(storemod.pickle, "load", counting)
    s.add("a", [_emb(2.0)], [1.0], ["frontal"])
    # No debe releer de disco: la caché es válida (somos el último escritor).
    assert calls["n"] == 0
    assert s.count("a") == 2


def test_recarga_si_otro_proceso_escribe(tmp_path, monkeypatch):
    import pickle
    s = FaceStore(str(tmp_path / "g.pkl"), max_per_person=50)
    s.add("a", [_emb(1.0)], [1.0], ["frontal"])

    # Simular una escritura EXTERNA: reemplazar el fichero por otro estado.
    with open(s.path, "wb") as fh:
        pickle.dump({"schema": storemod.SCHEMA, "persons": {}}, fh)

    calls = {"n": 0}
    orig = storemod.pickle.load

    def counting(fh):
        calls["n"] += 1
        return orig(fh)

    monkeypatch.setattr(storemod.pickle, "load", counting)
    s.add("b", [_emb(3.0)], [1.0], ["frontal"])
    assert calls["n"] >= 1  # detectó el cambio por (mtime/tamaño) y recargó


def test_defer_agrupa_mutaciones_en_una_escritura(tmp_path, monkeypatch):
    s = FaceStore(str(tmp_path / "g.pkl"), max_per_person=50)
    s.add("a", [_emb(1.0)], [1.0], ["frontal"])

    writes = {"n": 0}
    orig = storemod.pickle.dump

    def counting(obj, fh, *a, **k):
        writes["n"] += 1
        return orig(obj, fh, *a, **k)

    monkeypatch.setattr(storemod.pickle, "dump", counting)
    s.begin_defer()
    s.add("a", [_emb(2.0)], [1.0], ["frontal"])
    s.add_appearance("a", np.ones(4, dtype=np.float32), ts=1.0, src="x")
    s.add_attributes("a", {"k": 1}, ts=1.0, src="x")
    assert writes["n"] == 0          # nada escrito mientras está diferido
    n = s.flush_defer()
    assert n == 3 and writes["n"] == 1   # UNA sola escritura para 3 mutaciones
    assert s.count("a") == 2
    assert s.person_appearance("a")["desc"]
    assert s.person_attributes("a")["values"]
