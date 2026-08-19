"""Diccionario de identidad `face_enc_v2` — persistencia segura y concurrente.

Formato (pickle):
    {"version": 3, "schema": "face_enc_v2",
     "persons": {
        <cod_interno>: {
            "encodings": [ndarray(512,) ...],
            "quality":   [float ...],       # sharpness en el momento de enrolar
            "poses":     [str ...],         # etiqueta de pose
            "added_at":  [float ...],       # timestamp
            "appearance": {                 # opcional (capa L1b, F1+)
                "desc": [ [float...] ],     # descriptores de torso (144-d)
                "ts":   [float ...],        # epoch de captura
                "src":  [str ...],          # path del crop (traza)
            },
        }
     }}

Reglas:
- Lectura atómica vía os.replace (write-temp-then-rename) bajo FileLock.
- Mutaciones con bloqueo de TODO el read-modify-write (evita pérdidas entre procesos).
- Formato legado/desconocido NO se migra (re-enrolado desde cero, decisión de Fase 0).
- F6: snapshot()/merge_undoable()/restore_person() habilitan la reversibilidad
  (snapshot + journal + rollback) de fusiones y backfills.
"""
from __future__ import annotations

import os
import pickle
import time
from typing import Callable

import numpy as np
from filelock import FileLock

VERSION = 3
SCHEMA = "face_enc_v2"

# F1.4: umbral de similitud media para considerar un encoding "outlier" dentro
# de una persona (los genuinos de videovigilancia promedian >= 0.32).
OUTLIER_COSINE = 0.25


def _empty() -> dict:
    return {"version": VERSION, "schema": SCHEMA, "persons": {}}


def _new_person() -> dict:
    return {"encodings": [], "quality": [], "poses": [], "added_at": [], "appearance": None}


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
        # F1.4 (refinamiento autoaprendizaje): con volumen suficiente, descartar
        # ANTES outliers estructurales — encodings cuya similitud media con el
        # resto es < OUTLIER_COSINE. Son típicamente impostores añadidos por
        # contaminación histórica (perfiles mezclados); los genuinos (coseno
        # interno >= 0.32) no se ven afectados. Nunca se vacía a la persona.
        n = len(p["encodings"])
        if n >= 8:
            encs = np.stack(p["encodings"])
            S = encs @ encs.T
            mean_sim = (S.sum(axis=1) - 1.0) / np.maximum(1, n - 1)
            keep = np.where(mean_sim >= OUTLIER_COSINE)[0]
            if 0 < len(keep) < n:
                for k in ("encodings", "quality", "poses", "added_at"):
                    p[k] = [p[k][i] for i in keep]
                if p.get("appearance"):
                    n_app = len(p["appearance"]["desc"])
                    if n_app:
                        keep_app = [i for i in keep if i < n_app]
                        for k in ("desc", "ts", "src"):
                            p["appearance"][k] = [p["appearance"][k][i] for i in keep_app]
                n = len(p["encodings"])

        # si sigue sobrando: conservar los más nítidos (comportamiento previo)
        if n > max_per_person:
            idx = sorted(range(n), key=lambda i: p["quality"][i], reverse=True)[:max_per_person]
            for k in ("encodings", "quality", "poses", "added_at"):
                p[k] = [p[k][i] for i in idx]
            if p.get("appearance"):
                # apariencia alineada por índice (mismo crop); puede tener menos filas
                n_app = len(p["appearance"]["desc"])
                if n_app:
                    keep = [i for i in idx if i < n_app]
                    for k in ("desc", "ts", "src"):
                        p["appearance"][k] = [p["appearance"][k][i] for i in keep]

    def add(self, cod: str, encodings: list[np.ndarray],
            qualities: list[float], poses: list[str]) -> None:
        def _fn(data: dict) -> None:
            p = data["persons"].setdefault(cod, _new_person())
            now = time.time()
            for e, q, po in zip(encodings, qualities, poses):
                p["encodings"].append(np.asarray(e, dtype=np.float32))
                p["quality"].append(float(q))
                p["poses"].append(po)
                p["added_at"].append(now)
            self._prune(p, self.max_per_person)
        self._transaction(_fn)

    def add_appearance(self, cod: str, desc: np.ndarray, ts: float | None = None,
                       src: str = "") -> None:
        """Añade un descriptor de torso/ropa a la persona (capa L1b)."""
        def _fn(data: dict) -> None:
            p = data["persons"].setdefault(cod, _new_person())
            if p.get("appearance") is None:
                p["appearance"] = {"desc": [], "ts": [], "src": []}
            p["appearance"]["desc"].append(np.asarray(desc, dtype=np.float32))
            p["appearance"]["ts"].append(float(ts if ts is not None else time.time()))
            p["appearance"]["src"].append(src)
        self._transaction(_fn)

    def person_appearance(self, cod: str) -> dict | None:
        """Devuelve la galería de apariencia de la persona ({desc, ts, src}) o None."""
        p = self.person(cod)
        if not p or not p.get("appearance"):
            return None
        return p["appearance"]

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
            pa = data["persons"].setdefault(a, _new_person())
            pb = data["persons"].pop(b, None)
            if pb is not None:
                for k in ("encodings", "quality", "poses", "added_at"):
                    pa[k] = pa[k] + pb[k]
                if pb.get("appearance"):
                    if pa.get("appearance") is None:
                        pa["appearance"] = {"desc": [], "ts": [], "src": []}
                    for k in ("desc", "ts", "src"):
                        pa["appearance"][k] = pa["appearance"][k] + pb["appearance"][k]
                self._prune(pa, self.max_per_person)
        self._transaction(_fn)

    # --- F6: reversibilidad (snapshot + journal + rollback) ---

    def snapshot(self) -> dict:
        """Copia profunda de TODO el diccionario (para backups pre-merge)."""
        with FileLock(self.path + ".lock"):
            return pickle.loads(pickle.dumps(self._read_raw()))

    def merge_undoable(self, a: str, b: str) -> dict:
        """Fusiona `b` en `a` (como merge()) y devuelve un journal de la operación.

        El journal contiene lo necesario para el rollback: persona fuente, persona
        destino, nº de encodings movidos y la copia exacta de la persona fuente.
        El llamador debe persistir el snapshot y el journal (F6).
        """
        with FileLock(self.path + ".lock"):
            data = self._read_raw()
            src_person = pickle.loads(pickle.dumps(data["persons"].get(b)))
            pa = data["persons"].setdefault(a, _new_person())
            pb = data["persons"].pop(b, None)
            if pb is not None:
                for k in ("encodings", "quality", "poses", "added_at"):
                    pa[k] = pa[k] + pb[k]
                if pb.get("appearance"):
                    if pa.get("appearance") is None:
                        pa["appearance"] = {"desc": [], "ts": [], "src": []}
                    for k in ("desc", "ts", "src"):
                        pa["appearance"][k] = pa["appearance"][k] + pb["appearance"][k]
                self._prune(pa, self.max_per_person)
            self._write(data)
        moved = 0
        if src_person:
            moved = len(src_person.get("encodings", []))
        return {
            "op": "merge", "src": b, "dst": a,
            "encodings_moved": moved,
            "src_person": src_person,       # copia exacta de la persona fuente
            "ts": time.time(),
        }

    def restore_person(self, cod: str, person: dict | None) -> None:
        """Re-inyecta una persona completa (rollback de merge/limpiar)."""
        def _fn(data: dict) -> None:
            if person is None:
                data["persons"].pop(cod, None)
            else:
                data["persons"][cod] = pickle.loads(pickle.dumps(person))
        self._transaction(_fn)

    def save_snapshot_bytes(self, out_path: str) -> None:
        """Persiste el snapshot del diccionario a un fichero pickle (backup)."""
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, "wb") as fh:
            pickle.dump(self.snapshot(), fh)

    def load_snapshot_bytes(self, path: str) -> dict:
        with open(path, "rb") as fh:
            return pickle.load(fh)

    def reembed_person(self, cod: str, encodings: list[np.ndarray],
                       qualities: list[float], poses: list[str]) -> None:
        """Sustituye los encodings de `cod` por los recalculados (backfill SR-before-embedding).

        Conserva `appearance` (capa L1b) tal cual; solo se reemplazan las listas
        de cara (encodings/quality/poses/added_at) para que query y galería
        queden en el mismo dominio (embeddings SR para caras pequeñas).
        """
        def _fn(data: dict) -> None:
            p = data["persons"].get(cod)
            if not p:
                return
            if not encodings:
                return
            now = time.time()
            p["encodings"] = [np.asarray(e, dtype=np.float32) for e in encodings]
            p["quality"] = [float(q) for q in qualities]
            p["poses"] = list(poses)
            p["added_at"] = [now] * len(encodings)
            self._prune(p, self.max_per_person)
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
