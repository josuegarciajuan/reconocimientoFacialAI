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
