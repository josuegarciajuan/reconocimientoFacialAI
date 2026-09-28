"""Calibración fina de SCORING y UMBRALES sobre una muestra real etiquetada (solo lectura).

Experimento de solo lectura sobre las fotos publicadas en
``admin/caras_procesadas/`` que ya están etiquetadas con una persona real. El
problema a resolver: con el scoring actual (una única similitud coseno sobre el
embedding nativo) el coseno genuino (misma persona, distinto fragmento) y el
impostor (persona distinta) se **solapan** (p. ej. mediana genuina ~0.394 vs
impostor ~0.292). La pregunta es si alguna variante de scoring (TTA por espejo,
top-k, centroide) y algún umbral separan la muestra.

Diseño **leave-one-fragment-out (LOFO)**:

1. Se seleccionan fotos etiquetadas con reparto round-robin por ``persona_id``
   (cap ``--max-por-persona``) para no sesgar hacia identidades con muchas fotos.
2. Por foto se calcula, de forma perezosa y **sin escribir nada**:
   - embedding nativo (``analyze`` sobre la imagen),
   - embedding volteado (``analyze`` sobre ``cv2.flip(img, 1)``), para TTA,
   - metadatos: lado de cara, nitidez, pose y ``pose_valida``.
3. Para cada persona real ``P`` y cada fragmento ``F`` (``persona_id``) de ``P``,
   la galería de ``P`` son las fotos de ``P`` con fragmento ``!= F``; las fotos
   de ``F`` son las queries. Ninguna foto de la query está en su galería.
4. Por query se calculan seis variantes de score contra la galería de CADA
   persona real (ver :func:`score_variantes`). El ``top-1`` es la persona de
   mayor score y decide TAR/FAR en el barrido de umbrales.

Variantes de scoring (funciones puras):

- ``max``         : ``max_i cos(q, g_i)``
- ``top3mean``    : media de los 3 mejores ``cos(q, g_i)``
- ``centroid``    : ``cos(q, normalize(mean_i g_i))``
- ``flipmax``     : TTA query: ``max(max_i cos(q,g_i), max_i cos(q_flip,g_i))``
- ``fliptop3``    : media top-3 con TTA query (máximo por elemento de galería)
- ``flipcentroid``: ``cos(normalize(q+q_flip), normalize(mean(G)))``

Se incluye además, **marcado aparte y sin entrar en la variante ganadora**, un
diagnóstico etiquetado ``medoidmax = max_own - mean_top_otras`` (usa las
etiquetas reales; no es una función de inferencia).

Métricas por umbral (fracciones sobre las queries evaluables ``n``):

- ``TAR`` = queries cuyo top-1 es la persona correcta Y su score ``>= umbral`` / n
- ``FAR`` = queries cuyo top-1 es una persona incorrecta Y su score ``>= umbral`` / n
- ``FRR`` = ``1 - TAR``

El módulo **no escribe nada**: solo hace ``SELECT`` (lectura de BD vía
``medir_banco.construir_fotos``), lee imágenes y usa el modelo con imports
perezosos (es importable y testeable sin cv2, insightface, BD ni red).

Uso::

    motor/venv/bin/python -m motor.audit.calibrar_fino \\
        --local 1 --ruta /root/reconocimientoFacial \\
        --etiquetas /ruta/etiquetas.json --max-por-persona 40 --json

La parte pura (:func:`score_variantes`, :func:`metricas_umbral`,
:func:`evaluar_medidas`, :func:`resumir`, :func:`elegir_youden`,
:func:`elegir_far_max`) no toca BD, red ni modelos y se testea con embeddings
sintéticos.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from typing import Any, Mapping, Sequence

import numpy as np

from ..core.config import Config
from .auditar_identidades import cargar_etiquetas
from .medir_banco import RAIZ, _f, construir_fotos
from .verificar_cara_a_cara import _norm, _pct, _stats, limitar_por_persona

VERSION = 1

DEFAULT_MAX_POR_PERSONA = 40
DEFAULT_DET_SIZE = 640
DEFAULT_UMBRAL_MIN = 0.20
DEFAULT_UMBRAL_MAX = 0.70
DEFAULT_PASO = 0.01

#: Tope de FAR del punto "operativo" (mismo criterio que ``medir_banco``).
FAR_MAX_OBJETIVO = 0.05
#: TAR objetivo del mejor punto con far<=FAR_MAX_OBJETIVO.
TAR_OBJETIVO = 0.90
#: Nº de vecinos para las medias top-k.
TOP_K = 3
#: Nº de identidades ajenas para el diagnóstico ``medoidmax``.
MEAN_OTRAS_K = 3

#: Orden canónico de las variantes de scoring (determinista en informes).
VARIANTES = ("max", "top3mean", "centroid", "flipmax", "fliptop3", "flipcentroid")

DESCRIPCIONES = {
    "max": "max_i cos(q, g_i)",
    "top3mean": "media de los 3 mejores cos(q, g_i)",
    "centroid": "cos(q, normalize(mean_i g_i))",
    "flipmax": "TTA query: max(max_i cos(q,g_i), max_i cos(q_flip,g_i))",
    "fliptop3": "media top-3 con TTA query (max por elemento de galeria)",
    "flipcentroid": "cos(normalize(q+q_flip), normalize(mean(G)))",
}


# ---------------------------------------------------------------------------
# Utilidades numéricas puras
# ---------------------------------------------------------------------------
def _a_matriz(vecs: Any) -> np.ndarray:
    """Convierte una galería en matriz ``(n, d)`` con cada fila L2-normalizada.

    Acepta una secuencia de vectores o un array 2-D/1-D. Lista vacía -> ``(0, 0)``.
    """
    a = np.asarray(vecs, dtype=np.float64)
    if a.size == 0:
        return a.reshape(0, 0)
    if a.ndim == 1:
        a = a.reshape(1, -1)
    n = np.linalg.norm(a, axis=1, keepdims=True)
    n[n <= 0.0] = 1.0
    return a / n


def _cos(a: np.ndarray, b: np.ndarray) -> float:
    """Coseno entre dos vectores ya normalizados (``-1.0`` si no son comparables)."""
    if a.shape != b.shape:
        return -1.0
    return float(np.dot(a, b))


def _centroide(M: np.ndarray) -> np.ndarray:
    """Centroide normalizado (media de las filas) de una matriz ``(n, d)``."""
    if M.shape[0] == 0:
        return np.zeros(M.shape[1] if M.ndim == 2 else 0, dtype=np.float64)
    return _norm(M.mean(axis=0))


def _media_topk(sims: np.ndarray, k: int = TOP_K) -> float:
    """Media de los ``k`` mayores cosenos (``min(k, n)`` si hay menos; ``-1.0`` si vacío)."""
    if sims.size == 0:
        return -1.0
    kk = max(1, min(int(k), int(sims.size)))
    top = np.sort(np.asarray(sims, dtype=np.float64))[::-1][:kk]
    return float(top.mean())


def _flip_de(m: Mapping[str, Any]) -> Any:
    """Embedding volteado de una medida (cae al nativo si no hay espejo)."""
    f = m.get("flip")
    return m.get("embedding") if f is None else f


def rango_umbrales(umin: float, umax: float, paso: float) -> list[float]:
    """Barrido de umbrales ``[umin, umin+paso, ..., umax]`` (redondeado a 6 decimales).

    ``paso <= 0`` o rango invertido -> lista vacía. Se incluye ``umax`` cuando
    cae en la rejilla (con redondeo para evitar ruido de coma flotante).
    """
    try:
        lo, hi, step = float(umin), float(umax), float(paso)
    except (TypeError, ValueError):
        return []
    if step <= 0.0 or hi < lo:
        return []
    n = int(round((hi - lo) / step))
    out = [round(lo + i * step, 6) for i in range(n + 1)]
    if out and out[-1] < hi and abs(out[-1] - hi) < step * 0.5:
        out[-1] = round(hi, 6)
    return out


# ---------------------------------------------------------------------------
# Núcleo puro: variantes de scoring
# ---------------------------------------------------------------------------
def score_variantes(
    q_vec: Any,
    q_flip: Any,
    G: Any,
    G_flip: Any = None,
) -> dict[str, float]:
    """Calcula las seis variantes de score de una query contra UNA galería.

    Args:
        q_vec: embedding nativo de la query.
        q_flip: embedding de la query sobre la imagen espejo (``None`` desactiva
            la TTA de query: las variantes ``flip*`` degeneran a sus pares sin
            espejo).
        G: matriz ``(n, d)`` de la galería (embedding nativo de cada miembro).
        G_flip: matriz ``(n, d)`` de la galería volteada. Se acepta por la API
            requerida pero las seis variantes de esta función usan TTA **solo de
            query** (la galería limpia no se aumenta); el argumento queda
            reservado para variantes simétricas futuras.

    Returns:
        ``{variante: score}``. Si la galería está vacía o la dimensión no
        coincide con la query, todas las variantes valen ``-1.0``.
    """
    q = _norm(q_vec)
    M = _a_matriz(G)
    vacio = {v: -1.0 for v in VARIANTES}
    if M.shape[0] == 0 or M.shape[1] != q.shape[0]:
        return vacio
    sims_q = M @ q
    qf: np.ndarray | None = None
    if q_flip is not None:
        cand = _norm(q_flip)
        if cand.shape[0] == q.shape[0]:
            qf = cand

    out: dict[str, float] = {
        "max": float(sims_q.max()),
        "top3mean": _media_topk(sims_q, TOP_K),
        "centroid": _cos(q, _centroide(M)),
    }
    if qf is not None:
        sims_tta = np.maximum(sims_q, M @ qf)  # TTA por elemento de galería
        q_tta = _norm(q + qf)
    else:
        sims_tta = sims_q
        q_tta = q
    out["flipmax"] = float(sims_tta.max())
    out["fliptop3"] = _media_topk(sims_tta, TOP_K)
    out["flipcentroid"] = _cos(q_tta, _centroide(M))
    return out


# ---------------------------------------------------------------------------
# Núcleo puro: barrido de umbrales y elección de puntos
# ---------------------------------------------------------------------------
def metricas_umbral(
    top1_correcto: Sequence[bool],
    top1_scores: Sequence[float],
    umbrales: Sequence[float],
) -> dict[float, dict]:
    """TAR/FAR/FRR por umbral a partir del top-1 de cada query.

    Args:
        top1_correcto: ``top1 == persona_real`` por query.
        top1_scores: score del top-1 por query (mismo orden).
        umbrales: umbrales de coseno a barrer.

    Returns:
        ``{umbral: {tar, far, frr, n_aciertos, n_falsos, n_queries}}``. Con 0
        queries las métricas quedan a ``None`` (sin datos).
    """
    n = len(top1_scores)
    out: dict[float, dict] = {}
    for u in umbrales:
        uf = float(u)
        if n == 0:
            out[uf] = {"tar": None, "far": None, "frr": None,
                       "n_aciertos": 0, "n_falsos": 0, "n_queries": 0}
            continue
        aciertos = 0
        falsos = 0
        for ok, s in zip(top1_correcto, top1_scores):
            if s is None or not np.isfinite(float(s)):
                continue
            if float(s) < uf:
                continue
            if ok:
                aciertos += 1
            else:
                falsos += 1
        tar = aciertos / n
        far = falsos / n
        out[uf] = {
            "tar": _f(tar),
            "far": _f(far),
            "frr": _f(1.0 - tar),
            "n_aciertos": aciertos,
            "n_falsos": falsos,
            "n_queries": n,
        }
    return out


def elegir_youden(puntos: Mapping[float, Mapping[str, Any]]) -> dict | None:
    """Punto de mayor ``J = TAR - FAR`` (empate: umbral más alto, más conservador)."""
    mejor: dict | None = None
    mejor_key: tuple[float, float] | None = None
    for u, d in puntos.items():
        tar, far = d.get("tar"), d.get("far")
        if tar is None or far is None:
            continue
        j = float(tar) - float(far)
        key = (j, float(u))
        if mejor_key is None or key > mejor_key:
            mejor_key = key
            mejor = {"umbral": float(u), "tar": _f(tar), "far": _f(far), "j": _f(j)}
    return mejor


def elegir_far_max(
    puntos: Mapping[float, Mapping[str, Any]],
    far_max: float = FAR_MAX_OBJETIVO,
    tar_min: float | None = None,
) -> dict | None:
    """Mejor punto con ``far <= far_max`` (y ``tar >= tar_min`` si se exige).

    Maximiza TAR; empate -> menor FAR; empate -> umbral más alto (más conservador).
    Devuelve ``None`` si ningún umbral cumple.
    """
    mejor: dict | None = None
    mejor_key: tuple[float, float, float] | None = None
    for u, d in puntos.items():
        tar, far = d.get("tar"), d.get("far")
        if tar is None or far is None:
            continue
        if float(far) > float(far_max):
            continue
        if tar_min is not None and float(tar) < float(tar_min):
            continue
        key = (float(tar), -float(far), float(u))
        if mejor_key is None or key > mejor_key:
            mejor_key = key
            mejor = {"umbral": float(u), "tar": _f(tar), "far": _f(far)}
    return mejor


# ---------------------------------------------------------------------------
# Núcleo puro: evaluación LOFO sobre medidas en memoria
# ---------------------------------------------------------------------------
def evaluar_medidas(
    medidas: Sequence[Mapping[str, Any]],
) -> tuple[list[dict], int]:
    """Evalúa cada foto como query contra las galerías LOFO de todas las personas.

    Args:
        medidas: secuencia de dicts con ``persona_real``, ``fragmento``
            (``persona_id``), ``embedding``, ``flip`` y metadatos opcionales.

    Returns:
        ``(resultados, n_no_evaluables)``. Un resultado por query evaluable:

        - ``scores``: por variante, ``{genuino, impostor, top1, top1_score,
          top1_correcto}``, donde ``genuino`` es el score contra la galería LOFO
          de su propia persona e ``impostor`` el mayor score contra las demás.
        - ``medoidmax``: diagnóstico etiquetado ``max_own - mean_top_otras``
          (``None`` si no hay otras identidades).
    """
    por_persona: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for m in medidas:
        p = m.get("persona_real")
        if p is None:
            continue
        por_persona[str(p)].append(m)

    matrices: dict[str, np.ndarray] = {}
    matrices_flip: dict[str, np.ndarray] = {}
    for p, ms in por_persona.items():
        matrices[p] = _a_matriz([m.get("embedding") for m in ms])
        matrices_flip[p] = _a_matriz([_flip_de(m) for m in ms])

    resultados: list[dict] = []
    n_no_evaluables = 0
    for persona, ms in por_persona.items():
        for m in ms:
            frag = str(m.get("fragmento"))
            idx = [j for j, x in enumerate(ms) if str(x.get("fragmento")) != frag]
            if not idx:
                n_no_evaluables += 1
                continue
            q = m.get("embedding")
            qf = _flip_de(m)
            sv: dict[str, dict[str, float]] = {v: {} for v in VARIANTES}
            for p, ms_p in por_persona.items():
                if p == persona:
                    G = matrices[p][idx]
                    Gf = matrices_flip[p][idx]
                else:
                    G = matrices[p]
                    Gf = matrices_flip[p]
                sc = score_variantes(q, qf, G, Gf)
                for v, val in sc.items():
                    sv[v][p] = val

            per: dict[str, dict] = {}
            for v in VARIANTES:
                scores = sv[v]
                own = scores.get(persona)
                otros = [val for p, val in scores.items() if p != persona]
                imp = max(otros) if otros else None
                if scores:
                    top1 = max(scores, key=lambda p: scores[p])
                    top1_score = float(scores[top1])
                else:
                    top1 = None
                    top1_score = -1.0
                per[v] = {
                    "genuino": _f(own),
                    "impostor": _f(imp),
                    "top1": top1,
                    "top1_score": _f(top1_score),
                    "top1_correcto": bool(top1 == persona),
                }

            base = sv["max"]
            own_m = base.get(persona)
            otras = sorted(
                (val for p, val in base.items() if p != persona), reverse=True
            )[:MEAN_OTRAS_K]
            medoid = None
            if own_m is not None and otras:
                medoid = _f(float(own_m) - float(np.mean(otras)))

            resultados.append({
                "persona_real": persona,
                "fragmento": frag,
                "foto_id": m.get("foto_id"),
                "lado_cara": m.get("lado_cara"),
                "sharpness": m.get("sharpness"),
                "pose": m.get("pose"),
                "pose_valida": m.get("pose_valida"),
                "medoidmax": medoid,
                "scores": per,
            })
    return resultados, n_no_evaluables


def _elegir_ganadora(por_variante: Mapping[str, Mapping[str, Any]]) -> str | None:
    """Variante de mayor J en su umbral Youden (empates: menor FAR, mayor TAR)."""
    mejor: str | None = None
    mejor_key: tuple[float, float, float] | None = None
    for v in VARIANTES:
        y = por_variante.get(v, {}).get("umbral_youden")
        if not y:
            continue
        key = (float(y["j"]), -float(y["far"]), float(y["tar"]))
        if mejor_key is None or key > mejor_key:
            mejor_key = key
            mejor = v
    return mejor


def _mejor_tar_objetivo(
    por_variante: Mapping[str, Mapping[str, Any]],
) -> dict | None:
    """Mejor punto con ``far<=FAR_MAX_OBJETIVO`` y ``tar>=TAR_OBJETIVO`` en cualquier variante."""
    mejor: dict | None = None
    mejor_key: tuple[float, float] | None = None
    for v in VARIANTES:
        p = por_variante.get(v, {}).get("punto_tar_objetivo")
        if not p:
            continue
        key = (float(p["tar"]), -float(p["far"]))
        if mejor_key is None or key > mejor_key:
            mejor_key = key
            mejor = {"variante": v, **p}
    return mejor


def resumir(
    resultados: Sequence[Mapping[str, Any]],
    umbrales: Sequence[float],
    far_max: float = FAR_MAX_OBJETIVO,
    tar_objetivo: float = TAR_OBJETIVO,
) -> dict:
    """Informe agregado: curvas por variante, ganadora, TAR por persona y fallos.

    Args:
        resultados: salida de :func:`evaluar_medidas`.
        umbrales: umbrales a barrer.
        far_max: tope de FAR del punto operativo.
        tar_objetivo: TAR objetivo a comprobar con ``far<=far_max``.

    Returns:
        Dict JSON-safe (sin embeddings): ``por_variante``, ``ganadora``,
        ``hay_tar090_far005``, ``por_persona_real``, ``queries_fallidas``,
        ``diagnostico_etiquetado`` y ``n_queries``.
    """
    por_variante: dict[str, dict] = {}
    for v in VARIANTES:
        top1_ok = [bool(r["scores"][v]["top1_correcto"]) for r in resultados]
        top1_scores = [float(r["scores"][v]["top1_score"]) for r in resultados]
        puntos = metricas_umbral(top1_ok, top1_scores, umbrales)
        for _u, d in puntos.items():
            if d.get("tar") is not None and d.get("far") is not None:
                d["j"] = _f(float(d["tar"]) - float(d["far"]))
            else:
                d["j"] = None
        por_variante[v] = {
            "descripcion": DESCRIPCIONES[v],
            "umbral_youden": elegir_youden(puntos),
            "far_max": float(far_max),
            "punto_far_max": elegir_far_max(puntos, far_max),
            "punto_tar_objetivo": elegir_far_max(puntos, far_max, tar_objetivo),
            "distribucion": {
                "genuino": _stats([r["scores"][v]["genuino"] for r in resultados]),
                "impostor": _stats([r["scores"][v]["impostor"] for r in resultados]),
            },
            "curva": puntos,
        }

    ganadora = _elegir_ganadora(por_variante)
    mejor_tar = _mejor_tar_objetivo(por_variante)
    hay_tar090 = {"existe": mejor_tar is not None, "far_max": float(far_max),
                  "tar_objetivo": float(tar_objetivo)}
    if mejor_tar is not None:
        hay_tar090.update(mejor_tar)

    por_persona: dict[str, dict] = {}
    fallidas: list[dict] = []
    if ganadora is not None:
        umbral_gan = float(por_variante[ganadora]["umbral_youden"]["umbral"])
        grupos: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for r in resultados:
            grupos[str(r["persona_real"])].append(r)
        for p, rs in grupos.items():
            aciertos = sum(
                1 for r in rs
                if r["scores"][ganadora]["top1_correcto"]
                and float(r["scores"][ganadora]["top1_score"]) >= umbral_gan
            )
            por_persona[p] = {
                "n_queries": len(rs),
                "n_aciertos": aciertos,
                "tar": _pct(aciertos, len(rs)),
            }
        for r in resultados:
            s = r["scores"][ganadora]
            ok = bool(s["top1_correcto"]) and float(s["top1_score"]) >= umbral_gan
            if ok:
                continue
            fallidas.append({
                "persona_real": r["persona_real"],
                "fragmento": r["fragmento"],
                "foto_id": r["foto_id"],
                "motivo": "top1_incorrecto" if not s["top1_correcto"]
                          else "score_bajo_umbral",
                "score_genuino": s["genuino"],
                "mejor_impostor": s["impostor"],
                "top1": s["top1"],
                "score_top1": s["top1_score"],
                "umbral": umbral_gan,
                "lado_cara": r.get("lado_cara"),
                "pose": r.get("pose"),
                "pose_valida": r.get("pose_valida"),
            })
        fallidas.sort(key=lambda x: (
            str(x["motivo"]),
            -(float(x["score_genuino"]) if x["score_genuino"] is not None else -2.0),
        ))

    meds = [r.get("medoidmax") for r in resultados]
    diagnostico = {
        "medoidmax": {
            "descripcion": ("max_own - media de los top-3 cosenos de OTRAS "
                            "identidades; usa etiquetas, SOLO diagnostico "
                            "(no entra en la variante ganadora)"),
            "usa_etiquetas": True,
            "stats": _stats(meds),
            "n_positivos": sum(1 for x in meds if x is not None and float(x) > 0.0),
        }
    }

    return {
        "n_queries": len(resultados),
        "variantes": list(VARIANTES),
        "por_variante": por_variante,
        "ganadora": ganadora,
        "hay_tar090_far005": hay_tar090,
        "por_persona_real": por_persona,
        "queries_fallidas": fallidas,
        "diagnostico_etiquetado": diagnostico,
    }


# ---------------------------------------------------------------------------
# Medición (impuro: imágenes, modelo)
# ---------------------------------------------------------------------------
def medir_fotos(
    fotos: Sequence[Mapping[str, Any]],
    cfg: Config,
    det_size: int,
    verbose: bool = True,
) -> tuple[list[dict], dict]:
    """Mide embedding nativo + espejo y metadatos de cada foto publicada.

    Elige la cara de mayor ``det_score`` de la imagen y la de su espejo
    (``cv2.flip(img, 1)``); si el espejo no detecta cara, cae al embedding nativo
    (cuenta en ``n_flip_fallback``). Imports perezosos (cv2, modelo, calidad).

    Returns:
        ``(medidas, contadores)``. Cada medida trae ``embedding``, ``flip``,
        ``lado_cara``, ``sharpness``, ``yaw``/``pitch``/``roll``, ``pose``,
        ``pose_valida`` y ``det_score``.
    """
    import cv2  # import perezoso: el módulo es importable sin cv2 real

    from ..core.model import analyze
    from ..core.quality import face_sharpness, pose_label, pose_valida

    min_score = float(getattr(cfg, "min_det_score", 0.4))
    medidas: list[dict] = []
    contadores = {
        "n_leidas": 0,
        "n_sin_imagen": 0,
        "n_sin_cara": 0,
        "n_flip_fallback": 0,
    }
    total = len(fotos)
    for i, foto in enumerate(fotos, 1):
        img = cv2.imread(str(foto.get("ruta")))
        if img is None:
            contadores["n_sin_imagen"] += 1
            continue
        contadores["n_leidas"] += 1
        caras = analyze(img, det_size=(det_size, det_size), min_score=min_score)
        if not caras:
            contadores["n_sin_cara"] += 1
            continue
        cara = max(caras, key=lambda c: float(c.det_score))

        caras_f = analyze(cv2.flip(img, 1), det_size=(det_size, det_size),
                          min_score=min_score)
        if caras_f:
            emb_flip = max(caras_f, key=lambda c: float(c.det_score)).embedding
        else:
            emb_flip = cara.embedding
            contadores["n_flip_fallback"] += 1

        fw = int(cara.bbox[2]) - int(cara.bbox[0])
        fh = int(cara.bbox[3]) - int(cara.bbox[1])
        medidas.append({
            "foto_id": foto.get("foto_id"),
            "persona_real": foto.get("persona_real"),
            "fragmento": str(foto.get("persona_id")),
            "persona_id": foto.get("persona_id"),
            "cod_interno": foto.get("cod_interno"),
            "cam": foto.get("cam"),
            "ts": foto.get("ts"),
            "ruta": foto.get("ruta"),
            "embedding": cara.embedding,
            "flip": emb_flip,
            "lado_cara": max(fw, fh),
            "sharpness": _f(face_sharpness(img, cara)),
            "yaw": _f(cara.yaw),
            "pitch": _f(cara.pitch),
            "roll": _f(cara.roll),
            "pose": pose_label(cara, cfg.yaw_frontal, cfg.yaw_45, cfg.yaw_90,
                               cfg.pitch_frontal),
            "pose_valida": bool(pose_valida(cara, cfg)),
            "det_score": _f(cara.det_score),
        })
        if verbose and (i % 10 == 0 or i == total):
            print(f"  [calibrar] {i}/{total} fotos", file=sys.stderr, flush=True)
    return medidas, contadores


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------
def _num(x: Any, dec: int = 3) -> str:
    """Formatea un float tolerando ``None``."""
    return "-" if x is None else f"{float(x):.{dec}f}"


def _pt_str(p: Mapping[str, Any] | None) -> str:
    """Formatea un punto de umbral (umbral/TAR/FAR) tolerando ``None``."""
    if not p:
        return "-"
    return (f"u={_num(p.get('umbral'), 2)} TAR={_num(p.get('tar'))} "
            f"FAR={_num(p.get('far'))}")


def formato_texto(salida: Mapping[str, Any]) -> str:
    """Render legible del informe (sin flag ``--json``)."""
    p = salida.get("parametros", {})
    m = salida.get("muestreo", {})
    inf = salida.get("informe", {})
    lineas = [
        "== Calibración fina de scoring y umbrales (LOFO, solo lectura) ==",
        f"local={p.get('local')}  etiquetas={p.get('etiquetas')}",
        f"max_por_persona={p.get('max_por_persona')}  det_size={p.get('det_size')}  "
        f"umbrales=[{p.get('umbral_min')}..{p.get('umbral_max')}] paso={p.get('paso')}",
        "",
        "-- Muestreo --",
        f"filas BD: {m.get('n_filas')}  con fichero: {m.get('n_con_fichero')}  "
        f"sin fichero: {m.get('n_sin_fichero')}  sin etiqueta: {m.get('n_sin_etiqueta')}",
        f"seleccionadas: {m.get('n_seleccionadas')}  medidas: {m.get('n_medidas')}  "
        f"sin imagen: {m.get('n_sin_imagen')}  sin cara: {m.get('n_sin_cara')}  "
        f"flip fallback: {m.get('n_flip_fallback')}",
        f"personas reales: {m.get('n_personas_reales')}  "
        f"con >=2 fragmentos: {m.get('n_personas_multi_fragmento')}  "
        f"queries: {m.get('n_queries_total')}  evaluables: {m.get('n_queries_evaluables')}",
        "",
        "-- Variantes (Youden J = TAR-FAR) --",
        "variante         umbral   TAR    FAR     J    | FAR<=0.05: punto | gen(med) imp(med)",
    ]
    for v in inf.get("variantes", []):
        d = inf.get("por_variante", {}).get(v, {})
        y = d.get("umbral_youden") or {}
        dist = d.get("distribucion", {})
        g = dist.get("genuino", {})
        i = dist.get("impostor", {})
        lineas.append(
            f"  {v:<13} {_num(y.get('umbral'), 2):>5} {_num(y.get('tar')):>6} "
            f"{_num(y.get('far')):>6} {_num(y.get('j')):>6}  | "
            f"{_pt_str(d.get('punto_far_max')):<34} | "
            f"{_num(g.get('mediana'))} {_num(i.get('mediana'))}"
        )
    gan = inf.get("ganadora")
    lineas += ["", "-- Ganadora --"]
    if gan:
        yg = inf.get("por_variante", {}).get(gan, {}).get("umbral_youden") or {}
        lineas.append(
            f"  {gan}: {_pt_str(yg)} J={_num(yg.get('j'))} "
            f"(umbral con mayor J, no necesariamente el operativo)"
        )
    else:
        lineas.append("  (sin variante ganadora: no hay queries evaluables)")
    hay = inf.get("hay_tar090_far005") or {}
    if hay.get("existe"):
        lineas.append(
            f"  FAR<=0.05 y TAR>=0.90: SÍ -> {hay.get('variante')} "
            f"{_pt_str(hay)}"
        )
    else:
        lineas.append("  FAR<=0.05 y TAR>=0.90: NO existe en ninguna variante/umbral")

    lineas += ["", "-- TAR por persona real (ganadora) --"]
    for persona, d in (inf.get("por_persona_real") or {}).items():
        lineas.append(
            f"  {persona}: {d.get('n_aciertos')}/{d.get('n_queries')} "
            f"= {_pct_s(d.get('tar'))}"
        )
    lineas += ["", f"-- Queries que fallan (ganadora, {len(inf.get('queries_fallidas') or [])}) --"]
    for q in (inf.get("queries_fallidas") or [])[:30]:
        lineas.append(
            f"  [{q.get('motivo')}] {q.get('persona_real')}/{q.get('fragmento')} "
            f"{q.get('foto_id')}: gen={_num(q.get('score_genuino'))} "
            f"imp={_num(q.get('mejor_impostor'))} top1={q.get('top1')} "
            f"score={_num(q.get('score_top1'))}"
        )
    diag = (inf.get("diagnostico_etiquetado") or {}).get("medoidmax", {})
    st = diag.get("stats", {})
    lineas += [
        "",
        "-- Diagnóstico etiquetado (no entra en la ganadora) --",
        f"  medoidmax: n={st.get('n')} mediana={_num(st.get('mediana'))} "
        f"p10={_num(st.get('p10'))} p90={_num(st.get('p90'))} "
        f"positivos={diag.get('n_positivos')}",
    ]
    for aviso in salida.get("avisos") or []:
        lineas.append(f"AVISO: {aviso}")
    return "\n".join(lineas)


def _pct_s(x: Any) -> str:
    """Formatea una fracción 0-1 como porcentaje tolerando ``None``."""
    return "-" if x is None else f"{100.0 * float(x):.1f}%"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Calibración fina de variantes de scoring y umbrales sobre "
                    "una muestra real etiquetada (leave-one-fragment-out, solo lectura)."
    )
    ap.add_argument("--local", type=int, default=1, help="sala/local_id (def. 1)")
    ap.add_argument("--ruta", default=RAIZ, help="raíz del repo (def. padre de motor/)")
    ap.add_argument("--etiquetas", required=True, help="JSON con id/cod_interno/persona")
    ap.add_argument("--max-por-persona", type=int, default=DEFAULT_MAX_POR_PERSONA,
                    help="cap de fotos por persona real (round-robin, def. 40)")
    ap.add_argument("--det-size", type=int, default=DEFAULT_DET_SIZE,
                    help="tamaño de detección de insightface (def. 640)")
    ap.add_argument("--umbral-min", type=float, default=DEFAULT_UMBRAL_MIN,
                    help="umbral mínimo del barrido (def. 0.20)")
    ap.add_argument("--umbral-max", type=float, default=DEFAULT_UMBRAL_MAX,
                    help="umbral máximo del barrido (def. 0.70)")
    ap.add_argument("--paso", type=float, default=DEFAULT_PASO,
                    help="paso del barrido de umbrales (def. 0.01)")
    ap.add_argument("--json", action="store_true", help="emitir el informe como JSON")
    return ap.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada CLI. Solo lee (SELECT, ficheros, modelo); no escribe nada."""
    args = _parse_args(argv)
    avisos: list[str] = []

    etiquetas = cargar_etiquetas(args.etiquetas)
    id2cod, realof, _ = etiquetas
    if not id2cod and not realof:
        print(f"ERROR: fichero de etiquetas vacío o ausente: {args.etiquetas}",
              file=sys.stderr)
        return 1

    try:
        fotos, n_sin_fichero, n_filas = construir_fotos(args.ruta, int(args.local))
    except RuntimeError as e:  # mysql CLI ausente, credenciales mal, BD caída...
        print(f"ERROR: no se pudo consultar MySQL: {e}", file=sys.stderr)
        return 1
    if not fotos:
        print("ERROR: no hay fotos publicadas con fichero en "
              f"admin/caras_procesadas/ (local={args.local}, filas BD={n_filas}).",
              file=sys.stderr)
        return 1

    # 1) Resolver persona real y fragmento (persona_id); quedarse con etiquetadas.
    resueltas: list[dict] = []
    n_sin_etiqueta = 0
    for f in fotos:
        pid = f.get("persona_id")
        cod = id2cod.get(pid) if pid is not None else None
        real = realof.get(cod) if cod is not None else None
        if real is None:
            n_sin_etiqueta += 1
            continue
        r = dict(f)
        r["persona_real"] = real
        r["fragmento"] = str(pid)
        resueltas.append(r)
    if not resueltas:
        print("ERROR: ninguna foto publicada tiene persona real en el fichero de "
              "etiquetas.", file=sys.stderr)
        return 1

    # 2) Cap determinista por persona real (round-robin entre fragmentos).
    seleccion = limitar_por_persona(resueltas, int(args.max_por_persona))
    if not seleccion:
        print("ERROR: --max-por-persona <= 0; no hay fotos que medir.", file=sys.stderr)
        return 1

    # 3) Modelo y config real.
    cfg = Config.from_env(args.ruta)

    medidas, contadores = medir_fotos(seleccion, cfg, int(args.det_size))
    if not medidas:
        print(f"ERROR: ninguna de las {len(seleccion)} fotos seleccionadas tiene "
              f"cara (sin imagen={contadores['n_sin_imagen']}, "
              f"sin cara={contadores['n_sin_cara']}).", file=sys.stderr)
        return 1

    # 4) Barrido de umbrales (por defecto 0.20..0.70 paso 0.01).
    umbrales = rango_umbrales(args.umbral_min, args.umbral_max, args.paso)
    if not umbrales:
        avisos.append("barrido de umbrales vacío (--paso<=0 o rango invertido).")
        umbrales = rango_umbrales(DEFAULT_UMBRAL_MIN, DEFAULT_UMBRAL_MAX, DEFAULT_PASO)

    # 5) Evaluación LOFO + resumen.
    resultados, n_no_eval = evaluar_medidas(medidas)
    if not resultados:
        avisos.append("ninguna persona real tiene >= 2 fragmentos; sin queries "
                      "evaluables (TAR/FAR no medibles).")
    informe = resumir(resultados, umbrales)

    personas = {m.get("persona_real") for m in medidas}
    personas_multi = len({r["persona_real"] for r in resultados})
    salida = {
        "version": VERSION,
        "parametros": {
            "local": int(args.local),
            "ruta": os.path.abspath(args.ruta),
            "etiquetas": os.path.abspath(args.etiquetas),
            "max_por_persona": int(args.max_por_persona),
            "det_size": int(args.det_size),
            "umbral_min": float(args.umbral_min),
            "umbral_max": float(args.umbral_max),
            "paso": float(args.paso),
            "n_umbrales": len(umbrales),
            "far_max_objetivo": FAR_MAX_OBJETIVO,
            "tar_objetivo": TAR_OBJETIVO,
        },
        "muestreo": {
            "n_filas": n_filas,
            "n_con_fichero": len(fotos),
            "n_sin_fichero": n_sin_fichero,
            "n_sin_etiqueta": n_sin_etiqueta,
            "n_seleccionadas": len(seleccion),
            "n_medidas": len(medidas),
            "n_sin_imagen": contadores["n_sin_imagen"],
            "n_sin_cara": contadores["n_sin_cara"],
            "n_flip_fallback": contadores["n_flip_fallback"],
            "n_personas_reales": len(personas),
            "n_personas_multi_fragmento": personas_multi,
            "n_queries_total": len(resultados) + n_no_eval,
            "n_queries_evaluables": len(resultados),
            "n_queries_no_evaluables": n_no_eval,
        },
        "informe": informe,
        "avisos": avisos,
    }
    if args.json:
        print(json.dumps(salida, ensure_ascii=False, indent=2))
    else:
        print(formato_texto(salida))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
