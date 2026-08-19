"""Fusión ponderada + escalada de la cascada (F3).

Sustituye la decisión binaria actual por una CASCADA DE CAPAS:
  L1a cara  -> s_cara, c_cara   (existente)
  L1b torso -> s_torso, c_torso (si hay crop)
  L1c zonas -> s_zona, c_zona   (si la cara fue el punto débil)
  L2  VLM local (Ollama)        (si lo anterior no concluye)
  L3  OpenAI gpt-4o-mini        (solo tras L2, en gris)

FUSIÓN (siempre):
  w_i = c_i * p_i          (confianza de instancia * peso-prior de la capa)
  S   = Σ(w_i * s_i) / Σ(w_i)   (capa sin señal -> c_i=0 -> se redistribuye sola)

ESCALADA (early-exit, no fallback ciego):
  1. L1a -> candidatos top-1/top-2 + banda.
  2. L1b (si hay crop) -> fusionar.
  3. ¿Concluyente? FINALIZAR. Si no -> escalar.
  4. L1c (si la cara fue el punto débil) -> re-fusionar.
  5. L2 VLM local -> re-fusionar. 6. L3 OpenAI -> re-fusionar -> decisión final.
  7. Gris tras L3 -> UNCERTAIN (cola de revisión manual). NUNCA duplicado en silencio.

INVARIANTE DE SEGURIDAD: una capa cara con confianza alta NUNCA se degrada a
"new" por las demás; solo puede matizarse a "uncertain" con evidencia contraria
MUY fuerte, nunca a "new" directo.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import Config
from .matching import LayerScore, MatchResult, select_candidates


@dataclass
class CascadeContext:
    """Proveedores de capas per-candidato. Cada callable(cod) -> LayerScore.

    Los proveedores de capas caras ya disponibles devuelven el LayerScore sin
    coste; los de capas caras (VLM/OpenAI) pueden devolver available=False si
    no hay presupuesto/caché/RAM (degradación, nunca bloqueo).
    """
    torso: object = None        # callable(cod) -> LayerScore
    zonas: object = None        # callable(cod) -> LayerScore
    vlm: object = None          # callable(cod) -> LayerScore
    openai: object = None       # callable(cod) -> LayerScore

    def layer(self, name: str, cod: str) -> LayerScore | None:
        prov = getattr(self, name, None)
        if prov is None:
            return None
        try:
            ls = prov(cod)
        except Exception:  # noqa: BLE001 — una capa rota degrada, no rompe la cascada
            return LayerScore(available=False)
        if ls is None:
            return None
        return ls


def fuse(layers: dict[str, LayerScore], weights: dict[str, float]) -> tuple[float, float]:
    """Fusión ponderada: devuelve (S, confianza agregada).

    S = Σ(c_i*p_i*s_i) / Σ(c_i*p_i). Capa sin señal (available=False o c=0)
    queda fuera y su peso se redistribuye automáticamente.
    """
    num = 0.0
    den = 0.0
    conf_avg = 0.0
    for name, ls in layers.items():
        if not ls.available or ls.confidence <= 0.0:
            continue
        w = ls.confidence * weights.get(name, 0.0)
        num += w * ls.score
        den += w
        conf_avg += ls.confidence
    if den <= 0.0:
        return 0.0, 0.0
    S = num / den
    conf = conf_avg / len(layers) if layers else 0.0
    return float(S), float(conf)


def _strong_opposite(layers: dict[str, LayerScore], cfg: Config) -> bool:
    """Evidencia contraria MUY fuerte: torso+VLM (o VLM+openai) dicen claramente
    distinta (score < gray_low) con confianza >= early_exit_conf."""
    strong = [ls for ls in layers.values()
              if ls.available and ls.confidence >= cfg.early_exit_conf and ls.score < cfg.gray_low]
    return len(strong) >= 2


def run_cascade(face_scores: dict[str, float],
                ctx: CascadeContext,
                cfg: Config,
                face_layer: LayerScore) -> MatchResult:
    """Ejecuta la cascada de fusión sobre los candidatos de L1a.

    face_scores : similitudes por persona de la capa cara (L1a).
    ctx         : proveedores de las capas superiores (por candidato).
    face_layer  : LayerScore de la capa cara (score=mejor coseno, confidence=c_cara).
    """
    cands = select_candidates(face_scores, cfg)
    if not cands:
        return MatchResult(verdict="new", scores=dict(face_scores), confidence=face_layer.confidence,
                           layer_scores={"cara": face_layer})

    top = cands[0]
    s1 = face_scores[top]
    s2 = max((v for k, v in face_scores.items() if k != top), default=0.0)

    layers: dict[str, LayerScore] = {"cara": face_layer}
    weights = {"cara": cfg.w_cara, "torso": cfg.w_torso, "zona": cfg.w_torso,
               "vlm": cfg.w_llm, "openai": cfg.w_llm}
    # el slot LLM (0.25) se reparte entre vlm y openai: si solo una está, lleva el 0.25 entero;
    # si están las dos, se reparten a medias (cada una contribuye su confianza).
    weights["vlm"] = cfg.w_llm
    weights["openai"] = cfg.w_llm

    face_secure = (s1 >= cfg.secure_threshold and face_layer.confidence >= cfg.face_conf_secure_floor)
    layer_order = ["torso", "zonas", "vlm", "openai"]

    for name in layer_order:
        # flags de fase: no llamar a capas deshabilitadas
        if name == "torso" and not cfg.torso_enabled:
            continue
        if name == "zonas" and not cfg.zones_enabled:
            continue
        if name == "vlm" and not cfg.vlm_enabled:
            continue
        if name == "openai" and not cfg.openai_enabled:
            continue
        ls = ctx.layer(name, top)
        if ls is None or not ls.available:
            continue
        layers[name] = ls

        S, conf = fuse(layers, weights)

        # EARLY-EXIT: capa con c_i ≈ 1 finaliza inmediatamente
        max_c = max(x.confidence for x in layers.values() if x.available)
        if max_c >= cfg.early_exit_conf:
            if ls.score >= cfg.gray_high:
                return _result("match", top, s1, s2, face_scores, layers, conf, cands)
            if ls.score < cfg.gray_low and _strong_opposite(layers, cfg):
                # evidencia contraria fortísima: matizar match seguro a uncertain
                if face_secure:
                    return _result("uncertain", top, s1, s2, face_scores, layers, conf, cands)
                return _result("new", None, s1, s2, face_scores, layers, conf, cands)
            # early-exit de nivel alto pero en banda gris: seguir escalando
            continue

        verdict = _decide(S, conf, cfg, face_secure)
        if verdict != "escalate":
            return _result(verdict, top if verdict in ("match", "uncertain") else None,
                           s1, s2, face_scores, layers, conf, cands)

    # tras todas las capas, decisión final con la fusión completa
    S, conf = fuse(layers, weights)
    verdict = _decide(S, conf, cfg, face_secure)
    if verdict == "escalate":
        verdict = "uncertain"        # sin más capas, la banda gris queda en uncertain
    person = top if verdict in ("match", "uncertain") else None
    if verdict == "new" and face_secure:
        verdict = "uncertain"        # invariante: nunca new si la cara era segura
        person = top
    return _result(verdict, person, s1, s2, face_scores, layers, conf, cands)


def _decide(S: float, conf: float, cfg: Config, face_secure: bool) -> str:
    if S >= cfg.gray_high and conf >= 0.35:
        return "match"
    if S < cfg.gray_low and conf >= cfg.new_confidence_min:
        return "new"
    return "escalate" if conf < 0.95 else "uncertain"


def _result(verdict, person, s1, s2, face_scores, layers, conf, cands) -> MatchResult:
    return MatchResult(
        verdict=verdict, person=person,
        best_score=s1, second_score=s2,
        scores=dict(face_scores), confidence=conf,
        layer_scores=dict(layers), candidates=list(cands),
    )
