"""Banco de evaluación etiquetado, sin BD ni red (Fase 0).

Construye un manifiesto reproducible de referencia/queries a partir de un
listado de fotos etiquetadas y evalúa TAR/FAR por umbral usando embeddings ya
calculados que se inyectan desde fuera (esta fase **no** carga modelos).

Partición anti-leakage: por cada persona real se ordenan sus fotos por ``ts`` y
las primeras ``(1 - test_frac)`` van a referencia; las últimas ``test_frac`` van
a queries. Una foto nunca está en ambos conjuntos.

Formato de ``fotos`` (lista de dicts)::

    [{"foto_id": str, "persona_id": int, "ruta": str, "ts": float, "cam": str}, ...]

El fichero de etiquetas es el mismo que usa ``auditar_identidades``::

    [{"id": <int BD>, "cod_interno": "<str>", "persona": "<nombre real>"}, ...]
"""
from __future__ import annotations

import argparse
import json
import math
import os
from collections import defaultdict
from typing import Any, Mapping, Sequence

import numpy as np

from .auditar_identidades import normalizar_etiquetas

VERSION = 1
DEFAULT_TEST_FRAC = 0.3


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def cargar_json(path: str) -> Any:
    """Carga un JSON (lista o dict). Ruta ausente/vacía -> ``None``."""
    if not path or not os.path.exists(path) or os.path.getsize(path) == 0:
        return None
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _as_int(x: Any) -> int | None:
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def _unit(v: Any) -> np.ndarray:
    """Normaliza un vector a norma 1 (defensivo; entradas ya vienen L2-normalizadas)."""
    a = np.asarray(v, dtype=np.float64).ravel()
    n = float(np.linalg.norm(a))
    if n <= 0.0:
        return a
    return a / n


def _f(x: Any) -> float | None:
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ---------------------------------------------------------------------------
# Manifiesto
# ---------------------------------------------------------------------------
def _item(foto: Mapping[str, Any], persona: str) -> dict:
    return {
        "ruta": foto.get("ruta"),
        "persona_real": persona,
        "foto_id": foto.get("foto_id"),
        "persona_id": _as_int(foto.get("persona_id")),
        "cam": foto.get("cam"),
        "ts": _f(foto.get("ts")),
    }


def construir_manifiesto(
    fotos: Sequence[Mapping[str, Any]],
    etiquetas: Any,
    test_frac: float = DEFAULT_TEST_FRAC,
) -> dict:
    """Particiona las fotos en referencia/queries por persona real.

    Reglas:
        - Agrupa por persona real; ordena por ``ts`` (empates por ``foto_id``).
        - ``n_ref = clamp(int(n * (1 - test_frac)), 1, n-1)`` para ``n >= 2``.
        - ``n < 2`` (o partición degenerada) marca el grupo como insuficiente:
          sus fotos van a referencia y nunca a queries.
        - Sin solapamiento: una ruta de query jamás aparece en referencia.

    Returns:
        ``{"version", "referencia", "queries", "resumen"}``.
    """
    id2cod, realof, _ = normalizar_etiquetas(etiquetas)
    grupos: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    n_sin_etiqueta = 0
    for foto in fotos or []:
        if not isinstance(foto, Mapping):
            n_sin_etiqueta += 1
            continue
        pid = _as_int(foto.get("persona_id"))
        cod = id2cod.get(pid) if pid is not None else None
        persona = realof.get(cod) if cod is not None else None
        if persona is None:
            n_sin_etiqueta += 1
            continue
        grupos[persona].append(foto)

    try:
        frac = float(test_frac)
    except (TypeError, ValueError):
        frac = DEFAULT_TEST_FRAC
    frac = min(max(frac, 0.0), 1.0)

    referencia: list[dict] = []
    queries: list[dict] = []
    insuficientes: list[dict] = []
    for persona in sorted(grupos):
        fs = sorted(
            grupos[persona],
            key=lambda x: (_f(x.get("ts")) if _f(x.get("ts")) is not None else 0.0,
                           str(x.get("foto_id", ""))),
        )
        n = len(fs)
        if n < 2:
            insuficientes.append({"persona_real": persona, "n": n, "motivo": "menos_de_2_fotos"})
            referencia.extend(_item(f, persona) for f in fs)
            continue
        n_ref = int(n * (1.0 - frac))
        n_ref = max(1, min(n - 1, n_ref))
        if n_ref < 1 or (n - n_ref) < 1:
            insuficientes.append({"persona_real": persona, "n": n, "motivo": "particion_degenerada"})
            referencia.extend(_item(f, persona) for f in fs)
            continue
        referencia.extend(_item(f, persona) for f in fs[:n_ref])
        queries.extend(_item(f, persona) for f in fs[n_ref:])

    return {
        "version": VERSION,
        "test_frac": frac,
        "referencia": referencia,
        "queries": queries,
        "resumen": {
            "n_personas": len(grupos),
            "n_referencia": len(referencia),
            "n_queries": len(queries),
            "n_insuficientes": len(insuficientes),
            "insuficientes": insuficientes,
            "n_sin_etiqueta": n_sin_etiqueta,
            "test_frac": frac,
        },
    }


# ---------------------------------------------------------------------------
# Evaluación
# ---------------------------------------------------------------------------
def _dup_rate(asignaciones: Sequence[tuple[str | None, int | None]]) -> float | None:
    """% de personas reales con más de una identidad (``persona_id``) asignada.

    ``asignaciones`` son pares ``(persona_real, persona_id_del_match)``. Devuelve
    ``None`` si ningún match trae ``persona_id`` (no se puede medir).
    """
    por_persona: dict[str, set[int]] = defaultdict(set)
    for persona, pid in asignaciones:
        if persona is None or pid is None:
            continue
        por_persona[persona].add(pid)
    if not por_persona:
        return None
    dup = sum(1 for pids in por_persona.values() if len(pids) > 1)
    return dup / len(por_persona)


def evaluar(
    manifest: Mapping[str, Any],
    embeddings_por_ruta: Mapping[str, Any],
    umbrales: Sequence[float],
) -> dict:
    """Calcula TAR/FAR/dup_rate por umbral sobre el manifiesto.

    Para cada query se define:
        - ``gmax``: mejor coseno contra una referencia de su MISMA persona real.
        - ``imax``: mejor coseno contra una referencia de OTRA persona real.
        - ``top1``: referencia de mejor coseno global.

    Por umbral ``u``:
        - ``tar`` = queries con ``gmax >= u`` / queries con referencia genuina.
        - ``far`` = queries con ``imax >= u`` / total de queries evaluadas.
        - ``tar_top1`` / ``far_top1``: variantes independientes del umbral.
        - ``dup_rate``: sobre el ``persona_id`` del top-1 (si el manifiesto lo trae).

    Args:
        manifest: salida de :func:`construir_manifiesto`.
        embeddings_por_ruta: ``{ruta: vector}`` (ya L2-normalizado).
        umbrales: iterable de umbrales de coseno.

    Returns:
        ``{umbral_float: {tar, far, tar_top1, far_top1, dup_rate, n_*}}``.
    """
    refs = list(manifest.get("referencia") or [])
    queries = list(manifest.get("queries") or [])

    ref_vecs: list[np.ndarray] = []
    ref_personas: list[str | None] = []
    ref_pids: list[int | None] = []
    for r in refs:
        v = embeddings_por_ruta.get(r.get("ruta"))
        if v is None:
            continue
        ref_vecs.append(_unit(v))
        ref_personas.append(r.get("persona_real"))
        ref_pids.append(_as_int(r.get("persona_id")))
    R = np.vstack(ref_vecs) if ref_vecs else np.zeros((0, 0), dtype=np.float64)

    evaluadas: list[dict] = []
    n_faltantes = 0
    for q in queries:
        v = embeddings_por_ruta.get(q.get("ruta"))
        if v is None:
            n_faltantes += 1
            continue
        persona_q = q.get("persona_real")
        entry: dict[str, Any] = {
            "persona_real": persona_q,
            "gmax": None,
            "imax": None,
            "top1_correcto": False,
            "top1_pid": None,
            "top1_persona": None,
        }
        if R.shape[0] > 0:
            qv = _unit(v)
            if qv.shape[0] == R.shape[1]:
                sims = R @ qv                       # (n_ref,)
                gen = np.asarray([p == persona_q for p in ref_personas], dtype=bool)
                imp = ~gen
                if gen.any():
                    entry["gmax"] = float(sims[gen].max())
                if imp.any():
                    entry["imax"] = float(sims[imp].max())
                j = int(np.argmax(sims))
                entry["top1_correcto"] = bool(ref_personas[j] == persona_q)
                entry["top1_pid"] = ref_pids[j]
                entry["top1_persona"] = ref_personas[j]
            else:
                n_faltantes += 1
                continue
        evaluadas.append(entry)

    n_total = len(evaluadas)
    genuinas = [e for e in evaluadas if e["gmax"] is not None]
    impostoras = [e for e in evaluadas if e["imax"] is not None]
    dup = _dup_rate([(e["persona_real"], e["top1_pid"]) for e in evaluadas])
    tar_top1 = (
        sum(1 for e in genuinas if e["top1_correcto"]) / len(genuinas)
        if genuinas else None
    )
    far_top1 = (
        sum(1 for e in evaluadas if e["top1_persona"] is not None
            and e["top1_persona"] != e["persona_real"]) / n_total
        if n_total else None
    )

    resultados: dict[float, dict] = {}
    for u in umbrales:
        uf = float(u)
        tar = (
            sum(1 for e in genuinas if e["gmax"] is not None and e["gmax"] >= uf) / len(genuinas)
            if genuinas else None
        )
        far = (
            sum(1 for e in impostoras if e["imax"] is not None and e["imax"] >= uf) / n_total
            if n_total else None
        )
        resultados[uf] = {
            "tar": _f(tar),
            "far": _f(far),
            "tar_top1": _f(tar_top1),
            "far_top1": _f(far_top1),
            "dup_rate": _f(dup),
            "n_queries": n_total,
            "n_genuinas": len(genuinas),
            "n_impostoras": len(impostoras),
            "n_referencia": int(R.shape[0]),
            "n_sin_embedding": n_faltantes,
        }
    return resultados


# ---------------------------------------------------------------------------
# CLI (generación del manifiesto; sin BD ni red)
# ---------------------------------------------------------------------------
def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Genera un manifiesto de evaluación referencia/queries (offline)."
    )
    ap.add_argument("--fotos", required=True, help="JSON con foto_id/persona_id/ruta/ts/cam")
    ap.add_argument("--etiquetas", required=True, help="JSON con id/cod_interno/persona")
    ap.add_argument("--test-frac", type=float, default=DEFAULT_TEST_FRAC,
                    help="fracción de fotos por persona reservadas a queries (def. 0.3)")
    ap.add_argument("--out", default=None,
                    help="ruta de salida gitignored (si se omite, imprime por stdout)")
    return ap.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada CLI: imprime/guarda el manifiesto. No toca BD ni red."""
    args = _parse_args(argv)
    fotos = cargar_json(args.fotos) or []
    etiquetas = cargar_json(args.etiquetas)
    manifest = construir_manifiesto(fotos, etiquetas, args.test_frac)
    texto = json.dumps(manifest, ensure_ascii=False, indent=2)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(texto + "\n")
    else:
        print(texto)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
