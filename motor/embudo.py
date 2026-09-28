#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Embudo de recall — motor/embudo.py

Agrega los eventos de `motor/logs/embudo_<local>.jsonl` (Fase 0) y los cruza con
la BD (`ws.php embudo_datos`) para localizar en qué etapa se pierde gente:

    video → caras detectadas → caras guardadas → decisiones → estancias

Cobertura = `estancias / cruces_lineas` (cuántas de las personas que cruzaron una
línea acabaron registradas).

Uso:
    motor/venv/bin/python motor/embudo.py <local_id> [--desde YYYY-MM-DD] [--json]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.core.embudo import cobertura, leer_eventos, resumir  # noqa: E402

PROYECTO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def datos_bd(local_id, desde: str | None = None) -> dict:
    """Conteos de BD vía `ws.php embudo_datos`. {} si no se puede consultar."""
    args = ["php", os.path.join(PROYECTO, "ws.php"), "embudo_datos", str(local_id)]
    if desde:
        args.append(desde)
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=30, cwd=PROYECTO)
        return json.loads(r.stdout.strip() or "{}")
    except Exception:  # noqa: BLE001
        return {}


def _fmt(v) -> str:
    try:
        f = float(v)
        return str(int(f)) if f == int(f) else f"{f:.1f}"
    except (TypeError, ValueError):
        return str(v)


def informe(ruta: str, local_id, desde: str | None = None, bd: dict | None = None) -> dict:
    res = resumir(leer_eventos(ruta, local_id), desde=desde)
    bd = bd if bd is not None else datos_bd(local_id, desde)
    cruces = bd.get("cruces", 0)
    estancias = bd.get("estancias", 0)
    return {
        "local_id": local_id,
        "desde": desde,
        "bd": bd,
        "cobertura": round(cobertura(estancias, cruces), 4),
        "resumen": res,
    }


def imprimir(info: dict) -> None:
    bd = info.get("bd") or {}
    total = (info.get("resumen") or {}).get("total", {})
    print(f"Embudo de recall — local {info['local_id']}"
          + (f" (desde {info['desde']})" if info.get("desde") else ""))
    print("=" * 60)
    print(f"BD:  cruces={_fmt(bd.get('cruces', 0))}  estancias={_fmt(bd.get('estancias', 0))}  "
          f"videos={_fmt(bd.get('videos', 0))}  personas={_fmt(bd.get('personas', 0))}")
    print(f"Cobertura (estancias/cruces): {info.get('cobertura', 0) * 100:.1f}%")
    print()
    print("Extracción:")
    print(f"  vídeos={_fmt(total.get('videos', 0))}  frames={_fmt(total.get('frames', 0))}  "
          f"caras_detect={_fmt(total.get('caras_detect', 0))}  "
          f"caras_guard={_fmt(total.get('caras_guard', 0))}  "
          f"borrosas={_fmt(total.get('caras_borroso', 0))}  "
          f"dedup={_fmt(total.get('caras_dedup', 0))}  "
          f"cuerpos={_fmt(total.get('cuerpos', 0))}  cruces_log={_fmt(total.get('cruces', 0))}")
    verdicts = {k[len("verdicts_"):]: v for k, v in total.items() if k.startswith("verdicts_")}
    descartes = {k[len("descartes_"):]: v for k, v in total.items() if k.startswith("descartes_")}
    cuerpos = {k[len("cuerpos_"):]: v for k, v in total.items()
               if k.startswith("cuerpos_") and k not in ("cuerpos",)}
    print("Clasificación:")
    print(f"  verdicts={verdicts or '{}'}")
    print(f"  descartes={descartes or '{}'}")
    print(f"  cuerpos={cuerpos or '{}'}")
    por_dia = (info.get("resumen") or {}).get("por_dia", {})
    if por_dia:
        print()
        print("Por día / cámara:")
        for fecha in sorted(por_dia):
            for cam, acc in por_dia[fecha].items():
                print(f"  {fecha} cam {cam}: vídeos={_fmt(acc.get('videos', 0))} "
                      f"detect={_fmt(acc.get('caras_detect', 0))} "
                      f"guard={_fmt(acc.get('caras_guard', 0))} "
                      f"borrosas={_fmt(acc.get('caras_borroso', 0))} "
                      f"cruces={_fmt(acc.get('cruces', 0))}")
    print()
    print("Guía: si 'caras_borroso' es alto → revisar min_sharpness (Fase 2).")
    print("      si 'caras_detect'≈0 en vídeos con gente → sensibilidad de captura (Fase 1).")
    print("      si cobertura baja pero caras_guard alta → matching/identidad (Fase 3).")


def main() -> int:
    ap = argparse.ArgumentParser(description="Embudo de recall del motor de reconocimiento facial")
    ap.add_argument("local_id")
    ap.add_argument("--ruta", default=PROYECTO)
    ap.add_argument("--desde", default=None, help="solo eventos desde YYYY-MM-DD")
    ap.add_argument("--json", action="store_true", help="salida JSON cruda")
    args = ap.parse_args()

    info = informe(args.ruta, args.local_id, args.desde)
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
    else:
        imprimir(info)
    return 0


if __name__ == "__main__":
    sys.exit(main())
