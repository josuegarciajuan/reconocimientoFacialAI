"""Enrutado situacional (reenfoque A+B) — motor/core/router.py

La decisión ya NO es una media ponderada de capas: cada situación del query
(pose + nitidez + presencia de cara/torso) define qué capas son:

  - AUTORIDAD     : decide la identidad (siempre la capa de cara/perfil;
                    sin cara, torso+LLM — nunca crean persona).
  - CO-AUTORIDAD  : debe CONFIRMAR por acuerdo (silueta en perfil/ángulos).
  - APOYO         : corrobora en la zona gris (barato -> caro) o veta con
                    evidencia contraria muy fuerte.

Invariante: la IDENTIDAD la decide SOLO la capa de cara/perfil:
"new" <=> s1 < match_threshold. Las demás capas jamás crean personas.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .config import Config


@dataclass
class Situation:
    """Estado del query que condiciona el enrutado."""
    pose: str | None = None          # etiqueta de pose (quality.pose_label)
    sharpness: float = 0.0           # varianza Laplaciano de la cara representativa
    has_face: bool = True            # ¿hay cara? (False => crops de espaldas F7)
    has_torso: bool = False          # ¿hay crop de torso compañero?


@dataclass
class RoutingPlan:
    authority: tuple = ("cara",)                       # capas que deciden
    co_authority: tuple = ()                           # capas que deben confirmar (acuerdo)
    support: tuple = ()                                # corroboran en la zona gris
    veto_capable: tuple = ("torso", "vlm", "openai")   # pueden aportar evidencia contraria
    early_exit: bool = False                           # frontal nítida: decide la cara sola


PROFILE_CLASSES = {"pi", "pd"}
ANGLE_CLASSES = {"m45i", "m45d", "arr", "aba"}


def route(sit: Situation, cfg: Config) -> RoutingPlan:
    """Devuelve el plan de enrutado para la situación del query."""
    if not sit.has_face:
        # F7: sin cara, torso+LLM mandan; NUNCA se crea persona sin cara.
        return RoutingPlan(authority=("torso", "vlm"), early_exit=False)

    p = sit.pose
    nitida = bool(sit.sharpness) and sit.sharpness >= cfg.min_sharpness
    sil = cfg.silueta_enabled

    # Perfil y ángulos raros: la cara (pose-consciente) es autoridad y la
    # silueta geométrica CONFIRMA por acuerdo (la cara frontal "no cuadra").
    if p in PROFILE_CLASSES or p in ANGLE_CLASSES:
        co = ("silueta",) if sil else ()
        return RoutingPlan(authority=("cara",), co_authority=co)

    # Frontal nítida: la cara decide SOLA (early-exit, sin capas caras).
    if p == "f" and nitida:
        return RoutingPlan(authority=("cara",), early_exit=True)

    # Frontal borrosa: cara + silueta de apoyo en gris.
    if p == "f":
        support = ("silueta",) if sil else ()
        return RoutingPlan(authority=("cara",), support=support)

    # Pose desconocida/otra: apoyo general (silueta; torso si hay crop y capa on).
    support = []
    if sil:
        support.append("silueta")
    if cfg.torso_enabled and sit.has_torso:
        support.append("torso")
    return RoutingPlan(authority=("cara",), support=tuple(support))
