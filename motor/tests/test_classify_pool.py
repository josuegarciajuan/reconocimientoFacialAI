"""Contrato del split de embeddings para `classify` (M3)."""
import json

import numpy as np

from motor.clasificador import _cargar_faces_provider
from motor.clasificador_bridge import build_request, _batch_id


def test_build_request_contract():
    carpeta = "/root/reconocimientoFacial/motor/caras/sinclasificar/1/15"
    req = build_request("1", "15", carpeta, batch_id="abc123", fingerprint_val="f1", rid="req-c")
    assert req["process"] == "classify"
    assert req["externalId"] == "classify:1/15/abc123"
    assert req["params"] == {"local": "1", "cam": "15", "dir": carpeta, "batch": "abc123"}
    assert req["fingerprint"] == "f1"
    # sin lote no hay sufijo en externalId
    req2 = build_request("1", "15", carpeta, rid="r2")
    assert req2["externalId"] == "classify:1/15"
    assert req2["params"]["batch"] is None


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


def test_batch_id_estable():
    assert _batch_id(["a.png", "b.png"]) == _batch_id(["a.png", "b.png"])
    assert _batch_id(["a.png", "b.png"]) != _batch_id(["a.png", "c.png"])
    assert len(_batch_id(["x.png"])) == 12


def test_split_providers_nuevo_y_antiguo():
    from motor.clasificador import _split_providers
    emb = [0.1] * 512
    nuevo = {"faces": {"a.png": [{"bbox": [1, 2, 3, 4], "det_score": 1.0,
                                  "pose": [0, 0, 0], "embedding": emb}]},
             "busto": {"b.png": []}}
    faces, busto = _split_providers(nuevo)
    assert "a.png" in faces and len(faces["a.png"]) == 1
    assert "b.png" in busto and busto["b.png"] == []
    # formato antiguo: dict plano filename->faces
    faces2, busto2 = _split_providers({"a.png": []})
    assert "a.png" in faces2 and busto2 == {}
