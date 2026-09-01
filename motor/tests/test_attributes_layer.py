from motor.core.attributes import attributes_layer_score


def test_attributes_are_low_weight_corroboration_only():
    score = attributes_layer_score(
        {"glasses": "visible", "headwear": "unknown"},
        {"glasses": "absent", "headwear": "unknown"},
    )
    assert score.available
    assert score.confidence < 1.0
    assert score.score < 0.5


def test_attributes_unknown_is_unavailable_not_negative_evidence():
    score = attributes_layer_score({"glasses": "unknown"}, {"glasses": "visible"})
    assert not score.available
