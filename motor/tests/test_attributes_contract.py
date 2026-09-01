import json

from motor.core.attributes import ATTRIBUTES_VERSION, validate_attributes


def test_attributes_contract_accepts_known_values_and_discards_reasoning():
    payload = {
        "version": ATTRIBUTES_VERSION,
        "attributes": {
            "glasses": "visible",
            "headwear": "unknown",
            "mask": "absent",
            "beard_moustache": "visible",
            "hair": "silhouette",
            "accessories": ["backpack"],
            "clothing_color": "blue",
        },
        "confidence": 0.8,
        "reasoning": "must not be persisted",
    }
    result = validate_attributes(payload)
    assert result["version"] == ATTRIBUTES_VERSION
    assert result["attributes"]["glasses"] == "visible"
    assert "reasoning" not in result


def test_attributes_contract_fails_closed_on_invalid_json_shape():
    assert validate_attributes({"attributes": {"glasses": "maybe"}}) is None
    assert validate_attributes(json.loads('{"attributes": []}')) is None
