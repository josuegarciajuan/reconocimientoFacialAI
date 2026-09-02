#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Consolidación al nacer (Fase 5 / M6) — motor/consolidar_nacidos.py

Cuando el clasificador crea una persona NUEVA (verdict new/uncertain/review),
la deja en una cola "pendiente de consolidación". Un disparador (primero que
ocurra) la compara contra las personas existentes usando la galería YA multi-
pose:

  - si el parecido es SÓLIDO (max coseno mutuo >= consolidate_min_cos y margen
    top1-top2 >= consolidate_min_margin) -> FUSIONA con snapshot reversible;
  - si tras `pending_max_attempts` intentos (o plazo duro) NO hay coincidencia
    sólida -> CONFIRMA la persona como nueva definitiva (nunca queda colgando).

Por qué acierta aquí y no en vivo: en vivo la persona recién nacida tenía 1-2
plantillas de una sola pose (el coseno con una vista en pose espejo era ~0.34);
con varias poses acumuladas la misma persona da >=0.50, claramente por encima
del peor impostor limpio (0.456) y de pares reales distintos (0.43).

Uso:
    motor/venv/bin/python motor/consolidar_nacidos.py <local> [--ruta .] [--once]
    # o integrado en el bucle del clasificador (llamada periódica a run_once)
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time

import numpy as np
from filelock import FileLock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.config import Config                    # noqa: E402
from motor.core.store import FaceStore                  # noqa: E402
from motor.core.matching import best_cosine_robust      # noqa: E402


# ---------------------------------------------------------------------------
# cola pendiente (append-only bajo lock)
# ---------------------------------------------------------------------------

def _queue_path(ruta: str, local_id: str) -> str:
    return os.path.join(ruta, "motor/pending", str(local_id), "pending.jsonl")


def _read_raw(ruta: str, local_id: str) -> list[dict]:
    p = _queue_path(ruta, local_id)
    if not os.path.exists(p):
        return []
    try:
        with open(p, encoding="utf-8") as fh:
            lines = [ln for ln in fh.read().splitlines() if ln.strip()]
    except OSError:
        return []
    out = []
    for ln in lines:
        try:
            e = json.loads(ln)
        except json.JSONDecodeError:
            continue
        out.append(e)
    return out


def _read_queue(ruta: str, local_id: str) -> list[dict]:
    p = _queue_path(ruta, local_id)
    with FileLock(p + ".lock"):
        return _read_raw(ruta, local_id)


def _write_queue(ruta: str, local_id: str, entries: list[dict]) -> None:
    p = _queue_path(ruta, local_id)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with FileLock(p + ".lock"):
        with open(p, "w", encoding="utf-8") as fh:
            for e in entries:
                fh.write(json.dumps(e) + "\n")


def enqueue(ruta: str, local_id: str, cod: str, pose: str | None = None) -> None:
    """Marca una persona recién creada como pendiente de consolidación."""
    p = _queue_path(ruta, local_id)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    now = time.time()
    with FileLock(p + ".lock"):
        entries = _read_raw(ruta, local_id)
        if any(e.get("cod") == cod for e in entries):
            return
        entries.append({"cod": cod, "ts": now, "attempts": 0,
                        "pose": pose, "created": now})
        with open(p, "w", encoding="utf-8") as fh:
            for e in entries:
                fh.write(json.dumps(e) + "\n")


# ---------------------------------------------------------------------------
# decisión pura (testeable sin BD)
# ---------------------------------------------------------------------------

def choose_merge_candidate(store: FaceStore, cfg: Config, cod: str,
                           exclude: set[str] | None = None,
                           k: int = 5) -> str | None:
    """Mejor persona con la que fusionar `cod` (o None).

    Criterio (galerías ricas, Fase 5):
      - mejor coseno mutuo >= cfg.consolidate_min_cos
      - el 2º mejor candidato queda a >= cfg.consolidate_min_margin del 1º
      - además la media robusta top-k del par supera consolidate_min_cos - 0.05
        (evita depender de un único encoding puente).
    Excluye a otras personas también pendientes salvo cuando no quede otra
    opción: el nacido más antiguo es el destino natural de un nacido gemelo.
    """
    enc = store.person_encodings(cod)
    if enc is None or len(enc) == 0:
        return None
    exclude = exclude or set()
    ranked: list[tuple[float, str]] = []
    for other in store.persons():
        if other == cod or other in exclude:
            continue
        g = store.person_encodings(other)
        if g is None or len(g) == 0:
            continue
        mx = float(np.max(enc @ g.T))
        r = best_cosine_robust(enc[0], g, k=k)
        ranked.append((mx, r, other))
    if not ranked:
        return None
    ranked.sort(key=lambda t: -t[0])
    best_max, best_rob, best_cod = ranked[0]
    if best_max < cfg.consolidate_min_cos:
        return None
    if len(ranked) > 1 and (best_max - ranked[1][0]) < cfg.consolidate_min_margin:
        return None
    if best_rob < cfg.consolidate_min_cos - 0.05:
        return None
    return best_cod


def _distinct_poses(store: FaceStore, cod: str) -> int:
    p = store.person(cod)
    if not p:
        return 0
    return len({po for po in p.get("poses", []) if po})


# ---------------------------------------------------------------------------
# worker
# ---------------------------------------------------------------------------

def run_once(ruta: str, local_id: str, cfg: Config, store: FaceStore,
             log=print) -> int:
    """Procesa la cola de pendientes: fusiona o confirma/descarta candidatos.

    Devuelve el nº de operaciones (merges + confirmaciones). No bloquea: si
    una entrada no está lista aún, se deja para la siguiente pasada.
    """
    entries = _read_queue(ruta, local_id)
    if not entries:
        return 0
    now = time.time()
    pending_cods = {e["cod"] for e in entries}
    done = 0
    for e in entries:
        cod = e["cod"]
        age = now - float(e.get("ts", now))
        attempts = int(e.get("attempts", 0))
        poses = _distinct_poses(store, cod)
        ready = (poses >= cfg.pending_min_poses
                 or age >= cfg.pending_max_wait_s
                 or attempts >= cfg.pending_max_attempts
                 or age >= cfg.pending_hard_deadline_s)
        if not ready:
            continue
        # intento de fusión (solo contra personas NO pendientes; si no queda
        # otra, permite pendiente-pendiente, destino = la más antigua)
        other_pending = {c for c in pending_cods if c != cod}
        cand = choose_merge_candidate(store, cfg, cod, exclude=other_pending)
        if cand is None:
            e["attempts"] = attempts + 1
            if attempts + 1 > cfg.pending_max_attempts or age >= cfg.pending_hard_deadline_s:
                log(f"[consolidar] {cod} confirmada como persona NUEVA definitiva "
                    f"(intentos={attempts + 1}, poses={poses})")
                done += 1
            continue
        # --- fusión (con snapshot del store para reversibilidad) ---
        dst = cand
        from motor.core.backup import new_backup_dir  # noqa: E402
        out_dir = new_backup_dir(ruta, "consolidar")
        store.save_snapshot_bytes(os.path.join(out_dir, "face_enc_v2.bak"))
        merged = store.merge_undoable(dst, cod)
        _merge_folders(ruta, local_id, cod, dst)
        _merge_bd(ruta, cod, dst)
        with open(os.path.join(out_dir, "journal.jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps({
                "ts": time.time(), "op": "merge_nacido",
                "src": cod, "dst": dst,
                "encodings_moved": merged.get("encodings_moved", 0),
                "snapshot": "face_enc_v2.bak"}) + "\n")
        log(f"[consolidar] {cod} FUSIONADA en {dst} "
            f"({merged.get('encodings_moved', 0)} encodings)")
        done += 1
    # guardar cola (entradas listas ya procesadas se eliminan en la escritura)
    remaining = []
    for e in entries:
        cod = e["cod"]
        # si fue fusionada desapareció del store; si fue confirmada/descartada,
        # intentos>max => fuera de la cola
        p = store.person(cod)
        age = now - float(e.get("ts", now))
        attempts = int(e.get("attempts", 0))
        if p is None or attempts > cfg.pending_max_attempts or age >= cfg.pending_hard_deadline_s:
            continue
        remaining.append(e)
    _write_queue(ruta, local_id, remaining)
    return done


def _merge_folders(ruta: str, local_id: str, src_cod: str, dst_cod: str) -> None:
    """Mueve fotos de display y retratos de src a dst."""
    base = os.path.join(ruta, "motor/caras", str(local_id))
    if os.path.isdir(base):
        for cam in os.listdir(base):
            sdir = os.path.join(base, cam, src_cod)
            ddir = os.path.join(base, cam, dst_cod)
            if os.path.isdir(sdir):
                os.makedirs(ddir, exist_ok=True)
                for f in os.listdir(sdir):
                    try:
                        shutil.move(os.path.join(sdir, f), os.path.join(ddir, f))
                    except OSError:
                        pass
                try:
                    os.rmdir(sdir)
                except OSError:
                    pass
    portraits_src = os.path.join(ruta, "motor/portraits", str(local_id), src_cod)
    portraits_dst = os.path.join(ruta, "motor/portraits", str(local_id), dst_cod)
    if os.path.isdir(portraits_src):
        os.makedirs(portraits_dst, exist_ok=True)
        for f in os.listdir(portraits_src):
            try:
                shutil.move(os.path.join(portraits_src, f), os.path.join(portraits_dst, f))
            except OSError:
                pass
        try:
            os.rmdir(portraits_src)
        except OSError:
            pass


def _mysql(ruta: str, sql: str) -> list[str]:
    from motor.core.photos import _mysql as _m  # noqa: E402
    return _m(ruta, sql)


def _merge_bd(ruta: str, src_cod: str, dst_cod: str) -> None:
    """Reasigna estancias de src a dst y borra la fila de personas de src."""
    try:
        rows = _mysql(ruta, f"SELECT id FROM personas WHERE cod_interno='{dst_cod}'")
        if not rows:
            return
        dst_pid = rows[0]
        _mysql(ruta, f"UPDATE estancias SET persona_id={dst_pid} "
                     f"WHERE persona_id IN (SELECT id FROM personas WHERE cod_interno='{src_cod}')")
        _mysql(ruta, f"DELETE FROM personas WHERE cod_interno='{src_cod}'")
    except Exception as e:  # noqa: BLE001
        print(f"[consolidar] aviso BD al fusionar {src_cod}->{dst_cod}: {e}", flush=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("local_id")
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    args = ap.parse_args()
    cfg = Config.from_env(args.ruta)
    store = FaceStore(os.path.join(args.ruta, "motor/bbdd_reconocimiento",
                                   args.local_id, "face_enc_v2"),
                      max_per_person=cfg.max_encodings_per_person)
    n = run_once(args.ruta, args.local_id, cfg, store)
    print(f"[consolidar] {n} operacion(es)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
