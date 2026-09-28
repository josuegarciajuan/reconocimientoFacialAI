"""Medición TAR/FAR por umbral sobre fotos reales publicadas (solo lectura).

Runner de medición (Fase 0+) que, **sin escribir nada**, toma una muestra
determinista de las fotos publicadas en ``admin/caras_procesadas/`` de una sala
(``local``), calcula el embedding de la cara principal en DOS dominios:

- ``nativo``: el embedding que ya devuelve el detector (``face.embedding``).
- ``sr``: embedding recalculado con SR-before-embedding
  (``superres.enhance_embedding``, solo si la cara es pequeña).

y llama a :func:`motor.audit.banco_eval.evaluar` para cada umbral, reportando
``tar``, ``far`` y ``gap = tar - far`` por dominio, además del *umbral
equilibrado* (mayor ``gap`` con ``far <= 0.10``; si ninguno lo cumple, el de
mayor ``gap``).

El objetivo es recalibrar el umbral de matching con datos reales y decidir si el
SR-before-embedding mejora la separación genuino/impostor.

Acceso a datos:
    - MySQL en **modo solo lectura** (SELECT) vía ``motor.core.photos._mysql``.
    - Imágenes en disco (``cv2.imread``).
    - Modelo de visión (insightface) y SR (torch/Real-ESRGAN), importados de
      forma perezosa para que este módulo sea importable (y testeable) sin ellos.

Uso::

    motor/venv/bin/python -m motor.audit.medir_banco \
        --local 1 --ruta /root/reconocimientoFacial \
        --etiquetas /ruta/etiquetas.json --max-fotos 80 --json

La parte pura (:func:`curva`, :func:`muestrear`, :func:`elegir_equilibrado`,
:func:`parsear_umbrales`) no toca BD, red ni modelo, y se testea con embeddings
sintéticos.

Nota de dirección de las métricas: al SUBIR el umbral, tanto ``tar`` como
``far`` son no crecientes (cada una exige ``cos >= umbral``). Por eso el triplete
``(tar, far)`` describe una curva ROC: bajar el umbral sube ambas; subirlo las
baja. ``gap = tar - far`` es la métrica de compromiso que se maximiza.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Mapping, Sequence

from .auditar_identidades import cargar_etiquetas, normalizar_etiquetas
from .banco_eval import construir_manifiesto, evaluar

VERSION = 1

#: Raíz del repo (padre de ``motor/``), como en el resto de scripts del motor.
RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

DEFAULT_UMBRALES = "0.30,0.35,0.40,0.45,0.48,0.50,0.55,0.60,0.65"
DEFAULT_MAX_FOTOS = 80
DEFAULT_TEST_FRAC = 0.3
DEFAULT_DET_SIZE = 640
DEFAULT_SR_MIN_FACE = 160

#: Score mínimo de detección para aceptar una cara (contexto de Fase 0).
MIN_SCORE = 0.4

#: ``far`` máximo admitido para el "umbral equilibrado".
FAR_MAX_EQUILIBRADO = 0.10


# ---------------------------------------------------------------------------
# Utilidades puras
# ---------------------------------------------------------------------------
def _f(x: Any) -> float | None:
    """Convierte a float JSON-safe (``None`` si no es finito o no convertible)."""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _epoch(fecha: Any) -> float:
    """Epoch local de una fecha MySQL (``YYYY-MM-DD HH:MM:SS``).

    Entrada nula, vacía, ``NULL`` o con formato irreconocible -> ``0.0`` (para
    no romper el orden temporal determinista del muestreo).
    """
    if fecha is None:
        return 0.0
    s = str(fecha).strip().strip("'\"")
    if not s or s.upper() == "NULL":
        return 0.0
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            return float(time.mktime(dt.timetuple()))
        except ValueError:
            continue
    return 0.0


def parsear_umbrales(raw: str | Sequence[float]) -> list[float]:
    """Parsea ``"0.3,0.5,0.7"`` (o una secuencia) a floats únicos y ordenados.

    Valores no numéricos o no finitos se ignoran. ``None``/vacío -> lista vacía.
    """
    if raw is None:
        return []
    if isinstance(raw, (int, float)):
        partes: Sequence[Any] = [raw]
    elif isinstance(raw, str):
        partes = raw.replace(";", ",").split(",")
    else:
        partes = list(raw)
    out: list[float] = []
    for p in partes:
        try:
            v = float(str(p).strip())
        except (TypeError, ValueError):
            continue
        if math.isfinite(v) and v not in out:
            out.append(v)
    out.sort()
    return out


def muestrear(
    fotos: Sequence[Mapping[str, Any]],
    max_fotos: int,
) -> list[Mapping[str, Any]]:
    """Muestra determinista repartida round-robin entre ``persona_id``.

    Agrupa por ``persona_id``, ordena cada grupo por ``ts`` (empates por
    ``foto_id``) y va tomando una foto de cada grupo por ronda hasta
    ``max_fotos``. Así ninguna identidad con muchas fotos ahoga a las demás.

    Determinista: dos ejecuciones con las mismas fotos dan la misma muestra.
    """
    if max_fotos <= 0:
        return []
    grupos: dict[Any, list[Mapping[str, Any]]] = defaultdict(list)
    for f in fotos:
        grupos[f.get("persona_id")].append(f)
    for pid in grupos:
        grupos[pid].sort(
            key=lambda x: (
                _f(x.get("ts")) if _f(x.get("ts")) is not None else 0.0,
                str(x.get("foto_id") or ""),
            )
        )
    orden = sorted(grupos, key=lambda p: (p is None, str(p)))
    idx = {pid: 0 for pid in orden}
    out: list[Mapping[str, Any]] = []
    while len(out) < max_fotos:
        progreso = False
        for pid in orden:
            if len(out) >= max_fotos:
                break
            k = idx[pid]
            if k < len(grupos[pid]):
                out.append(grupos[pid][k])
                idx[pid] = k + 1
                progreso = True
        if not progreso:
            break
    return out


def elegir_equilibrado(
    puntos: Mapping[float, Mapping[str, Any]],
    far_max: float = FAR_MAX_EQUILIBRADO,
) -> float | None:
    """Umbral de mayor ``gap`` con ``far <= far_max`` (fallback: mayor ``gap``).

    Si ningún punto cumple el tope de ``far``, se devuelve el de mayor ``gap``.
    Empates de ``gap``: se prefiere el umbral MÁS ALTO (más conservador, menos
    falsos positivos). Devuelve ``None`` si no hay ningún ``gap`` medible.
    """
    if not puntos:
        return None
    validos: list[tuple[float, float]] = []
    elegibles: list[tuple[float, float]] = []
    for u, d in puntos.items():
        g = d.get("gap") if isinstance(d, Mapping) else None
        if g is None:
            continue
        gu = float(u)
        gg = float(g)
        validos.append((gu, gg))
        far = d.get("far")
        if far is not None and float(far) <= far_max:
            elegibles.append((gu, gg))
    pool = elegibles or validos
    if not pool:
        return None
    return max(pool, key=lambda t: (t[1], t[0]))[0]


def curva(
    embeddings_por_ruta: Mapping[str, Any],
    manifest: Mapping[str, Any],
    umbrales: Sequence[float],
) -> dict:
    """Curva TAR/FAR/gap por umbral para UN dominio de embeddings.

    Parte **pura** (sin insightface, BD ni cv2): envuelve
    :func:`banco_eval.evaluar` y añade ``gap = tar - far`` y ``frr = 1 - tar``
    por umbral, más el umbral equilibrado del dominio.

    Args:
        embeddings_por_ruta: ``{ruta: vector}`` (L2-normalizado idealmente).
        manifest: salida de :func:`banco_eval.construir_manifiesto`.
        umbrales: umbrales de coseno a evaluar.

    Returns:
        ``{"umbrales", "puntos": {u: {...evaluar..., "gap", "frr"}},
        "umbral_equilibrado", "far_max_equilibrado"}``.
    """
    us = [float(u) for u in umbrales]
    ev = evaluar(manifest, embeddings_por_ruta, us)
    puntos: dict[float, dict] = {}
    for u in us:
        d = dict(ev.get(u, {}))
        tar = d.get("tar")
        far = d.get("far")
        d["gap"] = _f((tar - far) if (tar is not None and far is not None) else None)
        d["frr"] = _f((1.0 - tar) if tar is not None else None)
        puntos[u] = d
    return {
        "umbrales": us,
        "puntos": puntos,
        "umbral_equilibrado": elegir_equilibrado(puntos, FAR_MAX_EQUILIBRADO),
        "far_max_equilibrado": FAR_MAX_EQUILIBRADO,
    }


def _mejor_dominio(dominios: Mapping[str, Mapping[str, Any]]) -> str | None:
    """Dominio con mayor ``gap`` en su umbral equilibrado (nombre alfabético al empatar)."""
    mejor: str | None = None
    mejor_gap: float | None = None
    for nombre in sorted(dominios):
        d = dominios[nombre]
        u = d.get("umbral_equilibrado")
        if u is None:
            continue
        g = d.get("puntos", {}).get(u, {}).get("gap")
        if g is None:
            continue
        if mejor_gap is None or float(g) > mejor_gap:
            mejor_gap = float(g)
            mejor = nombre
    return mejor


# ---------------------------------------------------------------------------
# Acceso a datos (impuro: BD e imágenes)
# ---------------------------------------------------------------------------
def consulta_fotos(ruta: str, local: int) -> list[dict]:
    """SELECT de solo lectura: filas de fotos con su identidad y metadata.

    Devuelve dicts con ``foto_id`` (str), ``persona_id`` (int),
    ``cod_interno`` (str), ``fecha_ini`` (str) y ``cam`` (str).
    """
    from ..core.photos import _mysql

    sql = (
        "SELECT f.id, e.persona_id, p.cod_interno, e.fecha_ini, e.camara_id "
        "FROM fotos f "
        "JOIN estancias e ON e.id = f.estancia_id "
        "JOIN personas p ON p.id = e.persona_id "
        f"WHERE e.persona_id <> 0 AND p.local_id = {int(local)} "
        "ORDER BY e.persona_id, e.fecha_ini, f.id"
    )
    filas: list[dict] = []
    for linea in _mysql(ruta, sql):
        partes = linea.split("\t")
        if len(partes) < 5:
            continue
        pid = _f(partes[1])
        filas.append(
            {
                "foto_id": partes[0].strip(),
                "persona_id": int(pid) if pid is not None else None,
                "cod_interno": partes[2].strip(),
                "fecha_ini": partes[3].strip(),
                "cam": partes[4].strip(),
            }
        )
    return filas


def construir_fotos(ruta: str, local: int) -> tuple[list[dict], int, int]:
    """Fotos de BD cuyo fichero existe en disco.

    Returns:
        ``(fotos, n_sin_fichero, n_filas)`` donde ``fotos`` trae ``ruta`` y
        ``ts`` ya resueltos, listos para :func:`construir_manifiesto`.
    """
    filas = consulta_fotos(ruta, local)
    fotos_dir = os.path.join(ruta, "admin/caras_procesadas")
    out: list[dict] = []
    n_sin_fichero = 0
    for r in filas:
        fid = r["foto_id"]
        if not fid:
            continue
        p = os.path.join(fotos_dir, fid + ".jpg")
        if not os.path.isfile(p):
            n_sin_fichero += 1
            continue
        out.append(
            {
                "foto_id": fid,
                "persona_id": r["persona_id"],
                "cod_interno": r["cod_interno"],
                "ruta": p,
                "ts": _epoch(r["fecha_ini"]),
                "cam": r["cam"],
            }
        )
    return out, n_sin_fichero, len(filas)


def _embeber_muestra(
    muestra: Sequence[Mapping[str, Any]],
    cfg: Any,
    det_size: int,
    verbose: bool = True,
) -> tuple[dict[str, Any], dict[str, Any], list[dict], int, int]:
    """Calcula embeddings nativo y SR de cada foto de la muestra.

    Por foto: lee la imagen, detecta caras, elige la de mayor ``det_score`` y
    calcula los dos dominios. Devuelve
    ``(embs_nativo, embs_sr, fotos_ok, n_sin_imagen, n_sin_cara)``.
    """
    import cv2  # import perezoso: mantiene el módulo importable sin cv2 real

    from ..core.model import analyze
    from ..core.superres import enhance_embedding

    embs_nativo: dict[str, Any] = {}
    embs_sr: dict[str, Any] = {}
    fotos_ok: list[dict] = []
    n_sin_imagen = 0
    n_sin_cara = 0
    total = len(muestra)
    for i, foto in enumerate(muestra, 1):
        img = cv2.imread(str(foto.get("ruta")))
        if img is None:
            n_sin_imagen += 1
            continue
        caras = analyze(img, det_size=(det_size, det_size), min_score=MIN_SCORE)
        if not caras:
            n_sin_cara += 1
        else:
            cara = max(caras, key=lambda c: float(c.det_score))
            embs_nativo[foto["ruta"]] = cara.embedding
            embs_sr[foto["ruta"]] = enhance_embedding(img, cara, cfg)
            fotos_ok.append(dict(foto))
        if verbose and (i % 10 == 0 or i == total):
            print(f"  [medir] {i}/{total} fotos", file=sys.stderr, flush=True)
    return embs_nativo, embs_sr, fotos_ok, n_sin_imagen, n_sin_cara


# ---------------------------------------------------------------------------
# Resumen
# ---------------------------------------------------------------------------
def resumen_muestra(
    fotos_ok: Sequence[Mapping[str, Any]],
    etiquetas: Any,
) -> dict:
    """Personas reales incluidas y fragmentación (cods) dentro de la muestra medida."""
    id2cod, realof, _ = normalizar_etiquetas(etiquetas)
    por_real: dict[str, dict] = {}
    sin_etiqueta = 0
    for f in fotos_ok:
        pid = f.get("persona_id")
        cod = id2cod.get(pid) if pid is not None else None
        real = realof.get(cod) if cod is not None else None
        if real is None:
            sin_etiqueta += 1
            continue
        d = por_real.setdefault(
            real, {"persona_ids": set(), "cods": set(), "n_fotos": 0}
        )
        if pid is not None:
            d["persona_ids"].add(int(pid))
        if cod is not None:
            d["cods"].add(str(cod))
        d["n_fotos"] += 1
    detalle: dict[str, dict] = {}
    for real, d in por_real.items():
        detalle[real] = {
            "n_fragmentos": len(d["cods"]),
            "n_persona_id": len(d["persona_ids"]),
            "persona_ids": sorted(d["persona_ids"]),
            "cods": sorted(d["cods"]),
            "n_fotos": int(d["n_fotos"]),
        }
    return {
        "n_personas_reales": len(por_real),
        "n_fotos_sin_etiqueta": sin_etiqueta,
        "por_persona_real": detalle,
    }


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------
def _num(x: Any, dec: int = 3) -> str:
    """Formatea un float tolerando ``None``."""
    return "-" if x is None else f"{float(x):.{dec}f}"


def formato_texto(salida: Mapping[str, Any]) -> str:
    """Render legible del resultado (sin flag ``--json``)."""
    p = salida.get("parametros", {})
    m = salida.get("muestreo", {})
    lineas = [
        "== Medición TAR/FAR nativo vs SR (solo lectura) ==",
        f"local={p.get('local')}  etiquetas={p.get('etiquetas')}",
        f"max_fotos={p.get('max_fotos')}  test_frac={p.get('test_frac')}  "
        f"det_size={p.get('det_size')}  sr_min_face={p.get('sr_min_face')}",
        "",
        "-- Muestreo --",
        f"fotos en BD: {m.get('n_filas')}  |  con fichero: {m.get('n_con_fichero')}  "
        f"|  sin fichero: {m.get('n_sin_fichero')}",
        f"muestra: {m.get('n_muestra')}  |  con cara (medidas): {m.get('n_medidas')}  "
        f"|  sin imagen: {m.get('n_sin_imagen')}  |  sin cara: {m.get('n_sin_cara')}",
        f"descartadas por muestreo: {m.get('n_descartadas_muestreo')}  "
        f"|  sin etiqueta real: {m.get('n_sin_etiqueta')}",
        f"personas reales incluidas: {m.get('n_personas_reales')}",
    ]
    for real, d in (m.get("por_persona_real") or {}).items():
        lineas.append(
            f"  {real}: {d['n_fragmentos']} fragmentos / {d['n_persona_id']} id(s) "
            f"| {d['n_fotos']} fotos | ids={d['persona_ids']} cods={d['cods']}"
        )
    r = salida.get("manifiesto", {})
    lineas += [
        "",
        "-- Manifiesto --",
        f"referencia={r.get('n_referencia')}  queries={r.get('n_queries')}  "
        f"insuficientes={r.get('n_insuficientes')}  test_frac={r.get('test_frac')}",
    ]
    for aviso in salida.get("avisos") or []:
        lineas.append(f"AVISO: {aviso}")
    for nombre, d in (salida.get("dominios") or {}).items():
        lineas += [
            "",
            f"-- Dominio {nombre} --",
            "  umbral     tar     far     gap",
        ]
        for u, pt in d.get("puntos", {}).items():
            lineas.append(
                f"  {_num(u, 2):>5}   {_num(pt.get('tar')):>6}  "
                f"{_num(pt.get('far')):>6}  {_num(pt.get('gap')):>6}"
            )
        eq = d.get("umbral_equilibrado")
        lineas.append(
            f"  umbral equilibrado (gap máx con far<={d.get('far_max_equilibrado')}): "
            f"{_num(eq, 2) if eq is not None else '-'}"
        )
    lineas += ["", f"mejor dominio (gap en su equilibrado): {salida.get('mejor_dominio') or '-'}"]
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Mide TAR/FAR por umbral (nativo vs SR) sobre fotos reales (solo lectura)."
    )
    ap.add_argument("--local", type=int, default=1, help="sala/local_id (def. 1)")
    ap.add_argument("--ruta", default=RAIZ, help="raíz del repo (def. padre de motor/)")
    ap.add_argument("--etiquetas", required=True, help="JSON con id/cod_interno/persona")
    ap.add_argument("--max-fotos", type=int, default=DEFAULT_MAX_FOTOS,
                    help="máximo de fotos a medir (muestreo determinista, def. 80)")
    ap.add_argument("--test-frac", type=float, default=DEFAULT_TEST_FRAC,
                    help="fracción de queries por persona (def. 0.3)")
    ap.add_argument("--det-size", type=int, default=DEFAULT_DET_SIZE,
                    help="tamaño de detección de insightface (def. 640)")
    ap.add_argument("--sr-min-face", type=int, default=DEFAULT_SR_MIN_FACE,
                    help="lado mayor de cara bajo el que aplica SR-before-embedding (def. 160)")
    ap.add_argument("--umbrales", default=DEFAULT_UMBRALES,
                    help="umbrales separados por comas")
    ap.add_argument("--json", action="store_true", help="emitir el resultado como JSON")
    return ap.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada CLI. Solo lee (BD SELECT, ficheros, modelos); no escribe nada."""
    args = _parse_args(argv)
    umbrales = parsear_umbrales(args.umbrales)
    avisos: list[str] = []

    etiquetas = cargar_etiquetas(args.etiquetas)
    id2cod, realof, _ = etiquetas
    if not id2cod and not realof:
        print(
            f"ERROR: fichero de etiquetas vacío o ausente: {args.etiquetas}",
            file=sys.stderr,
        )
        return 1

    # 1) BD + disco
    try:
        fotos, n_sin_fichero, n_filas = construir_fotos(args.ruta, int(args.local))
    except RuntimeError as e:  # mysql CLI ausente, credenciales mal, BD caída...
        print(f"ERROR: no se pudo consultar MySQL: {e}", file=sys.stderr)
        return 1
    if not fotos:
        print(
            "ERROR: no hay fotos publicadas con fichero en "
            f"admin/caras_procesadas/ (local={args.local}, filas BD={n_filas}).",
            file=sys.stderr,
        )
        return 1

    # 2) Solo fotos con persona real etiquetada (el presupuesto va a identidades reales)
    def _real_of(f: Mapping[str, Any]) -> str | None:
        pid = f.get("persona_id")
        cod = id2cod.get(pid) if pid is not None else None
        return realof.get(cod) if cod is not None else None

    fotos_etq = [f for f in fotos if _real_of(f) is not None]
    n_sin_etiqueta = len(fotos) - len(fotos_etq)
    if not fotos_etq:
        print(
            "ERROR: ninguna foto publicada tiene persona real en el fichero de etiquetas.",
            file=sys.stderr,
        )
        return 1

    # 3) Muestreo determinista round-robin entre persona_id
    muestra = muestrear(fotos_etq, int(args.max_fotos))
    n_descartadas_muestreo = len(fotos_etq) - len(muestra)

    # 4) Modelo y config
    from ..core.config import Config

    cfg = Config.from_env(args.ruta)
    cfg.sr_embed_min_face = int(args.sr_min_face)
    cfg.sr_embed_enabled = True  # fuerza el dominio SR en la medición

    # 5) Embeddings nativo + SR
    embs_nativo, embs_sr, fotos_ok, n_sin_imagen, n_sin_cara = _embeber_muestra(
        muestra, cfg, int(args.det_size)
    )
    if not fotos_ok:
        print(
            f"ERROR: ninguna de las {len(muestra)} fotos de la muestra tiene cara "
            f"(sin imagen={n_sin_imagen}, sin cara={n_sin_cara}).",
            file=sys.stderr,
        )
        return 1

    # 6) Manifiesto y curvas
    manifest = construir_manifiesto(fotos_ok, etiquetas, float(args.test_frac))
    if manifest["resumen"]["n_queries"] == 0:
        avisos.append(
            "sin queries evaluables (cada persona real tiene menos de 2 fotos); "
            "TAR/FAR no medibles."
        )
    if not umbrales:
        avisos.append("lista de umbrales vacía; no se evalúa ninguna curva.")
        umbrales = parsear_umbrales(DEFAULT_UMBRALES)

    dominios = {
        "nativo": curva(embs_nativo, manifest, umbrales),
        "sr": curva(embs_sr, manifest, umbrales),
    }

    m = resumen_muestra(fotos_ok, etiquetas)
    salida = {
        "version": VERSION,
        "parametros": {
            "local": int(args.local),
            "ruta": os.path.abspath(args.ruta),
            "etiquetas": os.path.abspath(args.etiquetas),
            "max_fotos": int(args.max_fotos),
            "test_frac": float(args.test_frac),
            "det_size": int(args.det_size),
            "sr_min_face": int(args.sr_min_face),
            "umbrales": umbrales,
        },
        "muestreo": {
            "n_filas": n_filas,
            "n_con_fichero": len(fotos),
            "n_sin_fichero": n_sin_fichero,
            "n_etiquetadas": len(fotos_etq),
            "n_sin_etiqueta": n_sin_etiqueta,
            "n_muestra": len(muestra),
            "n_descartadas_muestreo": n_descartadas_muestreo,
            "n_medidas": len(fotos_ok),
            "n_sin_imagen": n_sin_imagen,
            "n_sin_cara": n_sin_cara,
            "n_personas_reales": m["n_personas_reales"],
            "n_fotos_sin_etiqueta_medidas": m["n_fotos_sin_etiqueta"],
            "por_persona_real": m["por_persona_real"],
        },
        "manifiesto": manifest["resumen"],
        "dominios": dominios,
        "mejor_dominio": _mejor_dominio(dominios),
        "avisos": avisos,
    }
    if args.json:
        print(json.dumps(salida, ensure_ascii=False, indent=2))
    else:
        print(formato_texto(salida))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
