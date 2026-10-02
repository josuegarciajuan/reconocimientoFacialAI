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
