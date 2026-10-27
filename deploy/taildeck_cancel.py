#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Cancelación project-scoped de trabajos en el control plane de SuperServer.

Se ejecuta SIEMPRE en el nodo del control plane (loopback + X-Panel-Gate).
La casa puede invocarlo por SSH mediante `deploy/td_cancel.sh`.

Garantías:
  - Solo actúa sobre jobs cuyo `project` coincide exactamente.
  - No para `taildeck.service`, ni toca otros proyectos.
  - Con `--purge-returns`, borra únicamente retornos de ESTE proyecto.
  - `--dry-run` no modifica nada.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = os.environ.get("RF_SUPERSERVER_API", "http://127.0.0.1:8110/superserver").rstrip("/")
RETURNS = Path(os.environ.get("RF_TAILDECK_RETURNS", "/var/lib/taildeck/returns"))
ACTIVE = {"queued", "preparing", "running", "collecting", "cancelling"}


def die(msg: str, code: int = 2) -> "NoReturn":
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def req(method: str, path: str, *, csrf: str | None = None, timeout: int = 180) -> dict:
    headers = {"X-Panel-Gate": "1"}
    if csrf:
        headers["X-CSRF-Token"] = csrf
    r = urllib.request.Request(API + path, headers=headers, method=method)
    with urllib.request.urlopen(r, timeout=timeout) as fh:
        return json.loads(fh.read().decode() or "{}")


def purge_returns(project: str, active_ids: set[str], dry_run: bool) -> tuple[int, int]:
    """Borra retornos del proyecto. Devuelve (dirs, bytes)."""
    if not RETURNS.is_dir():
        return 0, 0
    dirs = 0
    freed = 0
    # 1) Directorio project-scoped (entrega a la casa).
    proj_dir = RETURNS / project
    candidates = []
    if proj_dir.is_dir():
        candidates.append(proj_dir)
    # 2) Directorios planos <job-id>/ con resultMeta.json del proyecto.
    for child in RETURNS.iterdir():
        if not child.is_dir() or child == proj_dir:
            continue
        meta = child / "resultMeta.json"
        if not meta.is_file():
            continue
        try:
            obj = json.loads(meta.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if obj.get("project") == project:
            candidates.append(child)
    for path in candidates:
        # Seguridad: hijo directo de RETURNS, nunca la raíz.
        if path.parent != RETURNS or path.name in ("", ".", ".."):
            continue
        if path.name in active_ids:
            continue
        for root, _dirs, files in os.walk(path):
            for f in files:
                try:
                    freed += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
        if dry_run:
            print(f"  (dry-run) borraría {path}")
        else:
            shutil.rmtree(path, ignore_errors=False)
            print(f"  borrado {path}")
        dirs += 1
    return dirs, freed


def main() -> int:
    args = [a for a in sys.argv[1:]]
    dry_run = "--dry-run" in args
    purge = "--purge-returns" in args
    positional = [a for a in args if not a.startswith("-")]
    if len(positional) != 1:
        die("uso: taildeck_cancel.py <proyecto> [--dry-run] [--purge-returns]", 2)
    project = positional[0].strip()
    if not project:
        die("proyecto vacío; abortado para no tocar otra instancia", 2)

    try:
        auth = req("GET", "/api/auth", timeout=10)
        csrf = auth["csrf"]
        state = req("GET", "/api/state", csrf=csrf, timeout=30)
    except (urllib.error.URLError, OSError, KeyError, json.JSONDecodeError) as exc:
        die(f"control plane no accesible en {API}: {exc}", 3)

    jobs = [j for j in state.get("pool", [])
            if j.get("project") == project and j.get("status") in ACTIVE]
    print(f"[taildeck-cancel] proyecto={project} activos={len(jobs)} dry_run={int(dry_run)}")
    errors = 0
    for j in jobs:
        jid = str(j.get("id") or "")
        if not jid:
            continue
        if dry_run:
            print(f"  (dry-run) cancelaría {jid} {j.get('process')} {j.get('status')} node={j.get('node')}")
            continue
        try:
            out = req("POST", f"/api/pool/{jid}/cancel", csrf=csrf, timeout=180)
            st = (out.get("process") or {}).get("status", "?")
            print(f"  {jid} {j.get('process')} {j.get('status')} -> {st}")
        except Exception as exc:  # noqa: BLE001
            errors += 1
            print(f"  {jid} ERROR: {exc}", file=sys.stderr)

    state2 = state if dry_run else req("GET", "/api/state", csrf=csrf, timeout=30)
    rest = [j for j in state2.get("pool", [])
            if j.get("project") == project and j.get("status") in ACTIVE]
    for j in rest:
        print(f"  PENDIENTE {j.get('id')} {j.get('process')} {j.get('status')} node={j.get('node')}")
    active_ids = {str(j.get("id")) for j in rest}

    if purge:
        n, freed = purge_returns(project, active_ids, dry_run)
        print(f"[taildeck-cancel] retornos borrados={n} bytes={freed}")
    print(f"[taildeck-cancel] restantes={len(rest)} errores={errors}")
    return 0 if not rest and not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
