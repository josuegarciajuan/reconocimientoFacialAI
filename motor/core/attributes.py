"""Structured visible-appearance attributes.

This is deliberately not an identity representation.  Unknown values are
omitted from evidence and the result can only be used as a low-weight report
or corroborating signal.
"""
from __future__ import annotations

from .matching import LayerScore
import json

ATTRIBUTES_VERSION = "appearance-1"
ATTRIBUTES_PROMPT = """Inspect this one image and return ONLY JSON with version \"appearance-1\", attributes, and confidence. Use unknown when not clearly visible. attributes keys: glasses, headwear, mask, beard_moustache, hair, accessories, clothing_color. Never provide reasoning."""
FIELDS = {
    "glasses": {"visible", "absent", "unknown"},
    "headwear": {"visible", "absent", "unknown"},
    "mask": {"visible", "absent", "unknown"},
    "beard_moustache": {"visible", "absent", "unknown"},
    "hair": {"visible", "silhouette", "absent", "unknown"},
    "accessories": {"unknown", "none", "backpack", "bag", "scarf", "jewellery", "other"},
    "clothing_color": {"black", "white", "gray", "blue", "green", "red", "yellow", "brown", "orange", "purple", "multicolor", "unknown"},
}


def validate_attributes(payload: object) -> dict | None:
    """Return a canonical safe payload, or None (fail closed).

    Free-form model fields, including reasoning, are intentionally not copied.
    """
    if not isinstance(payload, dict) or payload.get("version") != ATTRIBUTES_VERSION:
        return None
    raw = payload.get("attributes")
    if not isinstance(raw, dict):
        return None
    out = {}
    for field, allowed in FIELDS.items():
        value = raw.get(field, "unknown")
        if field == "accessories" and isinstance(value, list):
            if not value or any(not isinstance(v, str) or v not in allowed - {"unknown"} for v in value):
                return None
            out[field] = sorted(set(value))
        elif isinstance(value, str) and value in allowed:
            out[field] = value
        else:
            return None
    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        return None
    if not 0.0 <= confidence <= 1.0:
        return None
    return {"version": ATTRIBUTES_VERSION, "attributes": out, "confidence": confidence}


def parse_attributes_response(content: object) -> dict | None:
    """Strictly parse a model response; markdown/free text is rejected."""
    if not isinstance(content, str):
        return validate_attributes(content)
    try:
        payload = json.loads(content)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return validate_attributes(payload)


def attributes_layer_score(query: dict, candidate: dict) -> LayerScore:
    """Score only mutually visible fields; unknown never contradicts."""
    if not isinstance(query, dict) or not isinstance(candidate, dict):
        return LayerScore(available=False)
    query = query.get("attributes", query)
    candidate = candidate.get("attributes", candidate)
    comparable = [k for k in FIELDS if query.get(k) not in (None, "unknown")
                  and candidate.get(k) not in (None, "unknown")]
    if not comparable:
        return LayerScore(available=False)
    matches = sum(query[k] == candidate[k] for k in comparable)
    score = matches / len(comparable)
    return LayerScore(score=score, confidence=min(0.35, len(comparable) / len(FIELDS)), available=True)
