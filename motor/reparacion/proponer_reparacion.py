"""Propuesta de reparación de identidades (fragmentación + contaminación).

**SOLO LECTURA**: este módulo nunca escribe el store, no crea ``.lock``/``.tmp``
y no toca la BD. Genera un JSON con las operaciones que ``aplicar_reparacion``
podría ejecutar.

Modelo de datos del store (pickle ``face_enc_v2``)::

    {"version": 4, "schema": "face_enc_v2",
     "persons": {cod: {"encodings": [ndarray(512,), ...],
                        "quality": [...], "poses": [...],
                        "sources": [str|None, ...], ...}}}

Etiquetas ground-truth (JSON) — la verdad la fija el usuario::

    [{"id": <int BD>, "cod_interno": "<str>", "persona": "<nombre real>"}]

Dos patologías:

- **Fragmentación**: varios ``cod_interno`` etiquetados con la MISMA persona
  real. Se propone fusionarlos en un único destino. Es una decisión tomada con
  ground-truth, no con coseno: ``--merge-min-cos`` solo sirve para REPORTAR la
  cohesión interna del grupo (no filtra nada).
- **Contaminación**: dentro de una galería hay encodings cuyo vecino externo
  más cercano pertenece a OTRA persona real. Se propone moverlos (por
  proveniencia ``sources``) a la persona correcta, o purgarlos si la persona
  externa es desconocida.

Parte pura (``proponer_merges``, ``proponer_contaminacion``,
``construir_propuesta``) separada de la CLI/IO para poder testearla sin red ni
BD.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from itertools import combinations
from typing import Any, Mapping, Sequence

import numpy as np

from motor.audit.auditar_identidades import (
    _cos_max,
    _f,
    _mat,
    _media_intra,
    cargar_etiquetas,
    cargar_store,
    nearest_external,
    normalizar_etiquetas,
)

#: Umbral por defecto para marcar un encoding como contaminado (coseno con el
#: vecino externo). Calibrado con el umbral de ``move_foto`` (~0.45) y los
#: genuinos de videovigilancia (~0.5-0.9).
CONTAM_MIN_COS_DEFAULT = 0.45

#: Con etiquetas ground-truth no se filtra por coseno; este valor solo se usa
#: para reportar si la cohesión del grupo alcanza el umbral.
MERGE_MIN_COS_DEFAULT = 0.0

Par = frozenset


# ---------------------------------------------------------------------------
# Normalización de entradas (store / etiquetas / bloqueados)
# ---------------------------------------------------------------------------
def _persons_map(store: Any) -> dict[str, Mapping[str, Any]]:
    """Devuelve ``{cod: person_dict}`` aceptando un dict-store o un ``FaceStore``.

    No muta nada: para ``FaceStore`` solo usa métodos de lectura y filtra a los
    valores que sean mappings. Un store vacío/ilegible devuelve ``{}``.
    """
    if hasattr(store, "persons") and hasattr(store, "person"):
        out: dict[str, Mapping[str, Any]] = {}
        for cod in store.persons():
            p = store.person(cod)
            if isinstance(p, Mapping):
                out[str(cod)] = p
        return out
    if isinstance(store, Mapping):
        persons = store.get("persons") or {}
        if isinstance(persons, Mapping):
            return {str(c): p for c, p in persons.items() if isinstance(p, Mapping)}
    return {}


def _matrices(persons: Mapping[str, Mapping[str, Any]]) -> dict[str, np.ndarray]:
    """Matriz 2-D de encodings por cod (float64, lista vacía -> ``(0, 0)``)."""
    return {cod: _mat(p.get("encodings") or []) for cod, p in persons.items()}


def _sources(p: Mapping[str, Any], n: int) -> list[str | None]:
    """Proveniencias alineadas a ``n`` (rellena con ``None`` si faltan)."""
    src = list(p.get("sources") or [])
    if len(src) < n:
        src = src + [None] * (n - len(src))
    return src[:n]


def _normalizar_bloqueados(bloqueados: Any) -> set[Par]:
    """Normaliza una colección de pares a un set de ``frozenset({a, b})``.

    Acepta listas/tuplas de 2 elementos y ya-frozensets. Ignora pares
    inválidos, repetidos o con ``a == b``.
    """
    out: set[Par] = set()
    if not bloqueados:
        return out
    for par in bloqueados:
        try:
            a, b = tuple(par)
        except (TypeError, ValueError):
            continue
        if a is None or b is None:
            continue
        a, b = str(a), str(b)
        if a == b:
            continue
        out.add(frozenset((a, b)))
    return out


def _cargar_bloqueados(path: str | None) -> set[Par]:
    """Carga un JSON de pares bloqueados (lista de ``[cod_a, cod_b]``).

    Acepta también ``{"bloqueados": [...]}`` / ``{"pares": [...]}``. Ruta
    ausente o vacía -> conjunto vacío.
    """
    if not path or not os.path.exists(path) or os.path.getsize(path) == 0:
        return set()
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    if isinstance(raw, Mapping):
        raw = raw.get("bloqueados") or raw.get("pares") or []
    return _normalizar_bloqueados(raw)


# ---------------------------------------------------------------------------
# Estadísticas por cod
# ---------------------------------------------------------------------------
def _stats_cod(persons: Mapping[str, Mapping[str, Any]], cod: str) -> dict:
    """``{n, intra}`` de un cod: nº de encodings y media intra (o ``None``)."""
    p = persons.get(cod) or {}
    M = _mat(p.get("encodings") or [])
    return {"n": int(M.shape[0]), "intra": _media_intra(M)}


def _clave_preferencia(n: int, intra: float | None, cod: str) -> tuple:
    """Orden de preferencia para elegir destino: más encodings, mejor intra, cod.

    Devuelve una clave apta para ``sorted`` (menor = mejor).
    """
    intra_v = float(intra) if intra is not None else float("-inf")
    return (-int(n), -intra_v, str(cod))


def _elegir_destino(cods: Sequence[str], stats: Mapping[str, dict]) -> str:
    """Destino de un grupo: el cod con más encodings (desempate intra, lex)."""
    return min(
        cods,
        key=lambda c: _clave_preferencia(stats[c]["n"], stats[c]["intra"], c),
    )


# ---------------------------------------------------------------------------
# Fragmentación: partición con restricciones de co-ocurrencia
# ---------------------------------------------------------------------------
def _particionar(
    cods_pref: Sequence[str], bloqueados: set[Par]
) -> tuple[list[list[str]], list[dict]]:
    """Reparte cods de una persona en componentes que respetan los bloqueos.

    ``bloqueados`` contiene pares que **no** pueden coexistir (co-ocurrencia =
    personas distintas). Algoritmo:

    1. Un cod **bloqueado con todos** los demás de su persona es una
       contradicción irresoluble (no puede fusionarse con nadie): se aparta y
       se marca en ``excluidos``.
    2. Con el resto se hace *first-fit* greedy: cada cod entra en la componente
       compatible (sin bloqueo con ningún miembro) más grande; si no hay
       ninguna compatible, abre su propia componente.

    Args:
        cods_pref: cods de una misma persona, en orden de preferencia
            (destino primero).
        bloqueados: pares prohibidos.

    Returns:
        ``(componentes, excluidos)``. ``excluidos`` es una lista de
        ``{"cod", "motivo"}``.
    """
    cods = list(dict.fromkeys(cods_pref))
    if len(cods) < 2:
        return ([cods] if cods else []), []

    universo = set(cods)
    excluidos: list[dict] = []
    descartados: set[str] = set()
    for cod in cods:
        otros = universo - {cod}
        if otros and all(frozenset((cod, o)) in bloqueados for o in otros):
            excluidos.append({
                "cod": cod,
                "motivo": "bloqueado por co-ocurrencia con todos los fragmentos de su persona",
            })
            descartados.add(cod)

    comps: list[list[str]] = []
    for cod in cods:
        if cod in descartados:
            continue
        compatibles = [
            k
            for k, comp in enumerate(comps)
            if not any(frozenset((cod, m)) in bloqueados for m in comp)
        ]
        if not comps:
            comps.append([cod])
        elif compatibles:
            # Mayor componente (desempate: la primera, más preferente).
            k = max(compatibles, key=lambda k: (len(comps[k]), -k))
            comps[k].append(cod)
        else:
            comps.append([cod])
    return comps, excluidos


def _cohesion(comp: Sequence[str], matrices: Mapping[str, np.ndarray]) -> dict:
    """Cohesión de una componente: max/mediana del mejor coseno entre sus cods."""
    pares: list[float] = []
    for a, b in combinations(sorted(comp), 2):
        c = _cos_max(matrices.get(a, _mat([])), matrices.get(b, _mat([])))
        if c is not None:
            pares.append(float(c))
    if not pares:
        return {"max": None, "mediana": None, "n_pares": 0}
    arr = np.asarray(pares, dtype=np.float64)
    return {
        "max": _f(float(arr.max())),
        "mediana": _f(float(np.median(arr))),
        "n_pares": int(len(pares)),
    }


def _analizar_merges(
    store: Any, etiquetas: Any, bloqueados: Any
) -> tuple[list[dict], list[dict]]:
    """Núcleo puro de ``proponer_merges``: devuelve ``(merges, excluidos_global)``."""
    _, realof, real_clusters = normalizar_etiquetas(etiquetas)
    persons = _persons_map(store)
    matrices = _matrices(persons)
    bloq = _normalizar_bloqueados(bloqueados)
    stats = {cod: _stats_cod(persons, cod) for cod in persons}

    merges: list[dict] = []
    excluidos_global: list[dict] = []
    for persona in sorted(real_clusters):
        cods = [c for c in real_clusters[persona] if c in persons]
        if not cods:
            continue
        # Orden de preferencia (destino primero) para una partición determinista.
        cods.sort(key=lambda c: _clave_preferencia(stats[c]["n"], stats[c]["intra"], c))
        comps, excluidos = _particionar(cods, bloq)
        for e in excluidos:
            excluidos_global.append({"persona": persona, **e})
        for comp in comps:
            if len(comp) < 2:
                continue
            destino = _elegir_destino(comp, stats)
            fuentes = sorted(
                (c for c in comp if c != destino),
                key=lambda c: _clave_preferencia(stats[c]["n"], stats[c]["intra"], c),
            )
            merges.append({
                "persona": persona,
                "destino": destino,
                "cods_fuente": list(fuentes),
                "n_cods": len(comp),
                "n_encodings": int(sum(stats[c]["n"] for c in comp)),
                "cohesion": _cohesion(comp, matrices),
                "excluidos": [e for e in excluidos],
                "cods_grupo": list(comp),
            })
    merges.sort(key=lambda m: (m["persona"], m["destino"]))
    return merges, excluidos_global


def proponer_merges(store: Any, etiquetas: Any, bloqueados: Any = None) -> list[dict]:
    """Propone fusiones de fragmentos de la misma persona real (ground-truth).

    Agrupa TODOS los ``cod_interno`` etiquetados con la misma ``persona`` y
    propone fusionarlos en un único destino (el cod con más encodings; desempate
    por mayor media intra, luego cod lexicográfico). Los pares bloqueados por
    co-ocurrencia nunca quedan en el mismo grupo; si un cod está bloqueado con
    todos los demás se marca en ``excluidos``.

    Args:
        store: dict ``face_enc_v2`` o ``FaceStore`` (solo lectura).
        etiquetas: tupla ``(id2cod, realof, real_clusters)``, lista JSON o None.
        bloqueados: colección de pares ``[cod_a, cod_b]`` prohibidos.

    Returns:
        Lista de propuestas ``{persona, destino, cods_fuente, n_cods,
        n_encodings, cohesion, excluidos, cods_grupo}``.
    """
    merges, _ = _analizar_merges(store, etiquetas, bloqueados)
    return merges


# ---------------------------------------------------------------------------
# Contaminación: vecino externo por encoding
# ---------------------------------------------------------------------------
def _mejores_por_persona(
    real_clusters: Mapping[str, Sequence[str]],
    matrices: Mapping[str, np.ndarray],
) -> dict[str, str]:
    """Destino (cod con más encodings) de cada persona real presente en el store."""
    stats = {
        cod: {"n": int(matrices[cod].shape[0]) if cod in matrices else 0,
              "intra": _media_intra(matrices[cod]) if cod in matrices else None}
        for cod in {c for cods in real_clusters.values() for c in cods}
    }
    out: dict[str, str] = {}
    for persona, cods in real_clusters.items():
        presentes = [c for c in cods if c in matrices and matrices[c].shape[0] > 0]
        if presentes:
            out[persona] = _elegir_destino(presentes, stats)
    return out


def proponer_contaminacion(
    store: Any, etiquetas: Any, contam_min_cos: float = CONTAM_MIN_COS_DEFAULT
) -> list[dict]:
    """Propone mover/purgar encodings cuyo vecino externo es de otra persona.

    Para cada cod etiquetado y cada uno de sus encodings se calcula el vecino
    externo más cercano (``nearest_external``, excluyendo el propio cod). Si la
    persona real de ese vecino es distinta de la del cod y el coseno alcanza
    ``contam_min_cos``, el encoding se considera contaminado y se agrupa por
    ``(cod_origen, persona_destino)``.

    - ``destino_cod``: cod de la persona externa con más encodings (destino del
      movimiento). ``None`` si la persona externa es desconocida.
    - ``accion``: ``"mover"`` si hay destino; ``"purgar"`` si no.
    - ``sin_fuente``: subconjunto de encodings contaminados sin ``source``; solo
      pueden purgarse (no moverse de forma exacta por proveniencia).

    Args:
        store: dict ``face_enc_v2`` o ``FaceStore`` (solo lectura).
        etiquetas: tupla/lista/None con las etiquetas ground-truth.
        contam_min_cos: umbral de coseno para considerar contaminación.

    Returns:
        Lista de grupos JSON-safe ordenada por ``(persona_destino, cod_origen)``.
    """
    _, realof, real_clusters = normalizar_etiquetas(etiquetas)
    persons = _persons_map(store)
    matrices = _matrices(persons)
    dst_por_persona = _mejores_por_persona(real_clusters, matrices)

    grupos: dict[tuple[str, str | None], dict] = {}
    for cod in sorted(realof):
        if cod not in matrices or matrices[cod].shape[0] == 0:
            continue
        persona_own = realof[cod]
        E = matrices[cod]
        n = int(E.shape[0])
        best_cos, best_cod = nearest_external(E, cod, realof, matrices)
        srcs = _sources(persons[cod], n)
        for i in range(n):
            cos = float(best_cos[i])
            if not math.isfinite(cos) or cos < float(contam_min_cos):
                continue
            ext = best_cod[i]
            persona_ext = realof.get(ext) if ext is not None else None
            if persona_ext == persona_own:
                continue  # vecino de la misma persona real: no es contaminación
            key = (cod, persona_ext)
            g = grupos.setdefault(key, {
                "cod_origen": cod,
                "persona_destino": persona_ext,
                "destino_cod": dst_por_persona.get(persona_ext) if persona_ext else None,
                "accion": "mover" if (persona_ext and dst_por_persona.get(persona_ext)) else "purgar",
                "encodings": [],
                "sin_fuente": [],
            })
            entry = {
                "idx": int(i),
                "cos": _f(cos),
                "source": srcs[i],
                "vecino_cod": ext,
            }
            g["encodings"].append(entry)
            if srcs[i] is None:
                g["sin_fuente"].append(entry)

    salida: list[dict] = []
    for _key, g in grupos.items():
        g["encodings"].sort(key=lambda e: (e["idx"], str(e["source"])))
        g["sin_fuente"].sort(key=lambda e: e["idx"])
        g["n"] = len(g["encodings"])
        g["n_sin_fuente"] = len(g["sin_fuente"])
        salida.append(g)
    salida.sort(key=lambda g: (g["persona_destino"] or "", g["cod_origen"]))
    return salida


# ---------------------------------------------------------------------------
# Propuesta completa
# ---------------------------------------------------------------------------
def construir_propuesta(
    store: Any,
    etiquetas: Any,
    bloqueados: Any = None,
    merge_min_cos: float = MERGE_MIN_COS_DEFAULT,
    contam_min_cos: float = CONTAM_MIN_COS_DEFAULT,
) -> dict:
    """Construye la propuesta JSON-safe completa (merges + contaminación).

    ``merge_min_cos`` NO filtra: con ground-truth basta agrupar por persona.
    Solo se reporta, por grupo, si su cohesión alcanza el umbral
    (``cohesion_ok``) y en el resumen.
    """
    merges, excluidos = _analizar_merges(store, etiquetas, bloqueados)
    for m in merges:
        cm = m["cohesion"].get("max")
        m["cohesion_ok"] = (cm is not None and float(cm) >= float(merge_min_cos))
    contams = proponer_contaminacion(store, etiquetas, contam_min_cos)

    n_movibles = sum(
        len([e for e in g["encodings"] if e["source"] is not None])
        for g in contams if g["destino_cod"]
    )
    resumen = {
        "merge_min_cos": float(merge_min_cos),
        "contam_min_cos": float(contam_min_cos),
        "n_merges": len(merges),
        "n_encodings_fusionables": int(sum(m["n_encodings"] for m in merges)),
        "n_excluidos": len(excluidos),
        "excluidos": excluidos,
        "n_contaminaciones": len(contams),
        "n_encodings_contaminados": int(sum(g["n"] for g in contams)),
        "n_encodings_movibles": int(n_movibles),
        "n_encodings_sin_fuente": int(sum(g["n_sin_fuente"] for g in contams)),
        "n_encodings_purga": int(sum(g["n"] for g in contams if not g["destino_cod"])),
    }
    return {"merges": merges, "contaminaciones": contams, "resumen": resumen}


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------
def _num(x: Any, dec: int = 3) -> str:
    return "-" if x is None else f"{float(x):.{dec}f}"


def formato_texto(prop: Mapping[str, Any]) -> str:
    """Render legible de la propuesta para la CLI (sin ``--json``)."""
    r = prop.get("resumen", {})
    lineas = [
        "== Propuesta de reparación de identidades (solo lectura) ==",
        f"merges: {r.get('n_merges')} | encodings fusionables: {r.get('n_encodings_fusionables')}"
        f" | excluidos: {r.get('n_excluidos')}",
        f"contaminaciones: {r.get('n_contaminaciones')} | encodings contaminados: {r.get('n_encodings_contaminados')}"
        f" | movibles: {r.get('n_encodings_movibles')} | sin fuente: {r.get('n_encodings_sin_fuente')}"
        f" | purga: {r.get('n_encodings_purga')}",
        "",
        "-- Fusiones (fragmentación) --",
    ]
    for m in prop.get("merges") or []:
        coh = m.get("cohesion") or {}
        lineas.append(
            f"  {m['persona']}: destino={m['destino']} fuentes={m['cods_fuente']} "
            f"({m['n_encodings']} encodings) cohesion max={_num(coh.get('max'))} "
            f"mediana={_num(coh.get('mediana'))} ok={m.get('cohesion_ok')}"
        )
        for e in m.get("excluidos") or []:
            lineas.append(f"      excluido {e['cod']}: {e['motivo']}")
    lineas.append("")
    lineas.append("-- Contaminación --")
    for g in prop.get("contaminaciones") or []:
        lineas.append(
            f"  {g['cod_origen']} -> {g['persona_destino']} (destino={g['destino_cod']}, "
            f"accion={g['accion']}, n={g['n']}, sin_fuente={g['n_sin_fuente']})"
        )
        for e in g.get("encodings") or []:
            lineas.append(
                f"      idx={e['idx']} cos={_num(e['cos'])} vecino={e['vecino_cod']} "
                f"source={e['source']}"
            )
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Propone reparación (fragmentación + contaminación). Solo lee."
    )
    ap.add_argument("--store", required=True, help="ruta al pickle face_enc_v2")
    ap.add_argument("--etiquetas", required=True, help="JSON con id/cod_interno/persona")
    ap.add_argument("--bloqueados", default=None,
                    help="JSON opcional con pares [cod_a, cod_b] que NO se fusionan")
    ap.add_argument("--merge-min-cos", type=float, default=MERGE_MIN_COS_DEFAULT,
                    help="umbral SOLO para reportar cohesión de los grupos")
    ap.add_argument("--contam-min-cos", type=float, default=CONTAM_MIN_COS_DEFAULT,
                    help="coseno mínimo con el vecino externo para marcar contaminación")
    ap.add_argument("--json", action="store_true", help="emitir la propuesta como JSON")
    return ap.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada CLI. Solo lee; nunca escribe el store ni la BD."""
    args = _parse_args(argv)
    store = cargar_store(args.store)
    etiquetas = cargar_etiquetas(args.etiquetas)
    bloqueados = _cargar_bloqueados(args.bloqueados)
    prop = construir_propuesta(
        store, etiquetas, bloqueados,
        merge_min_cos=args.merge_min_cos,
        contam_min_cos=args.contam_min_cos,
    )
    if args.json:
        print(json.dumps(prop, ensure_ascii=False, indent=2))
    else:
        print(formato_texto(prop))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
