"""Robustez del aplicador ante datos corruptos del pool (no bloquear la cola).

Regresión: un `faces.json` con un valor que no era lista (string) hacía
`d["bbox"]` -> "string indices must be integers"; la petición fallaba y, al no
borrarse, el aplicador la reintentaba cada segundo para siempre (classify
bloqueado). Ahora el parser salta entradas inválidas y la petición irrecuperable
se mueve a `failed/`.
"""
import json
import os

from motor.clasificador import _faces_from_dict
from motor.clasificador_queue import fail_request, queue_dirs


def _face_dict():
    return {"bbox": [0, 0, 10, 10], "det_score": 0.9,
            "embedding": [0.01] * 512, "pose": [0.0, 0.0, 0.0]}


def test_faces_from_dict_ignora_no_lista_y_no_dict():
    raw = {
        "valido.png": [_face_dict()],
        "string.png": "no soy una lista",              # antes: TypeError
        "dict.png": {"bbox": [0, 0, 1, 1]},            # no es lista -> se salta
        "mezcla.png": [_face_dict(), "basura", {"sin": "claves"}, {"bbox": [0, 0, 1, 1]}],
    }
    out = _faces_from_dict(raw)
    assert set(out) >= {"valido.png", "mezcla.png"}
    assert len(out["valido.png"]) == 1
    # de la mezcla solo sobrevive la entrada válida
    assert len(out["mezcla.png"]) == 1
    # "string.png" no está (no era lista); "dict.png" tampoco
    assert "string.png" not in out
    assert "dict.png" not in out


def test_faces_from_dict_raw_no_dict_devuelve_vacio():
    assert _faces_from_dict(None) == {}
    assert _faces_from_dict("texto") == {}
    assert _faces_from_dict([]) == {}


def test_faces_from_dict_bbox_invalido_no_lanza():
    raw = {"x.png": [{"bbox": ["a", "b", "c", "d"], "embedding": [0.0] * 512}]}
    out = _faces_from_dict(raw)
    assert out.get("x.png") == []


def test_fail_request_mueve_a_failed(tmp_path):
    in_dir, _ = queue_dirs(str(tmp_path), "1")
    os.makedirs(in_dir, exist_ok=True)
    bad = os.path.join(in_dir, "malo.json")
    with open(bad, "w", encoding="utf-8") as fh:
        json.dump({"batch": "malo", "cam": "13", "faces": "corrupto"}, fh)

    dst = fail_request(str(tmp_path), "1", bad)
    assert dst is not None
    assert not os.path.exists(bad)
    assert os.path.exists(dst)
    assert dst.endswith(os.path.join("failed", "malo.json"))
