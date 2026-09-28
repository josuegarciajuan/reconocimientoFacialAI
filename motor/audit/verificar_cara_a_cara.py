"""Verificación "cara a cara" con la config REAL de clasificación (solo lectura).

Runner de DIAGNÓSTICO previo a la fusión de identidades. Responde, con números,
a la pregunta: *si cada persona real fuera una identidad nueva, ¿la config
actual la reconocería entre sus fragmentos?*

Diseño **leave-one-fragment-out (LOFO)**:

1. Se leen (SELECT) las fotos publicadas de una sala (``local``) y se mide, por
   foto, la cara de mayor ``det_score``: embedding (nativo o SR-before-embedding,
   igual que el clasificador), lado mayor, nitidez y pose.
2. Se agrupa por persona real (etiquetas) y por ``persona_id``/``cod_interno``
   (fragmento).
3. Para cada fragmento ``F`` de la persona ``P``, la galería LIMPIA de ``P`` son
   los embeddings de los DEMÁS fragmentos de ``P``; las fotos de ``F`` son las
   queries. Así ningún embedding de la query está en su galería (sin fuga).
4. Por query se calculan los scores por persona real (max coseno contra cada
   galería), se ejecuta :func:`motor.core.matching.decide` y se SIMULA la cascada
   con la config actual, sin capas de apoyo (no hay torso/VLM para fotos
   publicadas y la silueta está desactivada con ``silueta_confirm_enabled=False``)::

       lado_cara < cfg.match_min_face_side  o  pose no válida  -> "provisional"
       s1 >= secure_threshold                                  -> "match"
       s1 >= match_threshold                                   -> "uncertain"
       s1 <  match_threshold                                   -> "new"

   Como no hay confirmación por capas de apoyo, la banda ``[match, secure)``
   NUNCA se auto-confirma: queda en ``uncertain``.

El módulo **no escribe nada**: solo imprime por stdout. No toca la BD salvo
``SELECT`` y los modelos/ficheros los importa de forma perezosa (es importable y
testeable sin insightface, cv2, BD ni red).

Uso::

    motor/venv/bin/python -m motor.audit.verificar_cara_a_cara \
        --local 1 --ruta /root/reconocimientoFacial \
        --etiquetas /ruta/etiquetas.json --max-por-persona 40 --json

La parte pura (:func:`evaluar_queries`, :func:`resumen`) no toca BD ni modelos y
se testea con embeddings sintéticos.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from itertools import combinations
from typing import Any, Mapping, Sequence

import numpy as np

from ..core.config import Config
from .auditar_identidades import cargar_etiquetas
from .medir_banco import RAIZ, construir_fotos

VERSION = 1

DEFAULT_MAX_POR_PERSONA = 40
DEFAULT_DET_SIZE = 640
DEFAULT_SR_MIN_FACE = 160

#: Nº de pares de personas reales (face-to-face) mostrados, ordenados por coseno.
TOP_PARES_DEFAULT = 15

#: Clases de veredicto posible de la cascada simulada.
VEREDICTOS_ACTUAL = ("provisional", "match", "uncertain", "new")


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


def _norm(v: Any) -> np.ndarray:
    """Normaliza un vector a norma 1 (defensivo; los embeddings ya vienen L2)."""
    a = np.asarray(v, dtype=np.float64).ravel()
    n = float(np.linalg.norm(a))
    if n <= 0.0:
        return a
    return a / n


def _mat_norm(vecs: Sequence[Any]) -> np.ndarray:
    """Matriz ``(n, d)`` con cada fila normalizada. Lista vacía -> ``(0, 0)``."""
    if not vecs:
        return np.zeros((0, 0), dtype=np.float64)
    a = np.asarray([_norm(v) for v in vecs], dtype=np.float64)
    if a.ndim == 1:
        a = a.reshape(1, -1)
    return a


def _preparar_galerias(
    galerias: Mapping[str, Sequence[tuple[Any, Any]]],
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Convierte ``{persona: [(fragmento, vector), ...]}`` en matrices + fragmentos.

    Returns:
        ``(matrices, fragmentos)``: ``matrices[p]`` es ``(n, d)`` normalizada y
        ``fragmentos[p]`` un array object de etiquetas de fragmento alineado por
        fila (para poder excluir el fragmento de la query).
    """
    matrices: dict[str, np.ndarray] = {}
    fragmentos: dict[str, np.ndarray] = {}
    for persona, items in galerias.items():
        vecs: list[Any] = []
        frags: list[str] = []
        for frag, vec in items:
            vecs.append(vec)
            frags.append(str(frag))
        matrices[persona] = _mat_norm(vecs)
        fragmentos[persona] = np.asarray(frags, dtype=object)
    return matrices, fragmentos


def _stats(vals: Sequence[float | None]) -> dict:
    """Estadísticos de una lista de cosenos (mediana, p10, p90, min, max, n)."""
    xs = [float(v) for v in vals if v is not None]
    if not xs:
        return {"n": 0, "mediana": None, "p10": None, "p90": None,
                "min": None, "max": None}
    a = np.asarray(xs, dtype=np.float64)
    return {
        "n": len(xs),
        "mediana": _f(np.median(a)),
        "p10": _f(np.percentile(a, 10)),
        "p90": _f(np.percentile(a, 90)),
        "min": _f(a.min()),
        "max": _f(a.max()),
    }


def _pct(n: int, d: int) -> float | None:
    """Fracción ``n/d`` JSON-safe (``None`` si el denominador es 0)."""
    if d <= 0:
        return None
    return n / d


def limitar_por_persona(
    fotos: Sequence[Mapping[str, Any]],
    max_por_persona: int,
) -> list[Mapping[str, Any]]:
    """Cap determinista de fotos por persona real, repartiendo entre fragmentos.

    Round-robin entre los ``fragmento`` de cada persona (orden alfabético) para
    que ningún fragmento con muchas fotos ahogue a los demás; dentro de cada
    fragmento, orden por ``(ts, foto_id)``. Con ``max_por_persona <= 0`` devuelve
    lista vacía. Determinista: mismas entradas -> misma selección.

    Las fotos deben traer ya ``persona_real``, ``fragmento``, ``ts`` y ``foto_id``.
    """
    if max_por_persona <= 0:
        return []
    por_persona: dict[Any, list[Mapping[str, Any]]] = defaultdict(list)
    for f in fotos:
        por_persona[f.get("persona_real")].append(f)
    out: list[Mapping[str, Any]] = []
    for persona in sorted(por_persona, key=lambda p: (p is None, str(p))):
        por_frag: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for f in por_persona[persona]:
            por_frag[str(f.get("fragmento"))].append(f)
        for frag in por_frag:
            por_frag[frag].sort(
                key=lambda x: (
                    _f(x.get("ts")) if _f(x.get("ts")) is not None else 0.0,
                    str(x.get("foto_id") or ""),
                )
            )
        frags = sorted(por_frag)
        idx = {frag: 0 for frag in frags}
        elegidas: list[Mapping[str, Any]] = []
        while len(elegidas) < max_por_persona:
            progreso = False
            for frag in frags:
                if len(elegidas) >= max_por_persona:
                    break
                k = idx[frag]
                if k < len(por_frag[frag]):
                    elegidas.append(por_frag[frag][k])
                    idx[frag] = k + 1
                    progreso = True
            if not progreso:
                break
        out.extend(elegidas)
    return out


# ---------------------------------------------------------------------------
# Núcleo puro: evaluación LOFO y resumen
# ---------------------------------------------------------------------------
def evaluar_queries(
    galerias: Mapping[str, Sequence[tuple[Any, Any]]],
    queries: Sequence[Mapping[str, Any]],
    cfg: Config,
) -> list[dict]:
    """Evalúa cada query contra la galería LOFO y simula la cascada actual.

    Args:
        galerias: ``{persona_real: [(fragmento, embedding), ...]}`` con TODAS las
            fotos medidas. La exclusión del fragmento de la query se hace aquí.
        queries: secuencia de dicts con ``persona_real``, ``fragmento``,
            ``vector`` y, opcionalmente, ``lado_cara``, ``sharpness``,
            ``pose_valida`` (def. ``True``), ``pose`` (etiqueta o ``None``) y
            ``foto_id``.
        cfg: config real de clasificación (``match_threshold``,
            ``secure_threshold``, ``match_min_face_side``...).

    Returns:
        Lista de dicts (uno por query) con ``genuino``/``impostor``, ``top1``,
        ``s1``/``s2``, el veredicto de :func:`decide` (``resultado_cara``) y el de
        la cascada simulada (``resultado_actual``), además de ``acierto``,
        ``falso_match`` y ``evaluable`` (hay galería propia con otro fragmento).
    """
    matrices, fragmentos = _preparar_galerias(galerias)
    from ..core.matching import decide  # import tardío: no exige cv2 al importar el módulo
    min_side = int(cfg.match_min_face_side)
    secure = float(cfg.secure_threshold)
    match = float(cfg.match_threshold)

    resultados: list[dict] = []
    for q in queries:
        persona_q = q.get("persona_real")
        frag_q = str(q.get("fragmento"))
        vec = q.get("vector")
        sharpness = float(q.get("sharpness") or 0.0)
        pose_valida = bool(q.get("pose_valida", True))
        pose = q.get("pose")
        lado = float(q.get("lado_cara") or 0.0)

        scores: dict[str, float] = {}
        if vec is not None:
            qv = _norm(vec)
            for persona, M in matrices.items():
                if M.shape[0] == 0 or M.shape[1] != qv.shape[0]:
                    continue
                if persona == persona_q:
                    mask = fragmentos[persona] != frag_q   # leave-one-fragment-out
                    if not mask.any():
                        continue
                    ref = M[mask]
                else:
                    ref = M
                scores[str(persona)] = float(np.max(ref @ qv))

        genuino = scores.get(persona_q)
        extr = [v for p, v in scores.items() if p != persona_q]
        impostor = max(extr) if extr else None
        if scores:
            top1 = max(scores, key=lambda p: scores[p])
            s1 = float(scores[top1])
        else:
            top1 = None
            s1 = 0.0
        ranked = sorted(scores.values(), reverse=True)
        s2 = float(ranked[1]) if len(ranked) > 1 else 0.0

        res_cara = decide(scores, cfg, sharpness=sharpness,
                          pose=pose if pose_valida else None)

        # Guardia de información + validez de pose -> provisional (revisión).
        if lado < min_side or not pose_valida:
            actual = "provisional"
        elif s1 >= secure:
            actual = "match"
        elif s1 >= match:
            actual = "uncertain"   # sin capas de apoyo que confirmen la banda
        else:
            actual = "new"

        evaluable = genuino is not None
        acierto = bool(actual == "match" and top1 == persona_q)
        falso = bool(actual == "match" and top1 is not None and top1 != persona_q)

        resultados.append({
            "persona_real": persona_q,
            "fragmento": frag_q,
            "foto_id": q.get("foto_id"),
            "lado_cara": _f(lado),
            "sharpness": _f(sharpness),
            "pose": pose,
            "pose_valida": pose_valida,
            "yaw": _f(q.get("yaw")),
            "pitch": _f(q.get("pitch")),
            "roll": _f(q.get("roll")),
            "genuino": _f(genuino),
            "impostor": _f(impostor),
            "top1": top1,
            "s1": _f(s1),
            "s2": _f(s2),
            "scores": {k: _f(v) for k, v in scores.items()},
            "resultado_cara": res_cara.verdict,
            "resultado_actual": actual,
            "evaluable": evaluable,
            "acierto": acierto,
            "falso_match": falso,
        })
    return resultados


def _resumen_persona(resultados: Sequence[Mapping[str, Any]]) -> dict:
    """Agrega los resultados de UNA persona real (TAR, veredictos, falsos match)."""
    n = len(resultados)
    ev = [r for r in resultados if r.get("evaluable")]
    nev = len(ev)
    aciertos = sum(1 for r in ev if r.get("acierto"))
    cuenta = {v: sum(1 for r in resultados if r.get("resultado_actual") == v)
              for v in VEREDICTOS_ACTUAL}
    falsos = sum(1 for r in ev if r.get("falso_match"))
    return {
        "n_queries": n,
        "n_evaluables": nev,
        "n_aciertos": aciertos,
        "tar": _pct(aciertos, nev),
        "n_provisional": cuenta["provisional"],
        "n_match": cuenta["match"],
        "n_uncertain": cuenta["uncertain"],
        "n_new": cuenta["new"],
        "pct_provisional": _pct(cuenta["provisional"], n),
        "pct_uncertain": _pct(cuenta["uncertain"], n),
        "pct_new": _pct(cuenta["new"], n),
        "n_falsos_match": falsos,
        "pct_falsos_match": _pct(falsos, nev),
        "veredicto_actual": cuenta,
    }


def resumen(
    resultados: Sequence[Mapping[str, Any]],
    galerias: Mapping[str, Sequence[tuple[Any, Any]]],
    cfg: Config,
    top_pares: int = TOP_PARES_DEFAULT,
) -> dict:
    """Construye el informe agregado (personas, cosenos, matriz y veredicto).

    Args:
        resultados: salida de :func:`evaluar_queries`.
        galerias: mismas galerías pasadas a :func:`evaluar_queries` (para contar
            fragmentos y calcular los pares cara a cara).
        cfg: config real (umbrales) para las comparaciones de coseno.
        top_pares: nº de pares de personas (face-to-face) a mostrar.

    Returns:
        Dict JSON-safe con ``por_persona_real``, ``cosenos``, ``pares_cara_a_cara``
        y ``global`` (TAR/FAR y veredicto con números).
    """
    matrices, fragmentos = _preparar_galerias(galerias)
    match_umbral = float(cfg.match_threshold)

    personas = sorted(set(galerias) | {r.get("persona_real") for r in resultados},
                      key=lambda p: (p is None, str(p)))
    por_persona: dict[str, dict] = {}
    for p in personas:
        if p is None:
            continue
        rs = [r for r in resultados if r.get("persona_real") == p]
        d = _resumen_persona(rs)
        frags = fragmentos.get(p)
        d["n_fragmentos"] = int(len(set(frags.tolist()))) if frags is not None else 0
        por_persona[p] = d

    genuinos = [r.get("genuino") for r in resultados]
    impostores = [r.get("impostor") for r in resultados]
    cosenos = {
        "genuino": _stats(genuinos),
        "impostor": _stats(impostores),
        "match_threshold": match_umbral,
        "n_genuinos_ge_match": sum(
            1 for g in genuinos if g is not None and float(g) >= match_umbral
        ),
        "n_impostores_ge_match": sum(
            1 for i in impostores if i is not None and float(i) >= match_umbral
        ),
    }

    pares: list[dict] = []
    nombres = sorted(matrices)
    for a, b in combinations(nombres, 2):
        Ma, Mb = matrices[a], matrices[b]
        if Ma.shape[0] == 0 or Mb.shape[0] == 0 or Ma.shape[1] != Mb.shape[1]:
            continue
        pares.append({
            "persona_a": a,
            "persona_b": b,
            "max_cos": _f(float(np.max(Ma @ Mb.T))),
        })
    pares.sort(key=lambda x: x["max_cos"] if x["max_cos"] is not None else -1.0,
               reverse=True)
    top = pares[:max(0, int(top_pares))]

    g = _resumen_persona(resultados)
    ev = [r for r in resultados if r.get("evaluable")]
    nev = len(ev)
    n = len(resultados)
    tar = _pct(sum(1 for r in ev if r.get("acierto")), nev)
    falsos = sum(1 for r in ev if r.get("falso_match"))
    far = _pct(falsos, nev)

    if nev == 0:
        conclusion = ("SIN DATOS: no hay queries evaluables (se necesita al menos una "
                      "persona real con >= 2 fragmentos).")
    elif tar is not None and tar >= 0.9 and falsos == 0:
        conclusion = (
            f"SÍ: TAR={tar:.3f} (sin falsos match) reconoce a las personas entre "
            f"sus fragmentos con la config actual."
        )
    elif tar is not None and tar >= 0.6:
        conclusion = (
            f"PARCIAL: TAR={tar:.3f} con {falsos} falso(s) match; parte de los "
            f"fragmentos quedan en revisión/uncertain."
        )
    else:
        conclusion = (
            f"NO: TAR={tar if tar is None else round(tar, 3)}; la mayoría no se "
            f"reconocería entre fragmentos (revisión/uncertain/new)."
        )

    global_ = {
        **g,
        "n_queries": n,
        "n_evaluables": nev,
        "tar": tar,
        "far": far,
        "conclusion": conclusion,
    }
    return {
        "por_persona_real": por_persona,
        "cosenos": cosenos,
        "pares_cara_a_cara": top,
        "global": global_,
    }


# ---------------------------------------------------------------------------
# Medición (impuro: BD, ficheros, modelo)
# ---------------------------------------------------------------------------
def medir_fotos(
    fotos: Sequence[Mapping[str, Any]],
    cfg: Config,
    det_size: int,
    verbose: bool = True,
) -> tuple[list[dict], dict]:
    """Mide cara principal + embedding + calidad/pose de cada foto publicada.

    Igual que el clasificador: elige la cara de mayor ``det_score``, recorta el
    embedding con SR-before-embedding si el lado mayor es menor que
    ``cfg.sr_embed_min_face`` y registra lado, nitidez y pose.

    Args:
        fotos: fotos con ``ruta``, ``foto_id``, ``persona_real``, ``fragmento``,
            ``ts`` y ``cam`` (salida de :func:`limitar_por_persona`).
        cfg: config real (``min_det_score``, ``sr_embed_min_face``,
            ``sr_embed_enabled``, ``match_min_face_side``).
        det_size: tamaño de detección de insightface.
        verbose: progreso a stderr cada 10 fotos.

    Returns:
        ``(medidas, contadores)`` donde cada medida añade ``embedding``,
        ``lado_cara``, ``sharpness``, ``yaw``/``pitch``/``roll``, ``pose``,
        ``pose_valida``, ``info_suficiente`` y ``sr_aplicado``.
    """
    import cv2  # import perezoso: el módulo es importable sin cv2 real

    from ..core.model import analyze
    from ..core.quality import face_sharpness, pose_label, pose_valida
    from ..core.superres import enhance_embedding

    min_score = float(getattr(cfg, "min_det_score", 0.4))
    medidas: list[dict] = []
    contadores = {
        "n_leidas": 0,
        "n_sin_imagen": 0,
        "n_sin_cara": 0,
        "n_sr": 0,
        "n_baja_info": 0,
        "n_pose_invalida": 0,
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
        fw = int(cara.bbox[2]) - int(cara.bbox[0])
        fh = int(cara.bbox[3]) - int(cara.bbox[1])
        lado = max(fw, fh)
        sr_aplicado = bool(getattr(cfg, "sr_embed_enabled", True)
                           and lado < int(cfg.sr_embed_min_face))
        emb = enhance_embedding(img, cara, cfg)  # decide SR por sí mismo
        sharpness = face_sharpness(img, cara)
        pose_ok = pose_valida(cara, cfg)
        etiqueta = pose_label(cara, cfg.yaw_frontal, cfg.yaw_45, cfg.yaw_90,
                              cfg.pitch_frontal)
        info_suf = bool(lado >= int(cfg.match_min_face_side))
        if not info_suf:
            contadores["n_baja_info"] += 1
        if not pose_ok:
            contadores["n_pose_invalida"] += 1
        if sr_aplicado:
            contadores["n_sr"] += 1
        medidas.append({
            "foto_id": foto.get("foto_id"),
            "persona_real": foto.get("persona_real"),
            "fragmento": foto.get("fragmento"),
            "persona_id": foto.get("persona_id"),
            "cod_interno": foto.get("cod_interno"),
            "cam": foto.get("cam"),
            "ts": foto.get("ts"),
            "ruta": foto.get("ruta"),
            "embedding": emb,
            "lado_cara": lado,
            "sharpness": _f(sharpness),
            "yaw": _f(cara.yaw),
            "pitch": _f(cara.pitch),
            "roll": _f(cara.roll),
            "pose": etiqueta,
            "pose_valida": pose_ok,
            "info_suficiente": info_suf,
            "sr_aplicado": sr_aplicado,
            "det_score": _f(cara.det_score),
        })
        if verbose and (i % 10 == 0 or i == total):
            print(f"  [cara-a-cara] {i}/{total} fotos", file=sys.stderr, flush=True)
    return medidas, contadores


def construir_galerias_y_queries(
    medidas: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, list[tuple[str, Any]]], list[dict]]:
    """Agrupa las medidas por persona/fragmento y arma galerías + queries LOFO.

    Solo son queries las personas reales con **>= 2 fragmentos** (si no, no hay
    galería propia tras excluir el fragmento y el genuino no es evaluable).

    Returns:
        ``(galerias, queries)`` con
        ``galerias: {persona_real: [(fragmento, embedding), ...]}``.
    """
    por_persona: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for m in medidas:
        por_persona[m.get("persona_real")].append(m)

    galerias: dict[str, list[tuple[str, Any]]] = {}
    queries: list[dict] = []
    for persona, ms in por_persona.items():
        if persona is None:
            continue
        galerias[persona] = [(str(m.get("fragmento")), m.get("embedding")) for m in ms]
        n_frags = len({str(m.get("fragmento")) for m in ms})
        if n_frags < 2:
            continue
        for m in ms:
            queries.append({
                "persona_real": persona,
                "fragmento": str(m.get("fragmento")),
                "foto_id": m.get("foto_id"),
                "vector": m.get("embedding"),
                "lado_cara": m.get("lado_cara"),
                "sharpness": m.get("sharpness"),
                "pose": m.get("pose"),
                "pose_valida": m.get("pose_valida"),
                "yaw": m.get("yaw"),
                "pitch": m.get("pitch"),
                "roll": m.get("roll"),
            })
    return galerias, queries


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------
def _num(x: Any, dec: int = 3) -> str:
    """Formatea un float tolerando ``None``."""
    return "-" if x is None else f"{float(x):.{dec}f}"


def _pct_s(x: Any) -> str:
    """Formatea una fracción 0-1 como porcentaje tolerando ``None``."""
    return "-" if x is None else f"{100.0 * float(x):.1f}%"


def formato_texto(salida: Mapping[str, Any]) -> str:
    """Render legible del informe (sin flag ``--json``)."""
    p = salida.get("parametros", {})
    c = salida.get("config", {})
    m = salida.get("muestreo", {})
    inf = salida.get("informe", {})
    g = inf.get("global", {})
    lineas = [
        "== Verificación cara a cara (LOFO, solo lectura) ==",
        f"local={p.get('local')}  etiquetas={p.get('etiquetas')}",
        f"max_por_persona={p.get('max_por_persona')}  det_size={p.get('det_size')}  "
        f"sr_min_face={p.get('sr_min_face')}",
        f"config: match={_num(c.get('match_threshold'))} "
        f"secure={_num(c.get('secure_threshold'))} "
        f"guardia_lado={c.get('match_min_face_side')} "
        f"silueta_confirm={c.get('silueta_confirm_enabled')}",
        "",
        "-- Muestreo --",
        f"filas BD: {m.get('n_filas')}  con fichero: {m.get('n_con_fichero')}  "
        f"sin fichero: {m.get('n_sin_fichero')}  sin etiqueta: {m.get('n_sin_etiqueta')}",
        f"seleccionadas: {m.get('n_seleccionadas')}  medidas: {m.get('n_medidas')}  "
        f"sin imagen: {m.get('n_sin_imagen')}  sin cara: {m.get('n_sin_cara')}  "
        f"SR: {m.get('n_sr')}",
        f"baja info (<{c.get('match_min_face_side')}px): {m.get('n_baja_info')}  "
        f"pose inválida: {m.get('n_pose_invalida')}",
        f"personas reales: {m.get('n_personas_reales')}  "
        f"queries: {m.get('n_queries')}  evaluables: {m.get('n_evaluables')}",
        "",
        "-- Por persona real --",
    ]
    for persona, d in (inf.get("por_persona_real") or {}).items():
        lineas.append(
            f"  {persona}: {d.get('n_fragmentos')} fragmentos / {d.get('n_queries')} "
            f"queries | TAR={_num(d.get('tar'))} ({d.get('n_aciertos')}/"
            f"{d.get('n_evaluables')})"
        )
        lineas.append(
            f"      provisional={_pct_s(d.get('pct_provisional'))} "
            f"uncertain={_pct_s(d.get('pct_uncertain'))} "
            f"new={_pct_s(d.get('pct_new'))} "
            f"falsos_match={d.get('n_falsos_match')}"
        )
    cos = inf.get("cosenos", {})
    lineas += [
        "",
        "-- Distribución de cosenos --",
        f"  genuino:  n={cos.get('genuino', {}).get('n')} "
        f"mediana={_num(cos.get('genuino', {}).get('mediana'))} "
        f"p10={_num(cos.get('genuino', {}).get('p10'))} "
        f"p90={_num(cos.get('genuino', {}).get('p90'))}",
        f"  impostor: n={cos.get('impostor', {}).get('n')} "
        f"mediana={_num(cos.get('impostor', {}).get('mediana'))} "
        f"p10={_num(cos.get('impostor', {}).get('p10'))} "
        f"p90={_num(cos.get('impostor', {}).get('p90'))}",
        f"  genuinos >= match({_num(cos.get('match_threshold'))}): "
        f"{cos.get('n_genuinos_ge_match')}  |  impostores >= match: "
        f"{cos.get('n_impostores_ge_match')}",
        "",
        "-- Pares cara a cara (max cos, top) --",
    ]
    for par in inf.get("pares_cara_a_cara") or []:
        lineas.append(
            f"  {_num(par.get('max_cos'))}  {par.get('persona_a')} <-> "
            f"{par.get('persona_b')}"
        )
    lineas += [
        "",
        "-- Veredicto global --",
        f"TAR={_num(g.get('tar'))}  FAR={_num(g.get('far'))}  "
        f"provisional={_pct_s(g.get('pct_provisional'))}  "
        f"uncertain={_pct_s(g.get('pct_uncertain'))}  "
        f"new={_pct_s(g.get('pct_new'))}",
        f"{g.get('conclusion')}",
    ]
    for aviso in salida.get("avisos") or []:
        lineas.append(f"AVISO: {aviso}")
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(
        description="Verifica si la config actual reconoce a las personas entre "
                    "sus fragmentos (leave-one-fragment-out, solo lectura)."
    )
    ap.add_argument("--local", type=int, default=1, help="sala/local_id (def. 1)")
    ap.add_argument("--ruta", default=RAIZ, help="raíz del repo (def. padre de motor/)")
    ap.add_argument("--etiquetas", required=True, help="JSON con id/cod_interno/persona")
    ap.add_argument("--max-por-persona", type=int, default=DEFAULT_MAX_POR_PERSONA,
                    help="máximo de fotos medidas por persona real (def. 40)")
    ap.add_argument("--det-size", type=int, default=DEFAULT_DET_SIZE,
                    help="tamaño de detección de insightface (def. 640)")
    ap.add_argument("--sr-min-face", type=int, default=DEFAULT_SR_MIN_FACE,
                    help="lado mayor de cara bajo el que aplica SR-before-embedding "
                         "(def. 160; sobrescribe cfg.sr_embed_min_face)")
    ap.add_argument("--json", action="store_true", help="emitir el informe como JSON")
    return ap.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Punto de entrada CLI. Solo lee (SELECT, ficheros, modelos); no escribe nada."""
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

    # 1) Resolver persona real y fragmento; quedarse con las etiquetadas.
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
        r["fragmento"] = str(cod) if cod else str(pid)
        resueltas.append(r)
    if not resueltas:
        print("ERROR: ninguna foto publicada tiene persona real en el fichero de "
              "etiquetas.", file=sys.stderr)
        return 1

    # 2) Cap determinista por persona real (reparto round-robin entre fragmentos).
    seleccion = limitar_por_persona(resueltas, int(args.max_por_persona))
    if not seleccion:
        print("ERROR: --max-por-persona <= 0; no hay fotos que medir.", file=sys.stderr)
        return 1

    # 3) Modelo y config real (los umbrales se leen del .env de --ruta).
    cfg = Config.from_env(args.ruta)
    cfg.sr_embed_min_face = int(args.sr_min_face)  # override del runner

    medidas, contadores = medir_fotos(seleccion, cfg, int(args.det_size))
    if not medidas:
        print(f"ERROR: ninguna de las {len(seleccion)} fotos seleccionadas tiene "
              f"cara (sin imagen={contadores['n_sin_imagen']}, "
              f"sin cara={contadores['n_sin_cara']}).", file=sys.stderr)
        return 1

    # 4) Galerías LOFO + queries y evaluación.
    galerias, queries = construir_galerias_y_queries(medidas)
    personas_multi = sum(
        1 for persona, ms in galerias.items()
        if len({frag for frag, _ in ms}) >= 2
    )
    if not queries:
        avisos.append(
            "ninguna persona real tiene >= 2 fragmentos; sin queries evaluables."
        )
    if int(cfg.match_min_face_side) > int(args.sr_min_face):
        avisos.append(
            "match_min_face_side > sr_min_face: hay caras admitidas a decisión "
            "cuyo embedding se calculó sin SR."
        )

    resultados = evaluar_queries(galerias, queries, cfg)
    informe = resumen(resultados, galerias, cfg)

    personas_medidas = {m.get("persona_real") for m in medidas}
    salida = {
        "version": VERSION,
        "parametros": {
            "local": int(args.local),
            "ruta": os.path.abspath(args.ruta),
            "etiquetas": os.path.abspath(args.etiquetas),
            "max_por_persona": int(args.max_por_persona),
            "det_size": int(args.det_size),
            "sr_min_face": int(args.sr_min_face),
        },
        "config": {
            "match_threshold": _f(cfg.match_threshold),
            "secure_threshold": _f(cfg.secure_threshold),
            "margin": _f(cfg.margin),
            "match_min_face_side": int(cfg.match_min_face_side),
            "admission_margin": _f(cfg.admission_margin),
            "sr_embed_min_face": int(cfg.sr_embed_min_face),
            "silueta_confirm_enabled": bool(cfg.silueta_confirm_enabled),
            "pose_valid_yaw": _f(cfg.pose_valid_yaw),
            "pose_valid_pitch": _f(cfg.pose_valid_pitch),
            "pose_valid_roll": _f(cfg.pose_valid_roll),
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
            "n_sr": contadores["n_sr"],
            "n_baja_info": contadores["n_baja_info"],
            "n_pose_invalida": contadores["n_pose_invalida"],
            "n_personas_reales": len(personas_medidas),
            "n_personas_multi_fragmento": max(0, personas_multi),
            "n_queries": len(queries),
            "n_evaluables": informe["global"]["n_evaluables"],
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
