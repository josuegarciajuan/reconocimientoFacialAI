"""F17c: los frames de HQ usan la detección de busto del pool (sin analyze local)."""
import cv2
import numpy as np

import motor.clasificador as C
from motor.core.config import Config
from motor.core.model import Face


def _face(emb_val=1.0):
    return Face(bbox=(0, 0, 20, 20), det_score=1.0,
                embedding=np.full(8, emb_val, dtype=np.float32), pose=(0.0, 0.0, 0.0))


def test_collect_hq_frames_usa_provider_sin_analyze(tmp_path, monkeypatch):
    cfg = Config()
    cfg.sr_mf_enabled = True
    cfg.sr_mf_k = 3
    cfg.sr_mf_min_face = 1000  # fuerza MF-SR (rep pequeña)

    img = np.zeros((40, 40, 3), dtype=np.uint8)
    b2 = tmp_path / "busto2.png"
    cv2.imwrite(str(b2), img)

    f = _face()
    it1 = {"file": "stem1.png", "img": img, "faces": [f]}
    it2 = {"file": "stem2.png", "img": img, "faces": [f]}
    battery = [it1, it2]
    members = [(f.embedding, 0, 0), (f.embedding, 1, 0)]
    busto_map = {"stem1": str(tmp_path / "b1.png"), "stem2": str(b2)}

    prov = {"busto2.png": [_face()]}
    monkeypatch.setattr(C, "_BUSTO_PROVIDER", prov, raising=False)

    def boom(*a, **k):
        raise AssertionError("analyze() no debe llamarse: el busto viene del pool")

    monkeypatch.setattr(C, "analyze", boom)

    frames = C._collect_hq_frames(img, (0, 0, 20, 20), members, battery,
                                  busto_map, f, "stem1", cfg)
    assert len(frames) == 2  # frame 0 + busto del pool
