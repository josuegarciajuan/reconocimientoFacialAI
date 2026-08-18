"""Tests de store.py (face_enc_v2): persistencia, concurrencia, prune, merge."""
import os
import threading

import numpy as np

from motor.core.store import FaceStore, SCHEMA, VERSION


def rnd_emb(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(512)
    return v / np.linalg.norm(v)


def test_empty_store(tmp_path):
    s = FaceStore(str(tmp_path / "f"))
    assert s.persons() == []
    assert s.person_encodings("X") is None


def test_add_and_read(tmp_path):
    s = FaceStore(str(tmp_path / "f"), max_per_person=10)
    s.add("A", [rnd_emb(1), rnd_emb(2)], [70.0, 80.0], ["f", "pd"])
    assert s.persons() == ["A"]
    assert s.count("A") == 2
    enc = s.person_encodings("A")
    assert enc.shape == (2, 512)


def test_persistence_across_instances(tmp_path):
    p = str(tmp_path / "f")
    FaceStore(p).add("A", [rnd_emb(1)], [80.0], ["f"])
    s2 = FaceStore(p)
    assert s2.persons() == ["A"]


def test_schema_version(tmp_path):
    p = str(tmp_path / "f")
    FaceStore(p).add("A", [rnd_emb(1)], [80.0], ["f"])
    import pickle
    with open(p, "rb") as fh:
        data = pickle.load(fh)
    assert data["schema"] == SCHEMA and data["version"] == VERSION


def test_prune_keeps_best_quality(tmp_path):
    s = FaceStore(str(tmp_path / "f"), max_per_person=3)
    encs = [rnd_emb(i) for i in range(5)]
    quals = [10.0, 50.0, 90.0, 30.0, 70.0]
    s.add("A", encs, quals, ["f"] * 5)
    assert s.count("A") == 3
    kept = s.person("A")["quality"]
    assert sorted(kept, reverse=True) == [90.0, 70.0, 50.0]


def test_merge(tmp_path):
    p = str(tmp_path / "f")
    s = FaceStore(p)
    s.add("A", [rnd_emb(1)], [80.0], ["f"])
    s.add("B", [rnd_emb(2), rnd_emb(3)], [70.0, 60.0], ["pi", "pd"])
    s.merge("A", "B")
    assert set(s.persons()) == {"A"}
    assert s.count("A") == 3


def test_rename(tmp_path):
    p = str(tmp_path / "f")
    s = FaceStore(p)
    s.add("A", [rnd_emb(1)], [80.0], ["f"])
    s.rename("A", "Z")
    assert s.persons() == ["Z"]


def test_remove(tmp_path):
    p = str(tmp_path / "f")
    s = FaceStore(p)
    s.add("A", [rnd_emb(1)], [80.0], ["f"])
    s.remove("A")
    assert s.persons() == []


def test_remove_closest(tmp_path):
    p = str(tmp_path / "f")
    s = FaceStore(p)
    a = rnd_emb(1)
    b = rnd_emb(2)
    s.add("ORIGEN", [a, b], [80.0, 70.0], ["f", "f"])
    # quitar la más parecida a `a` (ella misma, coseno 1.0)
    removed = s.remove_closest("ORIGEN", a, min_cosine=0.5)
    assert removed == 1
    assert s.count("ORIGEN") == 1
    restantes = s.person_encodings("ORIGEN")
    assert abs(float(restantes[0] @ b)) > 0.9  # queda la otra


def test_remove_closest_por_debajo_umbral(tmp_path):
    p = str(tmp_path / "f")
    s = FaceStore(p)
    a = rnd_emb(1)
    s.add("ORIGEN", [a], [80.0], ["f"])
    removed = s.remove_closest("ORIGEN", rnd_emb(99), min_cosine=0.9)
    assert removed == 0
    assert s.count("ORIGEN") == 1


def test_concurrent_adds_no_loss(tmp_path):
    p = str(tmp_path / "f")
    s = FaceStore(p)
    errors = []

    def worker(seed):
        try:
            for _ in range(20):
                s.add(f"P{seed}", [rnd_emb(seed)], [80.0], ["f"])
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert not errors
    assert set(s.persons()) == {f"P{i}" for i in range(8)}


# --- F1/F6: apariencia + snapshot/merge_undoable ---

def test_add_appearance_and_read(tmp_path):
    s = FaceStore(str(tmp_path / "f"), max_per_person=10)
    s.add("A", [rnd_emb(1)], [80.0], ["f"])
    s.add_appearance("A", np.full(144, 0.01, dtype=np.float32), ts=1.0, src="crop.jpg")
    ap = s.person_appearance("A")
    assert ap and len(ap["desc"]) == 1
    assert ap["ts"] == [1.0]
    assert ap["src"] == ["crop.jpg"]


def test_merge_undoable_journal(tmp_path):
    p = str(tmp_path / "f")
    s = FaceStore(p)
    s.add("A", [rnd_emb(1)], [80.0], ["f"])
    s.add("B", [rnd_emb(2), rnd_emb(3)], [70.0, 60.0], ["pi", "pd"])
    s.add_appearance("B", np.full(144, 0.5, dtype=np.float32), ts=2.0, src="b.jpg")

    journal = s.merge_undoable("A", "B")
    assert journal["op"] == "merge"
    assert journal["src"] == "B" and journal["dst"] == "A"
    assert journal["encodings_moved"] == 2
    assert "src_person" in journal and journal["src_person"]["encodings"]

    # después del merge: B eliminada, A con 3 encodings + apariencia fusionada
    assert set(s.persons()) == {"A"}
    assert s.count("A") == 3
    assert len(s.person_appearance("A")["desc"]) == 1

    # rollback: re-inyectar la persona fuente
    s.restore_person("B", journal["src_person"])
    assert set(s.persons()) == {"A", "B"}
    assert s.count("B") == 2
    assert len(s.person_appearance("B")["desc"]) == 1


def test_snapshot_deep_copy(tmp_path):
    s = FaceStore(str(tmp_path / "f"), max_per_person=10)
    s.add("A", [rnd_emb(1)], [80.0], ["f"])
    snap = s.snapshot()
    assert snap["persons"]["A"]["encodings"]
    s.add("B", [rnd_emb(2)], [70.0], ["f"])
    assert "B" not in snap["persons"]      # copia independiente


def test_save_load_snapshot_bytes(tmp_path):
    p = str(tmp_path / "f")
    s = FaceStore(p)
    s.add("A", [rnd_emb(1)], [80.0], ["f"])
    out = str(tmp_path / "backup" / "face_enc_v2.bak")
    s.save_snapshot_bytes(out)
    s2 = FaceStore(p)
    data = s2.load_snapshot_bytes(out)
    assert set(data["persons"]) == {"A"}
