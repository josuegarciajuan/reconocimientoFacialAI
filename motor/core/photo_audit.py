"""Immutable classification audit sidecars, correlated by fotos.identificador_unico."""
from __future__ import annotations

import json
from pathlib import Path
from time import time

from .attributes import ATTRIBUTES_VERSION, validate_attributes


def build_audit_record(correlation_id, local_id, camera_id, classification, person,
                       layers, attributes=None, moved_at=None):
    safe_attributes = None
    if attributes is not None:
        safe_attributes = validate_attributes(attributes)
    return {
        "schema_version": "photo-audit-1",
        "correlation_id": str(correlation_id),
        "local_id": str(local_id),
        "camera_id": str(camera_id),
        "classification": str(classification),
        "person": None if person is None else str(person),
        "classification_phase": "post_move" if moved_at else "initial",
        "classified_at": time(),
        "layers": layers if isinstance(layers, dict) else {},
        "attributes": safe_attributes,
        "attributes_version": ATTRIBUTES_VERSION if safe_attributes else None,
    }


def write_audit_queue(root, local_id, camera_id, correlation_id, record):
    directory = Path(root) / "motor" / "audit_queue" / str(local_id) / str(camera_id)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{correlation_id}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(target)
    return target


def layer_scores_json(layers: dict) -> dict:
    """Serialize LayerScore values without accepting arbitrary model output."""
    out = {}
    for name, layer in (layers or {}).items():
        try:
            if isinstance(layer, dict):
                score = float(layer.get("score", 0.0))
                confidence = float(layer.get("confidence", 0.0))
                available = bool(layer.get("available", False))
            else:
                score = float(getattr(layer, "score", 0.0))
                confidence = float(getattr(layer, "confidence", 0.0))
                available = bool(getattr(layer, "available", False))
        except (AttributeError, TypeError, ValueError):
            continue
        if 0.0 <= score <= 1.0 and 0.0 <= confidence <= 1.0:
            out[str(name)] = {"score": score, "confidence": confidence, "available": available}
    return out
