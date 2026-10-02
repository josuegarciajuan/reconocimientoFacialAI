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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    args = ap.parse_args()
    root = os.path.realpath(os.path.join(args.ruta, "motor/backups"))
    if not os.path.isdir(root):
        print(f"backups inexistente: {root}")
        return 2
    now = dt.datetime.now()
    items = inventory(root)
    keep, purge = select(items, now)
    size = lambda xs: sum(x["size"] for x in xs)
    print(f"root={root}")
    print(f"total={len(items)} total_bytes={size(items)}")
    print(f"keep={len(keep)} keep_bytes={size(keep)}")
    print(f"purge={len(purge)} purge_bytes={size(purge)}")
    for x in purge:
        print(f"candidate {x['name']} {x['size']}")
    if not args.apply:
        print("DRY-RUN: no se ha borrado nada")
        return 0
    if not args.confirm:
        print("ERROR: --apply exige --confirm", flush=True)
        return 2
    for x in purge:
        path = os.path.realpath(x["path"])
        if not path.startswith(root + os.sep) or not PATTERN.fullmatch(os.path.basename(path)):
            raise RuntimeError(f"ruta rechazada: {path}")
        shutil.rmtree(path)
        print(f"deleted {x['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
