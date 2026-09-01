"""Motor de decisión SITUACIONAL (reenfoque A+B) — motor/core/fusion.py

Sustituye la fusión ponderada por un motor de EVIDENCIA con enrutado:

  - AUTORIDAD: la capa de cara/perfil decide la identidad. Sin cara (F7),
    torso+LLM mandan y NUNCA crean persona.
  - ACUERDO: en perfil/ángulos, la silueta es co-autoridad: debe superar
    `silueta_min_score` para confirmar "match"; si está y NO supera, el
    veredicto es "uncertain" (la silueta débil no desmiente, solo no confirma).
  - GATE DE IDENTIDAD: "new" <=> s1 < match_threshold. Las capas superiores
    jamás crean personas.
  - BANDA BAJA (2026-08-21): s1 en [new_low_floor, match_threshold) no crea
    "new" en silencio: si >= `low_band_min_agreements` capas de apoyo (torso/
    vlm/openai) coinciden FUERTE (>= gray_high con su confianza mínima), se
    asocia a top1 (anti-fragmentación de perfiles/espaldas: ArcFace cae a
    ~0.15-0.25 en poses extremas de personas conocidas). Un ÚNICO acuerdo LLM
    con c >= veto_conf también basta (p.ej. si un LLM está caído).
  - SUELO POR CARA: s1 >= secure_threshold NUNCA es "new" (mínimo "uncertain"),
    independientemente de la confianza de instancia c_cara (fix del bug de la
    media ponderada: una cara con coseno alto ya no se descarta por capas
    débiles con confianza no calibrada).
  - VETO: >=2 capas independientes (torso/vlm/openai) con c >= veto_conf y
    s < gray_low degradan un match seguro a "uncertain" (nunca a "new").
  - EARLY-EXIT: frontal nítida decide sola con la cara SOLO si el margen
    top1-top2 >= `early_exit_min_margin` (si el 2º candidato está cerca, la
    cara sola no es concluyente y se corrobora, pudiendo las capas vetar).
  - ZONA GRIS [match, secure): corroboración barato->caro; la primera capa
    de apoyo que confirma (>= umbral) da "match"; si ninguna, "uncertain".

`fuse()` se conserva SOLO como helper de desempate/reporte (p. ej. reagrupar).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import Config
from .matching import LayerScore, MatchResult, select_candidates
from .router import Situation, route


@dataclass
class CascadeContext:
    """Proveedores de capas per-candidato. Cada callable(cod) -> LayerScore.

    Los proveedores de capas caras (VLM/OpenAI) pueden devolver available=False
    si no hay presupuesto/caché/RAM (degradación, nunca bloqueo).
    """
    torso: object = None        # callable(cod) -> LayerScore (apariencia ropa)
    attributes: object = None   # callable(cod) -> LayerScore (visible attrs; report-only)
    zonas: object = None        # callable(cod) -> LayerScore (pose-conf, legacy)
    silueta: object = None      # callable(cod) -> LayerScore (geometría facial)
    perfil: object = None       # callable(cod) -> LayerScore (reservado: re-embedding perfil)
    vlm: object = None          # callable(cod) -> LayerScore (VLM local, L2)
    openai: object = None       # callable(cod) -> LayerScore (OpenAI, L3)

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
    """Fusión ponderada (helper de desempate/reporte): (S, confianza agregada).

    S = Σ(c_i*p_i*s_i) / Σ(c_i*p_i). Capa sin señal (available=False o c=0)
    queda fuera y su peso se redistribuye automáticamente.
    """
    num = 0.0
    den = 0.0
    conf_avg = 0.0
    n = 0
    for name, ls in layers.items():
        if not ls.available or ls.confidence <= 0.0:
            continue
        w = ls.confidence * weights.get(name, 0.0)
        num += w * ls.score
        den += w
        conf_avg += ls.confidence
        n += 1
    if den <= 0.0:
        return 0.0, 0.0
    S = num / den
    conf = conf_avg / n if n else 0.0
    return float(S), float(conf)


def _result(verdict, person, s1, s2, face_scores, layers, cands) -> MatchResult:
    confs = [ls.confidence for ls in layers.values()
             if ls.available and ls.confidence > 0.0]
    conf = float(sum(confs) / len(confs)) if confs else 0.0
    return MatchResult(
        verdict=verdict, person=person,
        best_score=float(s1), second_score=float(s2),
        scores=dict(face_scores), confidence=conf,
        layer_scores=dict(layers), candidates=list(cands),
    )


def _weights(cfg: Config) -> dict[str, float]:
    """Pesos-prior para el helper `fuse` (reporte/desempate, no decisión)."""
    return {"cara": cfg.w_cara, "perfil": cfg.perfil_w, "silueta": cfg.silueta_w,
            "torso": cfg.w_torso, "zonas": cfg.w_torso, "vlm": cfg.w_llm,
            "openai": cfg.w_llm, "attributes": cfg.attributes_weight}


def _escalation(plan, cfg: Config, ctx: CascadeContext) -> list[str]:
    """Orden barato->caro de las capas de apoyo para la zona gris.

    SOLO capas con EVIDENCIA INDEPENDIENTE: silueta geométrica, torso/ropa y
    LLMs. Se excluye `zonas` (legacy): su score re-reporta s_face (la misma
    capa de cara), así que no puede corroborar ni vetar sin ser circular.
    """
    order = list(plan.support)
    for name in ("torso", "vlm", "openai"):
        if name in order:
            continue
        enabled = {"torso": cfg.torso_enabled, "vlm": cfg.vlm_enabled,
                   "openai": cfg.openai_enabled}[name]
        if enabled:
            order.append(name)
    if cfg.attributes_enabled and "attributes" not in order:
        order.append("attributes")
    return order


def _agree_threshold(name: str, cfg: Config) -> float:
    """Score mínimo de una capa de apoyo para corroborar "match" en gris."""
    if name == "silueta":
        return cfg.silueta_min_score
    return cfg.gray_high


def _decide_body(face_scores, ctx: CascadeContext, cfg: Config, top: str,
                 face_layer: LayerScore, layers: dict, cands) -> MatchResult:
    """F7 — sin cara (espaldas): torso/VLM corroboran; NUNCA "new"."""
    for name in ("torso", "vlm", "openai"):
        ls = ctx.layer(name, top)
        if ls is None or not ls.available:
            continue
        layers[name] = ls
    S, conf = fuse(layers, _weights(cfg))
    if S >= cfg.gray_high and conf >= 0.35:
        return _result("match", top, face_layer.score, 0.0, face_scores, layers, cands)
    return _result("uncertain", None, face_layer.score, 0.0, face_scores, layers, cands)


def decide_situational(face_scores: dict[str, float],
                       ctx: CascadeContext,
                       cfg: Config,
                       face_layer: LayerScore,
                       situation: Situation | None = None) -> MatchResult:
    """Motor de decisión situacional.

    face_scores : similitudes por persona de la capa cara (ya pose-consciente
                  si cfg.zones_enabled).
    ctx         : proveedores de las capas superiores (por candidato).
    face_layer  : LayerScore de la capa cara (score=s1, confidence=c_cara).
    situation   : pose/nitidez/presencia de cara y torso (None => default).
    """
    situation = situation or Situation()
    plan = route(situation, cfg)

    cands = select_candidates(face_scores, cfg)
    if not cands:
        return MatchResult(verdict="new", scores=dict(face_scores),
                           confidence=face_layer.confidence,
                           layer_scores={"cara": face_layer}, candidates=[])

    top = cands[0]
    s1 = float(face_scores[top])
    s2 = float(max((v for k, v in face_scores.items() if k != top), default=0.0))
    layers: dict[str, LayerScore] = {"cara": face_layer}

    if not situation.has_face:
        return _decide_body(face_scores, ctx, cfg, top, face_layer, layers, cands)

    # --- ACUERDO de co-autoridad (silueta en perfil/ángulos) ---
    for name in plan.co_authority:
        ls = ctx.layer(name, top)
        if ls is None:
            continue
        layers[name] = ls
        if ls.available and ls.score < cfg.silueta_min_score:
            # silueta no confirma: uncertain (nunca new si s1 >= match_threshold)
            if s1 < cfg.match_threshold:
                return _result("new", None, s1, s2, face_scores, layers, cands)
            return _result("uncertain", top, s1, s2, face_scores, layers, cands)

    # --- GATE DE IDENTIDAD: SOLO la capa de cara/perfil crea ---
    if s1 < cfg.match_threshold:
        # BANDA BAJA (anti-fragmentación): coseno bajo contra TODO puede ser una
        # pose extrema de una persona conocida (perfil/espaldas) donde ArcFace
        # pierde discriminación (genuino ~0.15-0.25). Antes de crear "new" en
        # silencio, si las capas de apoyo coinciden FUERTE con top1, se asocia
        # (la identidad la sigue decidiendo la cara: esto NO crea, solo asocia).
        if s1 >= cfg.new_low_floor:
            acuerdos = 0
            acuerdos_sin_atributos = 0
            acuerdo_atributos = False
            acuerdo_llm_fuerte = False
            for name in _escalation(plan, cfg, ctx):
                ls = ctx.layer(name, top)
                if ls is None or not ls.available:
                    continue
                layers[name] = ls
                umbral = cfg.llm_min_conf if name in ("vlm", "openai") else cfg.min_layer_conf
                if ls.confidence < umbral:
                    continue
                if ls.score >= cfg.gray_high:
                    acuerdos += 1
                    if name == "attributes":
                        acuerdo_atributos = True
                    else:
                        acuerdos_sin_atributos += 1
                    if name in ("vlm", "openai") and ls.confidence >= cfg.veto_conf:
                        acuerdo_llm_fuerte = True
            if (acuerdos_sin_atributos >= cfg.low_band_min_agreements
                    or acuerdo_llm_fuerte
                    or (acuerdo_atributos and acuerdos_sin_atributos >= 1)):
                return _result("match", top, s1, s2, face_scores, layers, cands)
        return _result("new", None, s1, s2, face_scores, layers, cands)

    # --- EARLY-EXIT: frontal nítida decide sola SOLO con margen limpio ---
    # Con el 2º candidato cerca (margen < early_exit_min_margin) el coseno de
    # cara no es concluyente aunque s1 >= secure: se corrobora para que las
    # capas de apoyo puedan VETAR un impostor (falso merge) en vez de decidir
    # la cara sola sobre una evidencia ambigua.
    if plan.early_exit and (s1 - s2) >= cfg.early_exit_min_margin:
        verdict = "match" if s1 >= cfg.secure_threshold else "uncertain"
        return _result(verdict, top, s1, s2, face_scores, layers, cands)

    # --- CORROBORACIÓN barato->caro (una sola pasada: veta o confirma) ---
    # Cada capa de apoyo: score < gray_low y c >= veto_conf => VETO (evidencia
    # contraria muy fuerte); score >= umbral de acuerdo => CONFIRMA (fin, sin
    # llamar a capas más caras); en banda gris => neutra (se sigue escalando).
    # El fallback depende del suelo por cara: secure sin 2 vetos => match;
    # gris sin corroboración => uncertain. Las capas superiores NUNCA crean.
    vetoes = 0
    confirmado = False
    confirmado_atributos = False
    apoyo_no_atributos = False
    for name in _escalation(plan, cfg, ctx):
        ls = ctx.layer(name, top)
        if ls is None or not ls.available:
            continue
        layers[name] = ls
        if name in ("vlm", "openai"):
            if ls.confidence < cfg.llm_min_conf:
                continue
        elif name in ("torso", "zonas") and ls.confidence < cfg.min_layer_conf:
            # torso/zonas caducos o poco fiables NO corroboran (su score alto
            # no compensa una confianza baja, p. ej. ropa desactualizada).
            continue
        if ls.score < cfg.gray_low and ls.confidence >= cfg.veto_conf:
            vetoes += 1
            continue
        if ls.score >= _agree_threshold(name, cfg):
            if name == "attributes":
                confirmado_atributos = True
                if apoyo_no_atributos:
                    confirmado = True
                continue
            confirmado = True
        elif name != "attributes" and ls.score >= cfg.gray_low:
            # Attributes can break a genuinely indecisive tie only when an
            # independent layer already supplies non-negative support.
            apoyo_no_atributos = True
            if confirmado_atributos:
                confirmado = True
            if not cfg.attributes_enabled:
                break
    if vetoes >= 2:
        return _result("uncertain", top, s1, s2, face_scores, layers, cands)
    if confirmado:
        return _result("match", top, s1, s2, face_scores, layers, cands)
    if s1 >= cfg.secure_threshold:
        # suelo por cara: sin 2 vetos, la cara decide (nunca new)
        return _result("match", top, s1, s2, face_scores, layers, cands)
    return _result("uncertain", top, s1, s2, face_scores, layers, cands)


def run_cascade(face_scores: dict[str, float],
                ctx: CascadeContext,
                cfg: Config,
                face_layer: LayerScore,
                situation: Situation | None = None) -> MatchResult:
    """Wrapper retro-compatible: delega en el motor situacional.

    Si no se pasa `situation` (p. ej. reagrupar.py), se usa el default
    (pose None, frontal genérica) con autoridad "cara" + apoyo general.
    """
    return decide_situational(face_scores, ctx, cfg, face_layer, situation)
