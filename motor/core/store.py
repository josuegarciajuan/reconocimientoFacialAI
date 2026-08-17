"""Diccionario de identidad `face_enc_v2` — persistencia segura y concurrente.

Formato (pickle):
    {"version": 2, "schema": "face_enc_v2",
     "persons": {
        <cod_interno>: {
            "encodings": [ndarray(512,) ...],
            "quality":   [float ...],       # sharpness en el momento de enrolar
            "poses":     [str ...],         # etiqueta de pose
            "added_at":  [float ...],       # timestamp
        }
     }}

Reglas:
- Lectura atómica vía os.replace (write-temp-then-rename) bajo FileLock.
- Mutaciones con bloqueo de TODO el read-modify-write (evita pérdidas entre procesos).
- Formato legado/desconocido NO se migra (re-enrolado desde cero, decisión de Fase 0).
"""
from __future__ import annotations

import os
import pickle
import time
from typing import Callable

import numpy as np
from filelock import FileLock

VERSION = 2
SCHEMA = "face_enc_v2"


def _empty() -> dict:
    return {"version": VERSION, "schema": SCHEMA, "persons": {}}


class FaceStore:
    def __init__(self, path: str, max_per_person: int = 500):
        self.path = path
        self.max_per_person = max_per_person

    # --- I/O de bajo nivel ---

    def _read_raw(self) -> dict:
        if not os.path.exists(self.path):
            return _empty()
        try:
            with open(self.path, "rb") as fh:
                data = pickle.load(fh)
        except Exception:
            return _empty()
        if not isinstance(data, dict) or data.get("schema") != SCHEMA:
            return _empty()
        return data

    def _write(self, data: dict) -> None:
        tmp = self.path + ".tmp"
        with open(tmp, "wb") as fh:
            pickle.dump(data, fh)
        os.replace(tmp, self.path)

    def _transaction(self, fn: Callable[[dict], None]) -> None:
        with FileLock(self.path + ".lock"):
            data = self._read_raw()
            fn(data)
            self._write(data)

    # --- consultas (solo lectura) ---

    def persons(self) -> list[str]:
        return list(self._read_raw()["persons"].keys())

    def person(self, cod: str) -> dict | None:
        return self._read_raw()["persons"].get(cod)

    def person_encodings(self, cod: str) -> np.ndarray | None:
        p = self.person(cod)
        if not p or not p.get("encodings"):
            return None
        return np.asarray(p["encodings"], dtype=np.float32)

    def count(self, cod: str) -> int:
        p = self.person(cod)
        return len(p["encodings"]) if p else 0

    # --- mutaciones ---

    @staticmethod
    def _prune(p: dict, max_per_person: int) -> None:
        if len(p["encodings"]) > max_per_person:
            idx = sorted(range(len(p["quality"])), key=lambda i: p["quality"][i], reverse=True)[:max_per_person]
            for k in ("encodings", "quality", "poses", "added_at"):
                p[k] = [p[k][i] for i in idx]

    def add(self, cod: str, encodings: list[np.ndarray],
            qualities: list[float], poses: list[str]) -> None:
        def _fn(data: dict) -> None:
            p = data["persons"].setdefault(cod, {"encodings": [], "quality": [], "poses": [], "added_at": []})
            now = time.time()
            for e, q, po in zip(encodings, qualities, poses):
                p["encodings"].append(np.asarray(e, dtype=np.float32))
                p["quality"].append(float(q))
                p["poses"].append(po)
                p["added_at"].append(now)
            self._prune(p, self.max_per_person)
        self._transaction(_fn)

    def remove(self, cod: str) -> None:
        def _fn(data: dict) -> None:
            data["persons"].pop(cod, None)
        self._transaction(_fn)

    def rename(self, cod: str, new_cod: str) -> None:
        def _fn(data: dict) -> None:
            if cod in data["persons"] and new_cod not in data["persons"]:
                data["persons"][new_cod] = data["persons"].pop(cod)
        self._transaction(_fn)

    def merge(self, a: str, b: str) -> None:
        """Mueve todas las caras de `b` a `a` y elimina `b` (juntar personas)."""
        def _fn(data: dict) -> None:
            pa = data["persons"].setdefault(a, {"encodings": [], "quality": [], "poses": [], "added_at": []})
            pb = data["persons"].pop(b, None)
            if pb is not None:
                for k in ("encodings", "quality", "poses", "added_at"):
                    pa[k] = pa[k] + pb[k]
                self._prune(pa, self.max_per_person)
        self._transaction(_fn)

    def remove_closest(self, cod: str, embedding: np.ndarray, min_cosine: float = 0.5) -> int:
        """Elimina de `cod` el encoding más parecido a `embedding` (si supera min_cosine).
        Devuelve 1 si eliminó algo (B4: mover foto entre personas)."""
        removed = [0]

        def _fn(data: dict) -> None:
            p = data["persons"].get(cod)
            if not p or not p["encodings"]:
                return
            encs = np.asarray(p["encodings"], dtype=np.float32)
            sims = encs @ np.asarray(embedding, dtype=np.float32)
            idx = int(np.argmax(sims))
            if float(sims[idx]) >= min_cosine:
                for k in ("encodings", "quality", "poses", "added_at"):
                    p[k].pop(idx)
                removed[0] = 1

        self._transaction(_fn)
        return removed[0]
