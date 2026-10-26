#!/usr/bin/env python3
"""Informe de latencia y cobertura del pipeline.

Lee los ficheros ``motor/logs/pipeline_metrics_<local>.jsonl`` y calcula
percentiles por etapa (p50/p95/p99), estado de cola y cobertura de resultados.

Uso:
    motor/venv/bin/python motor/pipeline_report.py [--local 1] [--file RUTA]
        [--since-hours N] [--json]
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


def load_events(paths: list[str]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path in paths:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        except OSError:
            continue
    return events


def pct(values: list[float], p: float) -> float | None:
    xs = sorted(float(v) for v in values if v is not None)
    if not xs:
        return None
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * (float(p) / 100.0)
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return xs[int(k)]
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def summarize(events: list[dict[str, Any]], *, since: float | None = None) -> dict[str, Any]:
    by_stage: dict[str, list[float]] = {}
    summaries = 0
    final_count = 0
    early_count = 0
    units: set[str] = set()
    queue_latest: dict[str, Any] | None = None
    first_ts = None
    last_ts = None

    for ev in events:
        ts = ev.get("ts")
        if ts is None:
            continue
        if since is not None and float(ts) < since:
            continue
        first_ts = float(ts) if first_ts is None else min(first_ts, float(ts))
        last_ts = float(ts) if last_ts is None else max(last_ts, float(ts))
        tipo = ev.get("tipo")
        if tipo == "stage" and (ev.get("extra") or {}).get("event") == "end":
            stage = ev.get("stage") or "?"
            dur = ev.get("duration_s")
            if dur is not None:
                by_stage.setdefault(stage, []).append(float(dur))
            if ev.get("unit_id"):
                units.add(str(ev["unit_id"]))
        elif tipo == "summary":
            summaries += 1
            kind = ev.get("result_kind")
            if kind == "final":
                final_count += 1
            elif kind == "temprano":
                early_count += 1
        elif tipo == "queue":
            queue_latest = {"ts": ts, "counts": ev.get("counts") or {}}

    stages = {}
    for stage, vals in sorted(by_stage.items()):
        stages[stage] = {
            "count": len(vals),
            "p50_s": round(pct(vals, 50) or 0.0, 3),
            "p95_s": round(pct(vals, 95) or 0.0, 3),
            "p99_s": round(pct(vals, 99) or 0.0, 3),
            "total_s": round(sum(vals), 3),
        }

    return {
        "events": len(events),
        "first_ts": first_ts,
        "last_ts": last_ts,
        "window_s": (last_ts - first_ts) if (first_ts and last_ts) else 0.0,
        "distinct_units": len(units),
        "summaries": summaries,
        "final_summaries": final_count,
        "early_summaries": early_count,
        "stages": stages,
        "queue_latest": queue_latest,
    }


def _resolve_paths(args) -> list[str]:
    if args.file:
        return [args.file]
    root = args.ruta or os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    pattern = os.path.join(root, "motor", "logs", f"pipeline_metrics_{args.local}.jsonl")
    return sorted(glob.glob(pattern))


def format_table(report: dict[str, Any]) -> str:
    lines = []
    lines.append(f"eventos: {report['events']}  unidades: {report['distinct_units']}  "
                 f"ventana: {report['window_s']:.1f}s")
    lines.append(f"resúmenes: {report['summaries']} "
                 f"(final={report['final_summaries']}, temprano={report['early_summaries']})")
    if report["queue_latest"]:
        counts = report["queue_latest"]["counts"]
        lines.append("cola (último): " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
    lines.append("")
    lines.append(f"{'etapa':24} {'n':>6} {'p50(s)':>9} {'p95(s)':>9} {'p99(s)':>9}")
    lines.append("-" * 62)
    for stage, s in report["stages"].items():
        lines.append(f"{stage:24} {s['count']:>6} {s['p50_s']:>9.3f} "
                     f"{s['p95_s']:>9.3f} {s['p99_s']:>9.3f}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Informe de latencia del pipeline")
    ap.add_argument("--local", type=int, default=1)
    ap.add_argument("--file", default=None, help="fichero JSONL concreto")
    ap.add_argument("--ruta", default=None, help="raíz del proyecto")
    ap.add_argument("--since-hours", type=float, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    since = None
    if args.since_hours is not None:
        since = time.time() - float(args.since_hours) * 3600.0

    paths = _resolve_paths(args)
    events = load_events(paths)
    report = summarize(events, since=since)
    report["files"] = paths

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(format_table(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
