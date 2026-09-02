"""Immutable classification audit sidecars, correlated by fotos.identificador_unico."""
from __future__ import annotations

import json
from pathlib import Path
from time import time

from .attributes import ATTRIBUTES_VERSION, validate_attributes
from .safe_paths import safe_component


def build_audit_record(correlation_id, local_id, camera_id, classification, person,
                       layers, attributes=None, moved_at=None, meta=None):
    safe_component(correlation_id); safe_component(local_id); safe_component(camera_id)
    safe_attributes = None
    if attributes is not None:
        safe_attributes = validate_attributes(attributes)
    record = {
        "schema_version": "photo-audit-1",
        "correlation_id": str(correlation_id),
        "local_id": str(local_id),
        "camera_id": str(camera_id),
        "classification": str(classification),
        "person": None if person is None else str(person),
        "classification_phase": "initial",
        "classified_at": time(),
        "layers": layers if isinstance(layers, dict) else {},
        "attributes": safe_attributes,
        "attributes_version": ATTRIBUTES_VERSION if safe_attributes else None,
    }
    # A1 (2026-09-02): trazabilidad de la decisión (rama, mapa top-N de scores,
    # config efectiva, pose/stem). El validador PHP ignora claves extra.
    if isinstance(meta, dict):
        record.update({k: v for k, v in meta.items() if k not in record})
    return record


def write_audit_queue(root, local_id, camera_id, correlation_id, record):
    directory = Path(root) / "motor" / "audit_queue" / safe_component(local_id) / safe_component(camera_id)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{safe_component(correlation_id)}.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temporary.replace(target)
    return target


def write_move_event(root, local_id, camera_id, event):
    """Append a movement event to the local/camera stream journal."""
    path = Path(root) / "motor" / "audit_queue" / safe_component(local_id) / safe_component(camera_id) / "move_events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")
    return path


def post_move_event_for(path, person_code, classified_at):
    """Find the latest prior event targeting this person, never another one."""
    latest = None
    try:
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event.get("to_person_code") != person_code:
                continue
            if float(event.get("moved_at_epoch", event.get("moved_at", 0))) <= classified_at:
                if latest is None or float(event.get("moved_at_epoch", 0)) > float(latest.get("moved_at_epoch", 0)):
                    latest = event
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    return latest


def layer_scores_json(layers: dict) -> dict:
    """Serialize LayerScore values without accepting arbitrary model output."""
    out = {}
    for name, layer in (layers or {}).items():
        try:
            if isinstance(layer, dict):
                score = float(layer.get("score", 0.0))
                confidence = float(layer.get("confidence", 0.0))
                available = bool(layer.get("available", False))
                reason = str(layer.get("reason", ""))
            else:
                score = float(getattr(layer, "score", 0.0))
                confidence = float(getattr(layer, "confidence", 0.0))
                available = bool(getattr(layer, "available", False))
                reason = str(getattr(layer, "reason", ""))
        except (AttributeError, TypeError, ValueError):
            continue
        if 0.0 <= score <= 1.0 and 0.0 <= confidence <= 1.0:
            rec = {"score": score, "confidence": confidence, "available": available}
            if reason:  # A2: conservar el motivo de cada capa en la auditoría
                rec["reason"] = reason
            out[str(name)] = rec
    return out
