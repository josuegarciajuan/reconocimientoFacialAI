"""Tests del recolector de feedback (F3, §5): decisiones + etiquetas -> matriz."""
import json

import numpy as np

from motor.core.feedback import FeedbackCollector, embedding_hash
from motor.core.matching import LayerScore


def _feat_layers(s_cara, c_cara):
    return {
        "cara": {"s": s_cara, "c": c_cara},
        "torso": {"s": 0.4, "c": 0.3},
        "zona": {"s": 0.4, "c": 0.2},
        "vlm": {"s": 0.5, "c": 0.0},
        "openai": {"s": 0.5, "c": 0.0},
    }


def test_log_and_label_merge_produces_genuine(tmp_path):
    fc = FeedbackCollector(str(tmp_path), "1", enabled=True)
    emb = np.random.default_rng(1).standard_normal(512).astype(np.float32)
    emb /= np.linalg.norm(emb)
    qh = embedding_hash(emb)

    # decisión que separó A y B (person=B, top1=A) -> par genuino
    fc.log_decision({"verdict": "uncertain", "person": "B", "top1": "A", "top2": "C",
                     "best": 0.35, "second": 0.30, "layers": _feat_layers(0.35, 0.5),
                     "query_hash": qh, "stem": "x"})
    fc.log_decision({"verdict": "match", "person": "D", "top1": "D", "top2": "E",
                     "best": 0.5, "second": 0.2, "layers": _feat_layers(0.5, 0.8),
                     "query_hash": qh, "stem": "y"})
    fc.label_merge("A", "B")

    X, y = fc.export_matrix()
    assert len(X) == 1 and len(y) == 1
    assert y[0] == 1                       # genuino
    assert X.shape[1] == 10                # features fijas (s/c de 5 capas)


def test_log_and_label_move_produces_impostor(tmp_path):
    fc = FeedbackCollector(str(tmp_path), "1", enabled=True)
    emb = np.random.default_rng(2).standard_normal(512).astype(np.float32)
    emb /= np.linalg.norm(emb)
    qh = embedding_hash(emb)
    fc.log_decision({"verdict": "match", "person": "ORIGEN", "top1": "ORIGEN",
                     "top2": "Z", "best": 0.45, "second": 0.2,
                     "layers": _feat_layers(0.45, 0.7), "query_hash": qh, "stem": "z"})
    fc.label_move(qh, "ORIGEN")
    X, y = fc.export_matrix()
    assert len(X) == 1 and y[0] == 0       # impostor


def test_no_labels_returns_empty(tmp_path):
    fc = FeedbackCollector(str(tmp_path), "1", enabled=True)
    fc.log_decision({"verdict": "match", "person": "A", "top1": "A", "top2": None,
                     "best": 0.5, "second": 0.0, "layers": _feat_layers(0.5, 0.8),
                     "query_hash": "h", "stem": "x"})
    X, y = fc.export_matrix()
    assert len(X) == 0 and len(y) == 0


def test_disabled_collector_writes_nothing(tmp_path):
    fc = FeedbackCollector(str(tmp_path), "1", enabled=False)
    fc.log_decision({"verdict": "match", "layers": _feat_layers(0.5, 0.8)})
    X, y = fc.export_matrix()
    assert len(X) == 0


def test_log_decision_preserves_layer_availability_and_reason(tmp_path):
    fc = FeedbackCollector(str(tmp_path), "1", enabled=True)
    fc.log_decision({
        "verdict": "review",
        "layers": {
            "torso": LayerScore(available=False, reason="similarity_zero"),
        },
    })

    with open(fc.decisions_path, encoding="utf-8") as fh:
        logged = json.loads(fh.readline())
    assert logged["layers"]["torso"] == {
        "s": 0.0, "c": 0.0, "available": False, "reason": "similarity_zero",
    }


def test_embedding_hash_stable_and_private():
    emb = np.random.default_rng(3).standard_normal(512).astype(np.float32)
    assert embedding_hash(emb) == embedding_hash(emb.copy())
    assert len(embedding_hash(emb)) == 64   # sha256 hex
