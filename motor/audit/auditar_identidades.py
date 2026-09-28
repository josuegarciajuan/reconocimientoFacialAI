"""Analizador read-only de un store ``face_enc_v2`` (Fase 0).

Mide dos patologías observadas en producción:

1. **Fragmentación**: una persona real repartida en varios ``cod_interno``
   (51 identidades para ~8 personas).
2. **Contaminación**: encodings de otra persona dentro de una galería, y
   cods saturados en el tope de ``encodings`` (500).

El módulo es **puro y de solo lectura**: nunca abre el store en modo escritura,
nunca crea ``.lock`` y no muta el diccionario cargado. Todas las funciones de
cálculo se separan de la CLI para poder testearlas sin red ni BD.

Formato del store (pickle)::

    {"version": 4, "schema": "face_enc_v2",
     "persons": {cod: {"encodings": [ndarray(512,) ...],
                       "quality": [float ...], "poses": [str ...],
                       "sources": [str|None ...], ...}}}

Formato del fichero de etiquetas (JSON)::

    [{"id": <int BD>, "cod_interno": "<str>", "persona": "<nombre real>"}, ...]

Puede haber varios ``id`` para el mismo ``cod_interno`` y varios ``cod_interno``
para la misma persona real (justamente la fragmentación que se quiere medir).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import pickle
from collections import defaultdict
from itertools import combinations
from typing import Any, Callable, Iterable, Mapping, Sequence

import numpy as np

SCHEMA = "face_enc_v2"
VERSION = 4

#: Tope de encodings por identidad en el store de producción.
MAX_PER_PERSON_DEFAULT = 500

#: Umbrales de coseno relevantes para el matching (galería videovigilancia).
UMBRALES_FRAGMENTACION = (0.35, 0.48, 0.55)

TOP_IMPOSTORES_DEFAULT = 15

Etiquetas = tuple[dict[int, str], dict[str, str], dict[str, list[str]]]
PersonaDe = Callable[[str], str | None] | Mapping[str, str]


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------
def _store_vacio() -> dict:
    """Devuelve un store vacío con el schema esperado."""
    return {"version": VERSION, "schema": SCHEMA, "persons": {}}


def cargar_store(path: str) -> dict:
    """Carga un store ``face_enc_v2`` **sin modificarlo**.

    Acepta rutas ausentes o ficheros vacíos devolviendo un store vacío. Lanza
    ``ValueError`` si el pickle es de otro schema (para no interpretar mal datos).
    """
    if not path or not os.path.exists(path) or os.path.getsize(path) == 0:
        return _store_vacio()
    with open(path, "rb") as fh:
        data = pickle.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Store inválido (no es dict): {path}")
    if data.get("schema") != SCHEMA:
        raise ValueError(
            f"Store con schema no soportado: {data.get('schema')!r} (se esperaba {SCHEMA!r})"
        )
    if not isinstance(data.get("persons"), dict):
        data = dict(data)
        data["persons"] = {}
    return data


def parsear_etiquetas(raw: Any) -> Etiquetas:
    """Convierte la lista JSON de etiquetas en estructuras de consulta.

    Returns:
        ``(id2cod, realof, real_clusters)`` donde:
            - ``id2cod``: ``{id_bd: cod_interno}``
            - ``realof``: ``{cod_interno: persona_real}``
            - ``real_clusters``: ``{persona_real: [cod_interno, ...]}``

    Entradas sin ``cod_interno`` se ignoran. ``persona`` nula deja el cod sin
    etiqueta (aparece en ``id2cod`` pero no en ``realof``).
    """
    id2cod: dict[int, str] = {}
    realof: dict[str, str] = {}
    if raw is None:
        return id2cod, realof, {}
    if not isinstance(raw, (list, tuple)):
        raise ValueError("El fichero de etiquetas debe ser una lista JSON")
    for item in raw:
        if not isinstance(item, Mapping):
            continue
        cod = item.get("cod_interno")
        if cod is None:
            continue
        cod = str(cod)
        pid = item.get("id")
        if pid is not None:
            try:
                id2cod[int(pid)] = cod
            except (TypeError, ValueError):
                pass
        persona = item.get("persona")
        if persona is not None and str(persona) != "":
            realof[cod] = str(persona)
    real_clusters: dict[str, list[str]] = defaultdict(list)
    for cod, persona in realof.items():
        if cod not in real_clusters[persona]:
            real_clusters[persona].append(cod)
    return id2cod, realof, dict(real_clusters)


def cargar_etiquetas(path: str) -> Etiquetas:
    """Carga un JSON de etiquetas (lista de dicts) y lo normaliza.

    Ruta ausente o vacía -> estructuras vacías (store sin etiquetar).
    """
    if not path or not os.path.exists(path) or os.path.getsize(path) == 0:
        return {}, {}, {}
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    return parsear_etiquetas(raw)


def normalizar_etiquetas(etiquetas: Any) -> Etiquetas:
    """Acepta la tupla ``(id2cod, realof, real_clusters)``, una lista de dicts o None."""
    if etiquetas is None:
        return {}, {}, {}
    if isinstance(etiquetas, (tuple, list)) and len(etiquetas) == 3:
        id2cod, realof, real_clusters = etiquetas
        return (
            dict(id2cod or {}),
            dict(realof or {}),
            dict(real_clusters or {}),
        )
    return parsear_etiquetas(etiquetas)


# ---------------------------------------------------------------------------
# Utilidades numéricas
# ---------------------------------------------------------------------------
def _mat(arr: Any) -> np.ndarray:
    """Normaliza una lista de embeddings a matriz 2-D ``(n, d)`` float64."""
    a = np.asarray(arr, dtype=np.float64)
    if a.size == 0:
        return a.reshape(0, 0)
    if a.ndim == 1:
        a = a.reshape(1, -1)
    return a


def _persona(persona_de: PersonaDe | None, cod: Any) -> str | None:
    """Resuelve la persona real de un cod admitiendo callable o mapping."""
    if cod is None or persona_de is None:
        return None
    if callable(persona_de):
        return persona_de(cod)
    if isinstance(persona_de, Mapping):
        return persona_de.get(cod)
    return None


def _cos_max(A: np.ndarray, B: np.ndarray) -> float | None:
    """Máximo coseno entre dos matrices; ``None`` si son incompatibles/vacías."""
    if A.size == 0 or B.size == 0:
        return None
    if A.shape[1] != B.shape[1]:
        return None
    return float(np.max(A @ B.T))


def _media_intra(A: np.ndarray) -> float | None:
    """Media de los cosenos por pares (off-diagonal) dentro de una galería."""
    n = A.shape[0]
    if n < 2:
        return None
    sims = A @ A.T
    iu = np.triu_indices(n, k=1)
    return float(sims[iu].mean())


def _f(x: Any) -> float | None:
    """Convierte a float JSON-safe (``None`` si no es finito)."""
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


# ---------------------------------------------------------------------------
# Núcleo algorítmico
# ---------------------------------------------------------------------------
def nearest_external(
    encoding_matrix: Any,
    cod: str,
    persona_de: PersonaDe | None,
    matrices_por_cod: Mapping[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    """Vecino más cercano de cada encoding entre los **demás** cods.

    Para cada fila (encoding) de ``encoding_matrix`` calcula el coseno máximo
    contra todos los encodings de cada otro ``cod`` y se queda con el mejor.
    El propio ``cod`` se excluye siempre (no hay auto-match trivial de coseno 1).

    Complejidad: ``O(n_personas)`` productos matriciales, no
    ``O(n_encodings * personas)`` bucles. El bucle Python solo recorre los
    empates exactos (raros) para desempatar a favor de una persona distinta,
    de modo que ``persona_de`` se usa de forma determinista.

    Args:
        encoding_matrix: matriz ``(n, d)`` de encodings (o un vector ``(d,)``).
        cod: cod_interno de la galería consultada (se excluye).
        persona_de: callable/mapping ``cod -> persona_real`` (para el desempate).
        matrices_por_cod: mapping ``cod -> matriz (m, d)`` con todas las galerías.

    Returns:
        ``(best_cos, best_cod)`` con arrays de longitud ``n``. Si no hay ningún
        otro cod, ``best_cos`` queda a ``-inf`` y ``best_cod`` a ``None``.
    """
    E = _mat(encoding_matrix)
    n = E.shape[0]
    best_cos = np.full(n, -np.inf, dtype=np.float64)
    best_cod = np.empty(n, dtype=object)
    best_cod[:] = None
    if n == 0:
        return best_cos, best_cod

    persona_own = _persona(persona_de, cod)
    for other, M in matrices_por_cod.items():
        if other == cod:
            continue
        Mo = _mat(M)
        if Mo.shape[0] == 0 or Mo.shape[1] != E.shape[1]:
            continue
        sims = E @ Mo.T                       # (n, m) vectorizado
        idx = np.argmax(sims, axis=1)
        vals = sims[np.arange(n), idx]
        upd = vals > best_cos
        best_cos[upd] = vals[upd]
        best_cod[upd] = other
        # Desempate determinista: a igualdad de coseno, preferir persona distinta.
        ties = np.nonzero(vals == best_cos)[0]
        for i in ties:
            if (
                _persona(persona_de, best_cod[i]) == persona_own
                and _persona(persona_de, other) != persona_own
            ):
                best_cod[i] = other
    return best_cos, best_cod


def _resumen(persons: Mapping[str, Any], matrices: Mapping[str, np.ndarray],
             realof: Mapping[str, str], max_per_person: int) -> dict:
    n_encodings = int(sum(m.shape[0] for m in matrices.values()))
    n_con_1 = int(sum(1 for m in matrices.values() if m.shape[0] == 1))
    n_en_tope = int(sum(1 for m in matrices.values() if m.shape[0] >= max_per_person))
    n_sin_etiquetar = int(sum(1 for cod in persons if cod not in realof))
    return {
        "n_personas": len(persons),
        "n_encodings_total": n_encodings,
        "n_con_1_encoding": n_con_1,
        "n_en_tope": n_en_tope,
        "max_per_person": int(max_per_person),
        "n_sin_etiquetar": n_sin_etiquetar,
    }


def _por_persona_real(
    matrices: Mapping[str, np.ndarray],
    real_clusters: Mapping[str, Sequence[str]],
    umbrales: Sequence[float],
) -> dict:
    out: dict[str, dict] = {}
    for persona, cods in real_clusters.items():
        presentes = [c for c in cods if c in matrices and matrices[c].shape[0] > 0]
        if not presentes:
            continue
        n_enc = int(sum(matrices[c].shape[0] for c in presentes))
        mejores: list[float] = []
        for a, b in combinations(presentes, 2):
            cos = _cos_max(matrices[a], matrices[b])
            if cos is not None:
                mejores.append(cos)
        mejor = None
        if mejores:
            arr = np.asarray(mejores, dtype=np.float64)
            mejor = {
                "max": _f(arr.max()),
                "min": _f(arr.min()),
                "mediana": _f(np.median(arr)),
            }
        bajo = {str(u): int(sum(1 for c in mejores if c < float(u))) for u in umbrales}
        out[persona] = {
            "n_fragmentos": len(presentes),
            "n_encodings": n_enc,
            "fragmentos": list(presentes),
            "pares": {"n": len(mejores), "mejor_coseno": mejor, "bajo_umbral": bajo},
        }
    return out


def _impostores(
    matrices: Mapping[str, np.ndarray],
    realof: Mapping[str, str],
    top: int,
) -> list[dict]:
    etiquetados = [c for c in matrices if c in realof and matrices[c].shape[0] > 0]
    pares: list[tuple[float, str, str]] = []
    for a, b in combinations(etiquetados, 2):
        if realof[a] == realof[b]:
            continue
        cos = _cos_max(matrices[a], matrices[b])
        if cos is not None:
            pares.append((cos, a, b))
    pares.sort(key=lambda t: t[0], reverse=True)
    return [
        {
            "cod_a": a,
            "cod_b": b,
            "persona_a": realof.get(a),
            "persona_b": realof.get(b),
            "cos": _f(cos),
        }
        for cos, a, b in pares[:top]
    ]


def _higiene_por_cod(
    matrices: Mapping[str, np.ndarray],
    realof: Mapping[str, str],
    max_per_person: int,
) -> dict:
    out: dict[str, dict] = {}
    for cod, M in matrices.items():
        n = int(M.shape[0])
        persona_own = realof.get(cod)
        best_cos, best_cod = nearest_external(M, cod, realof, matrices)
        votos = 0
        if persona_own is not None and n > 0:
            for i in range(n):
                ext = best_cod[i]
                if ext is None:
                    continue
                if realof.get(ext) != persona_own:
                    votos += 1
        vecino = None
        if n > 0 and np.isfinite(best_cos).any():
            j = int(np.argmax(best_cos))
            if best_cod[j] is not None:
                vecino = {
                    "cod": best_cod[j],
                    "persona_real": realof.get(best_cod[j]),
                    "cos": _f(best_cos[j]),
                }
        out[cod] = {
            "n": n,
            "persona_real": persona_own,
            "media_intra": _f(_media_intra(M)),
            "vecino_externo": vecino,
            "votos_contaminacion": votos,
            "en_tope": bool(n >= max_per_person),
        }
    return out


def informe(
    store: Mapping[str, Any],
    etiquetas: Any,
    umbrales: Sequence[float] = UMBRALES_FRAGMENTACION,
    max_per_person: int = MAX_PER_PERSON_DEFAULT,
    top_impostores: int = TOP_IMPOSTORES_DEFAULT,
) -> dict:
    """Construye el informe de fragmentación/contaminación de un store.

    Args:
        store: diccionario ``face_enc_v2`` (ya cargado; no se modifica).
        etiquetas: tupla ``(id2cod, realof, real_clusters)``, lista JSON o None.
        umbrales: umbrales de coseno para contar pares frágiles.
        max_per_person: tope de la galería (para el flag ``en_tope``).
        top_impostores: cuántos pares impostores devolver.

    Returns:
        Dict JSON-safe con ``resumen``, ``por_persona_real``, ``impostores`` y
        ``higiene_por_cod``.
    """
    _, realof, real_clusters = normalizar_etiquetas(etiquetas)
    persons = store.get("persons") or {}
    if not isinstance(persons, Mapping):
        persons = {}
    matrices: dict[str, np.ndarray] = {}
    for cod, p in persons.items():
        encs = p.get("encodings") if isinstance(p, Mapping) else None
        matrices[str(cod)] = _mat(encs if encs is not None else [])
    return {
        "resumen": _resumen(persons, matrices, realof, max_per_person),
        "por_persona_real": _por_persona_real(matrices, real_clusters, umbrales),
        "impostores": _impostores(matrices, realof, top_impostores),
        "higiene_por_cod": _higiene_por_cod(matrices, realof, max_per_person),
    }


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------
def _num(x: Any, dec: int = 3) -> str:
    """Formatea un float del informe, tolerando ``None``."""
    return "-" if x is None else f"{float(x):.{dec}f}"


def formato_texto(inf: Mapping[str, Any]) -> str:
    """Render legible del informe para la CLI (sin flag ``--json``)."""
    r = inf.get("resumen", {})
    lineas = [
        "== Auditoría de identidades (face_enc_v2) ==",
        f"personas (cods): {r.get('n_personas')}  |  encodings: {r.get('n_encodings_total')}",
        f"con 1 encoding: {r.get('n_con_1_encoding')}  |  en tope ({r.get('max_per_person')}): {r.get('n_en_tope')}",
        f"cods sin etiquetar: {r.get('n_sin_etiquetar')}",
        "",
        "-- Por persona real --",
    ]
    for persona, d in (inf.get("por_persona_real") or {}).items():
        pares = d.get("pares", {})
        mejor = pares.get("mejor_coseno") or {}
        lineas.append(
            f"  {persona}: {d['n_fragmentos']} fragmentos / {d['n_encodings']} encodings | "
            f"pares={pares.get('n')}"
        )
        if mejor:
            lineas.append(
                f"      mejor cos: max={_num(mejor.get('max'))} min={_num(mejor.get('min'))} "
                f"mediana={_num(mejor.get('mediana'))}"
            )
        lineas.append(f"      pares bajo umbral: {pares.get('bajo_umbral')}")
    lineas.append("")
    lineas.append("-- Top impostores (personas reales distintas) --")
    for it in inf.get("impostores") or []:
        lineas.append(
            f"  {_num(it['cos'])}  {it['persona_a']}({it['cod_a']}) <-> "
            f"{it['persona_b']}({it['cod_b']})"
        )
    lineas.append("")
    lineas.append("-- Higiene por cod --")
    for cod, d in (inf.get("higiene_por_cod") or {}).items():
        v = d.get("vecino_externo")
        vs = "-" if v is None else f"{v['cod']}/{v['persona_real']}@{_num(v['cos'])}"
        mi = d.get("media_intra")
        mi_s = _num(mi)
        flag = " [TOPE]" if d.get("en_tope") else ""
        lineas.append(
            f"  {cod}{flag}: n={d['n']} intra={mi_s} externo={vs} "
            f"votos_contaminacion={d['votos_contaminacion']}"
        )
    return "\n".join(lineas)


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Auditoría read-only de identidades de un store face_enc_v2."
    )
    ap.add_argument("--store", required=True, help="ruta al pickle face_enc_v2")
    ap.add_argument("--etiquetas", required=True, help="JSON con id/cod_interno/persona")
    ap.add_argument("--json", action="store_true", help="emitir el informe como JSON")
    return ap.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada CLI. Solo lee; nunca escribe el store."""
    args = _parse_args(argv)
    store = cargar_store(args.store)
    etiquetas = cargar_etiquetas(args.etiquetas)
    inf = informe(store, etiquetas)
    if args.json:
        print(json.dumps(inf, ensure_ascii=False, indent=2))
    else:
        print(formato_texto(inf))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
