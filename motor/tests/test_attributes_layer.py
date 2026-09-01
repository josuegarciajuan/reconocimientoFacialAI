from motor.core.attributes import attributes_layer_score
from motor.core.fusion import CascadeContext, run_cascade
from motor.core.config import Config
from motor.core.matching import LayerScore


def test_attributes_are_low_weight_corroboration_only():
    score = attributes_layer_score(
        {"version": "appearance-1", "attributes": {"glasses": "visible", "headwear": "unknown"}},
        {"version": "appearance-1", "attributes": {"glasses": "absent", "headwear": "unknown"}},
    )
    assert score.available
    assert score.confidence < 1.0
    assert score.score < 0.5


def test_attributes_unknown_is_unavailable_not_negative_evidence():
    score = attributes_layer_score({"glasses": "unknown"}, {"glasses": "visible"})
    assert not score.available


def test_attributes_alone_cannot_confirm_identity():
    cfg = Config(cascade_enabled=True, attributes_enabled=True, torso_enabled=True,
                 match_threshold=0.30, secure_threshold=0.45,
                 new_low_floor=0.15, gray_high=0.42)
    result = run_cascade(
        {"A": 0.33, "B": 0.30},
        CascadeContext(attributes=lambda cod: LayerScore(0.99, 0.99, True)),
        cfg, LayerScore(0.33, 0.8),
    )
    assert result.verdict == "uncertain"


def test_attributes_can_support_but_not_replace_independent_evidence():
    cfg = Config(cascade_enabled=True, attributes_enabled=True, torso_enabled=True,
                 match_threshold=0.30, secure_threshold=0.45,
                 new_low_floor=0.15, gray_low=0.28, gray_high=0.42,
                 min_layer_conf=0.70)
    result = run_cascade(
        {"A": 0.33, "B": 0.30},
        CascadeContext(
            torso=lambda cod: LayerScore(0.35, 0.80, True),
            attributes=lambda cod: LayerScore(0.99, 0.99, True)),
        cfg, LayerScore(0.33, 0.8),
    )
    assert result.verdict == "match"
