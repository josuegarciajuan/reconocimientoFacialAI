"""Recolector de feedback etiquetado (F3, §5) — verdad = ACCIONES DEL PANEL.

- "Unir personas" (juntar_personas_v2.py)  => par GENUINO.
- "mover foto entre personas" (cambiar_foto.py) => par IMPOSTOR (la foto NO era
  de la persona origen).

El clasificador registra cada decisión con sus features por capa y un HASH del
embedding del query (privacidad: nunca fotos en el log). Las acciones del panel
emiten etiquetas que se casan con esas decisiones:

  decisions.jsonl : {ts, local, cam, verdict, person, top1, top2, best, second,
                     layers:{capa:{s,c}}, query_hash}
  labels.jsonl    : {type: merge|move, ts, a, b} / {type: move, ts, emb_hash, origen}

export_matrix() une ambos y produce (features, label) para la calibración diaria.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

import numpy as np
from filelock import FileLock

from .calibration import FEATURE_NAMES


def embedding_hash(emb: np.ndarray) -> str:
    """Hash del embedding (bytes float32) — identificador sin datos personales."""
    return hashlib.sha256(np.asarray(emb, dtype=np.float32).tobytes()).hexdigest()


def _ls_pair(v) -> tuple[float, float]:
    """(score, confidence) de un LayerScore O de un dict {"s":..,"c":..}.

    El clasificador pasa `result.layer_scores` (valores LayerScore); los tests
    y el formato persistido usan dicts. Sin esto, log_decision crasheaba con
    LayerScore (bug latente: antes layers siempre era {} y nunca se recorría).
    """
    if isinstance(v, dict):
        return float(v.get("score", 0.0)), float(v.get("confidence", 0.0))
    return float(getattr(v, "score", 0.0)), float(getattr(v, "confidence", 0.0))


def _ls_record(v) -> dict:
    """Representación de una capa que conserva disponibilidad y diagnóstico."""
    s, c = _ls_pair(v)
    if isinstance(v, dict):
        available = bool(v.get("available", True))
        reason = str(v.get("reason", ""))
    else:
        available = bool(getattr(v, "available", True))
        reason = str(getattr(v, "reason", ""))
    return {"s": s, "c": c, "available": available, "reason": reason}


class FeedbackCollector:
    def __init__(self, ruta: str, local_id: str, enabled: bool = True):
        self.dir = os.path.join(ruta, "motor/feedback", str(local_id))
        self.enabled = enabled
        self.decisions_path = os.path.join(self.dir, "decisions.jsonl")
        self.labels_path = os.path.join(self.dir, "labels.jsonl")

    def _lock(self, path: str):
        return FileLock(path + ".lock")

    def _append(self, path: str, obj: dict) -> None:
        if not self.enabled:
            return
        os.makedirs(self.dir, exist_ok=True)
        with self._lock(path):
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(obj, default=float) + "\n")

    def log_decision(self, entry: dict) -> None:
        """Registra una decisión de clasificación con features por capa."""
        e = {
            "ts": time.time(),
            "local": entry.get("local"),
            "cam": entry.get("cam"),
            "verdict": entry.get("verdict"),
            "person": entry.get("person"),
            "top1": entry.get("top1"),
            "top2": entry.get("top2"),
            "best": entry.get("best"),
            "second": entry.get("second"),
            "layers": {k: _ls_record(v)
                       for k, v in (entry.get("layers") or {}).items()},
            "query_hash": entry.get("query_hash"),
            "stem": entry.get("stem"),
            # F4: situación del query para calibración condicionada a la pose.
            "situation": {
                "pose": entry.get("pose"),
                "yaw": entry.get("yaw"),
                "pitch": entry.get("pitch"),
                "sharpness": float(entry.get("sharpness", 0.0) or 0.0),
                "has_face": bool(entry.get("has_face", True)),
            },
        }
        # A1 (2026-09-02): trazabilidad completa para replay/validación.
        for k in ("foto_id", "exact_match", "exact_conflict", "branch",
                  "top_scores", "cfg"):
            if k in entry:
                e[k] = entry[k]
        self._append(self.decisions_path, e)

    def label_merge(self, cod_a: str, cod_b: str) -> None:
        """Panel 'Unir': las personas a y b son la misma identidad (par genuino)."""
        self._append(self.labels_path, {"type": "merge", "ts": time.time(),
                                        "a": cod_a, "b": cod_b})

    def label_move(self, emb_hash: str, cod_origen: str) -> None:
        """Panel 'mover foto': el embedding movido NO era de cod_origen (impostor)."""
        self._append(self.labels_path, {"type": "move", "ts": time.time(),
                                        "emb_hash": emb_hash, "origen": cod_origen})

    # --- exportación para calibración ---

    def _read_jsonl(self, path: str) -> list[dict]:
        if not os.path.exists(path):
            return []
        out = []
        with self._lock(path):
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            out.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        return out

    def export_matrix(self) -> tuple[np.ndarray, np.ndarray]:
        """(X, y) para la calibración: features por capa + etiqueta humana.

        Retro-compatible: ver export_matrix_with_situations para la variante
        con la situación (pose) de cada decisión.
        """
        X, y, _ = self.export_matrix_with_situations()
        return X, y

    def export_matrix_with_situations(self) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """(X, y, situ): features + etiqueta + clase de situación de cada fila.

        Regla de etiquetado:
          + merge(a, b): decisiones cuyo candidato final (person/top1) pertenece
            a {a, b} y el otro de {a, b} estaba en top1/top2 -> el par era
            GENUINO (el clasificador los separó mal).
          + move(emb_hash, origen): decisiones con ese query_hash cuyo person
            era `origen` -> la asignación era IMPOSTOR.
        """
        decisions = self._read_jsonl(self.decisions_path)
        labels = self._read_jsonl(self.labels_path)
        if not decisions or not labels:
            return (np.zeros((0, len(FEATURE_NAMES))), np.zeros(0, dtype=np.int64), [])

        merge_sets: list[set[str]] = []
        impostors: set[str] = set()
        for lab in labels:
            if lab["type"] == "merge":
                merge_sets.append({lab["a"], lab["b"]})
            elif lab["type"] == "move":
                impostors.add(lab["emb_hash"])

        X: list[list[float]] = []
        y: list[int] = []
        situ: list[str] = []
        for d in decisions:
            feats = _features(d)
            if feats is None:
                continue
            person, top1, top2 = d.get("person"), d.get("top1"), d.get("top2")
            label: int | None = None
            # genuino: la decisión separó dos personas que el panel unió
            for s in merge_sets:
                if person in s and (top1 in s or top2 in s) and person is not None \
                        and (top1 != person or top2 != person):
                    label = 1
                    break
            if label is None and d.get("query_hash") in impostors and person is not None:
                label = 0                       # impostor de la persona asignada
            if label is not None:
                X.append(feats)
                y.append(label)
                sit = (d.get("situation") or {})
                situ.append(sit.get("pose") or "otro")
        return np.asarray(X, dtype=np.float64), np.asarray(y, dtype=np.int64), situ


def _features(d: dict) -> list[float] | None:
    layers = d.get("layers") or {}
    if not layers:
        return None
    # vector fijo: s_cara, c_cara, s_torso, c_torso, s_zona, c_zona, s_vlm, c_vlm, s_openai, c_openai
    order = [("cara", "s"), ("cara", "c"), ("torso", "s"), ("torso", "c"),
             ("zona", "s"), ("zona", "c"), ("vlm", "s"), ("vlm", "c"),
             ("openai", "s"), ("openai", "c")]
    feats = []
    for layer, kind in order:
        lv = layers.get(layer) or {}
        feats.append(float(lv.get(kind, 0.0)))
    return feats
