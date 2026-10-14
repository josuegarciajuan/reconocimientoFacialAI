#!/usr/bin/env python3
"""Retención segura de snapshots de consolidación (F15).

Por defecto solo informa. La eliminación exige ``--apply --confirm`` y queda
limitada a ``motor/backups/YYYYMMDD_HHMMSS_consolidar``.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import shutil

PATTERN = re.compile(r"^(\d{8})_(\d{6})_consolidar$")

# Spool del pool (Superserver). Los bridges ESCANEAN `returns/` para casar cada
# resultado y ese directorio crecía sin límite (10k dirs / 1,2 GB en producción),
# ralentizando todos los bridges. Aquí se le aplica la misma retención diaria.
RETURNS_DIR = "/var/lib/taildeck/returns/reconocimientoFacial"
PROCESSED_DIR = "/var/lib/taildeck/spool/processed"


def inventory(root: str) -> list[dict]:
    root = os.path.realpath(root)
    out = []
    for name in os.listdir(root):
        path = os.path.realpath(os.path.join(root, name))
        match = PATTERN.fullmatch(name)
        if not match or not path.startswith(root + os.sep) or not os.path.isdir(path):
            continue
        stamp = dt.datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")
        size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(path) for f in fs)
        out.append({"name": name, "path": path, "ts": stamp, "size": size})
    return sorted(out, key=lambda x: x["ts"], reverse=True)


def select(items: list[dict], now: dt.datetime, keep_latest: int = 50,
           hourly_hours: int = 24, daily_days: int = 7, protect_hours: int = 2):
    keep = {x["path"] for x in items[:keep_latest]}
    keep.update(x["path"] for x in items if now - x["ts"] <= dt.timedelta(hours=protect_hours))
    hourly = {}
    daily = {}
    for item in items:
        age = now - item["ts"]
        if age <= dt.timedelta(hours=hourly_hours):
            hourly.setdefault(item["ts"].strftime("%Y%m%d%H"), item)
        if age <= dt.timedelta(days=daily_days):
            daily.setdefault(item["ts"].strftime("%Y%m%d"), item)
    keep.update(x["path"] for x in hourly.values())
    keep.update(x["path"] for x in daily.values())
    return [x for x in items if x["path"] in keep], [x for x in items if x["path"] not in keep]


# ---------------------------------------------------------------------------
# Retención del spool del pool (returns/ + processed/)
# ---------------------------------------------------------------------------

def inventory_pool(returns_dir: str | None = None,
                   processed_dir: str | None = None) -> list[dict]:
    """Inventario de `returns/<dir>` y `processed/<file>` con su mtime.

    Los directorios por defecto se leen en tiempo de llamada (no como defaults
    del def) para poder testear/overridear sin tocar rutas globales.
    """
    returns_dir = returns_dir if returns_dir is not None else RETURNS_DIR
    processed_dir = processed_dir if processed_dir is not None else PROCESSED_DIR
    items: list[dict] = []
    if os.path.isdir(returns_dir):
        rroot = os.path.realpath(returns_dir)
        for name in os.listdir(rroot):
            path = os.path.realpath(os.path.join(rroot, name))
            if not path.startswith(rroot + os.sep):
                continue
            try:
                st = os.stat(path)
            except OSError:
                continue
            kind = "dir" if os.path.isdir(path) else "file"
            items.append({"name": f"returns/{name}", "path": path,
                          "ts": dt.datetime.fromtimestamp(st.st_mtime), "kind": kind})
    if os.path.isdir(processed_dir):
        proot = os.path.realpath(processed_dir)
        for name in os.listdir(proot):
            path = os.path.realpath(os.path.join(proot, name))
            if not path.startswith(proot + os.sep):
                continue
            try:
                st = os.stat(path)
            except OSError:
                continue
            items.append({"name": f"processed/{name}", "path": path,
                          "ts": dt.datetime.fromtimestamp(st.st_mtime), "kind": "file"})
    return sorted(items, key=lambda x: x["ts"], reverse=True)


def select_pool(items: list[dict], now: dt.datetime,
                protect_hours: int = 2) -> tuple[list[dict], list[dict]]:
    """Separa (conservar, purgar) del spool: purga lo más antiguo que
    `protect_hours`. Se protege una ventana reciente para no borrar resultados
    todavía en vuelo (los bridges los leen segundos después de generarse)."""
    corte = now - dt.timedelta(hours=max(0, int(protect_hours)))
    keep = [x for x in items if x["ts"] >= corte]
    purge = [x for x in items if x["ts"] < corte]
    return keep, purge


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--pool-hours", type=int, default=24,
                    help="retención del spool del pool en horas (default 24)")
    ap.add_argument("--no-pool", action="store_true", help="no tocar el spool del pool")
    args = ap.parse_args()
    now = dt.datetime.now()
    size = lambda xs: sum(x["size"] for x in xs if "size" in x)

    if args.apply and not args.confirm:
        print("ERROR: --apply exige --confirm", flush=True)
        return 2

    # --- snapshots de consolidación (motor/backups) ---
    root = os.path.realpath(os.path.join(args.ruta, "motor/backups"))
    if not os.path.isdir(root):
        print(f"backups inexistente (se omite): {root}")
    else:
        items = inventory(root)
        keep, purge = select(items, now)
        print(f"backups root={root}")
        print(f"backups total={len(items)} keep={len(keep)} purge={len(purge)} "
              f"purge_bytes={size(purge)}")
        for x in purge:
            print(f"  candidate backup {x['name']} {x['size']}")
        if args.apply:
            for x in purge:
                path = os.path.realpath(x["path"])
                if not path.startswith(root + os.sep) or not PATTERN.fullmatch(os.path.basename(path)):
                    raise RuntimeError(f"ruta rechazada: {path}")
                shutil.rmtree(path)
                print(f"deleted backup {x['name']}")

    # --- spool del pool (returns/ + processed/) ---
    if not args.no_pool:
        pitems = inventory_pool()
        pkeep, ppurge = select_pool(pitems, now, protect_hours=args.pool_hours)
        pbytes = 0
        for x in ppurge:
            try:
                pbytes += os.path.getsize(x["path"]) if x["kind"] == "file" else 0
                if x["kind"] == "dir":
                    pbytes += sum(os.path.getsize(os.path.join(d, f))
                                  for d, _, fs in os.walk(x["path"]) for f in fs)
            except OSError:
                pass
        print(f"pool total={len(pitems)} keep={len(pkeep)} purge={len(ppurge)} "
              f"purge_bytes={pbytes} (protege {args.pool_hours}h)")
        for x in ppurge[:20]:
            print(f"  candidate pool {x['name']}")
        if len(ppurge) > 20:
            print(f"  ... y {len(ppurge) - 20} más")
        if args.apply:
            n = 0
            for x in ppurge:
                path = os.path.realpath(x["path"])
                if not (path.startswith(os.path.realpath(RETURNS_DIR) + os.sep)
                        or path.startswith(os.path.realpath(PROCESSED_DIR) + os.sep)):
                    raise RuntimeError(f"ruta de pool rechazada: {path}")
                try:
                    if x["kind"] == "dir":
                        shutil.rmtree(path)
                    else:
                        os.remove(path)
                    n += 1
                except OSError:
                    pass
            print(f"pool purgado: {n} entradas")

    if not args.apply:
        print("DRY-RUN: no se ha borrado nada")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
