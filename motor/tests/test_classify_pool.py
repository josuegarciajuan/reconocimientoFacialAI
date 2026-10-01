"""Contrato del split de embeddings para `classify` (M3)."""
import json

import numpy as np

from motor.clasificador import _cargar_faces_provider
from motor.clasificador_bridge import build_request


def test_build_request_contract():
    carpeta = "/root/reconocimientoFacial/motor/caras/sinclasificar/1/15"
    req = build_request("1", "15", carpeta, rid="req-c")
    assert req["process"] == "classify"
    assert req["externalId"] == "classify:1/15"
    assert req["params"] == {"local": "1", "cam": "15", "dir": carpeta}


def test_provider_reconstruye_faces(tmp_path):
    emb = [0.1] * 512
    data = {"a.png": [{"bbox": [1, 2, 3, 4], "det_score": 0.9,
                       "pose": [1.0, 2.0, 3.0], "embedding": emb}]}
    p = tmp_path / "faces.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    prov = _cargar_faces_provider(str(p))
    faces = prov["a.png"]
    assert len(faces) == 1
    f = faces[0]
    assert tuple(f.bbox) == (1, 2, 3, 4)
    assert abs(f.det_score - 0.9) < 1e-9
    assert tuple(f.pose) == (1.0, 2.0, 3.0)
    assert isinstance(f.embedding, np.ndarray) and f.embedding.shape == (512,)
