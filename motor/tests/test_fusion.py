"""Tests del motor de decisión SITUACIONAL (reenfoque A+B).

Semántica del nuevo motor (motor/core/fusion.py::decide_situational):
- La IDENTIDAD la decide SOLO la capa de cara/perfil: "new" <=> s1 < match_threshold.
- SUELO por cara: s1 >= secure_threshold NUNCA es "new" (mínimo "uncertain"),
  independientemente de la confianza de instancia c_cara.
- ACUERDO en perfil/ángulos: la silueta es co-autoridad y debe superar
  silueta_min_score para confirmar "match".
- VETO: >=2 capas independientes (torso/vlm/openai) con c >= veto_conf y
  s < gray_low degradan un match seguro a "uncertain" (nunca a "new").
- EARLY-EXIT en frontal nítida: no se llaman capas caras (silueta/LLM).
"""
import numpy as np

from motor.core.config import Config
from motor.core.fusion import CascadeContext, run_cascade, fuse
from motor.core.matching import LayerScore, select_candidates
from motor.core.router import Situation


def _cfg(**kw):
    base = dict(cascade_enabled=True, torso_enabled=True, vlm_enabled=True,
                openai_enabled=True, silueta_enabled=True,
                secure_threshold=0.40, match_threshold=0.30, margin=0.03,
                gray_low=0.28, gray_high=0.42, veto_conf=0.90,
                llm_min_conf=0.85, silueta_min_score=0.50,
                min_sharpness=55.0, w_cara=0.70, w_torso=0.10, w_llm=0.10)
    base.update(kw)
    return Config(**base)


# ---------------------------------------------------------------- fuse (helper)

def test_fuse_weighted():
    layers = {
        "cara": LayerScore(score=0.50, confidence=0.80),
        "torso": LayerScore(score=0.70, confidence=0.50),
    }
    weights = {"cara": 0.60, "torso": 0.15}
    S, conf = fuse(layers, weights)
    num = 0.80 * 0.60 * 0.50 + 0.50 * 0.15 * 0.70
    den = 0.80 * 0.60 + 0.50 * 0.15
    assert abs(S - num / den) < 1e-9
    assert 0.0 <= conf <= 1.0


def test_fuse_redistributes_when_unavailable():
    layers = {
        "cara": LayerScore(score=0.55, confidence=0.90),
        "torso": LayerScore(score=0.0, confidence=0.0, available=False),
    }
    S, _ = fuse(layers, {"cara": 0.60, "torso": 0.15})
    assert abs(S - 0.55) < 1e-9


def test_fuse_no_signal_returns_zero():
    S, conf = fuse({"cara": LayerScore(available=False)}, {"cara": 0.6})
    assert S == 0.0 and conf == 0.0


def test_select_candidates_top1_top2_and_band():
    scores = {"A": 0.50, "B": 0.49, "C": 0.30, "D": 0.10}
    cfg = Config(escalate_band=0.02)
    cands = select_candidates(scores, cfg)
    assert cands[0] == "A"
    assert set(cands) >= {"A", "B"}
    assert "C" not in cands


def test_select_candidates_band_includes_close():
    scores = {"A": 0.50, "B": 0.46, "C": 0.44}
    cfg = Config(escalate_band=0.07)
    cands = select_candidates(scores, cfg)
    assert set(cands) == {"A", "B", "C"}


# ------------------------------------------------------------- suelo por cara

def test_suelo_por_cara_face_segura_nunca_new():
    """Traza crítica: cara 0.45 con c_cara BAJA (0.40) + LLM en contra fuerte.
    El suelo por cara (s1>=secure) debe impedir "new" aunque c_cara < 0.60."""
    cfg = _cfg()
    ctx = CascadeContext(
        torso=lambda cod: LayerScore(score=0.10, confidence=0.10),
        vlm=lambda cod: LayerScore(score=0.05, confidence=0.90),   # 1 solo veto
    )
    res = run_cascade({"A": 0.45, "B": 0.30}, ctx, cfg,
                      LayerScore(score=0.45, confidence=0.40),
                      situation=Situation(pose="f", sharpness=20.0))
    assert res.verdict != "new"
    assert res.verdict in ("match", "uncertain")


def test_suelo_por_cara_con_veto_simple_sigue_match():
    """Con un solo veto el match seguro se mantiene (necesita >=2 vetos)."""
    cfg = _cfg()
    ctx = CascadeContext(
        torso=lambda cod: LayerScore(score=0.10, confidence=0.10),
        vlm=lambda cod: LayerScore(score=0.05, confidence=0.90),
    )
    res = run_cascade({"A": 0.45, "B": 0.30}, ctx, cfg,
                      LayerScore(score=0.45, confidence=0.40),
                      situation=Situation(pose="f", sharpness=20.0))
    assert res.verdict == "match"


# ------------------------------------------------------------ acuerdo silueta

def test_acuerdo_perfil_silueta_debil_uncertain():
    """Perfil: silueta débil NO confirma -> uncertain (nunca new, s1>=match)."""
    cfg = _cfg()
    ctx = CascadeContext(silueta=lambda cod: LayerScore(score=0.20, confidence=0.50))
    res = run_cascade({"A": 0.50, "B": 0.30}, ctx, cfg,
                      LayerScore(score=0.50, confidence=0.80),
                      situation=Situation(pose="pi", sharpness=80.0))
    assert res.verdict == "uncertain"


def test_acuerdo_perfil_silueta_fuerte_match():
    cfg = _cfg()
    ctx = CascadeContext(silueta=lambda cod: LayerScore(score=0.75, confidence=0.80))
    res = run_cascade({"A": 0.50, "B": 0.30}, ctx, cfg,
                      LayerScore(score=0.50, confidence=0.80),
                      situation=Situation(pose="pd", sharpness=80.0))
    assert res.verdict == "match"


def test_acuerdo_silueta_sin_proveedor_no_bloquea_frontal():
    """Sin silueta disponible en frontal nítida: la cara decide sola."""
    cfg = _cfg()
    ctx = CascadeContext()   # sin proveedores
    res = run_cascade({"A": 0.85, "B": 0.20}, ctx, cfg,
                      LayerScore(score=0.85, confidence=0.95),
                      situation=Situation(pose="f", sharpness=120.0))
    assert res.verdict == "match"


# ----------------------------------------------------------------------- veto

def test_veto_dos_capas_degradan_secure_a_uncertain():
    cfg = _cfg()
    ctx = CascadeContext(
        torso=lambda cod: LayerScore(score=0.10, confidence=0.95),
        vlm=lambda cod: LayerScore(score=0.05, confidence=0.95),
    )
    res = run_cascade({"A": 0.55, "B": 0.10}, ctx, cfg,
                      LayerScore(score=0.55, confidence=0.90),
                      situation=Situation(pose=None, sharpness=60.0))
    assert res.verdict == "uncertain"
    assert res.person == "A"


def test_veto_nunca_new_cuando_face_secure():
    """Invariante: 2 vetos sobre cara segura -> uncertain, NUNCA new."""
    cfg = _cfg()
    ctx = CascadeContext(
        torso=lambda cod: LayerScore(score=0.10, confidence=0.98),
        vlm=lambda cod: LayerScore(score=0.05, confidence=0.99),
        openai=lambda cod: LayerScore(score=0.10, confidence=0.98),
    )
    res = run_cascade({"A": 0.55, "B": 0.10}, ctx, cfg,
                      LayerScore(score=0.55, confidence=0.80),
                      situation=Situation(pose=None, sharpness=60.0))
    assert res.verdict != "new"
    assert res.verdict in ("match", "uncertain")


# ------------------------------------------------------- gate de identidad

def test_new_solo_cuando_cara_baja():
    """'new' exige s1 < match_threshold: capas superiores NO crean personas."""
    cfg = _cfg()
    ctx = CascadeContext(
        torso=lambda cod: LayerScore(score=0.05, confidence=0.95),
        vlm=lambda cod: LayerScore(score=0.05, confidence=0.95),
    )
    res = run_cascade({"A": 0.20, "B": 0.18}, ctx, cfg,
                      LayerScore(score=0.20, confidence=0.50),
                      situation=Situation(pose="f", sharpness=20.0))
    assert res.verdict == "new"
    assert res.person is None


def test_cara_justo_en_umbral_uncertain_sin_apoyo():
    """s1 en [match, secure) sin corroboración -> uncertain."""
    cfg = _cfg()
    ctx = CascadeContext()   # sin proveedores
    res = run_cascade({"A": 0.33, "B": 0.31}, ctx, cfg,
                      LayerScore(score=0.33, confidence=0.40),
                      situation=Situation(pose="f", sharpness=20.0))
    assert res.verdict == "uncertain"


# ------------------------------------------------------- escalada barato->caro

def test_escalada_gris_torso_luego_vlm():
    """Gris: torso no corrobora (score < gray_high) -> escala a VLM -> match."""
    cfg = _cfg()
    calls = {"vlm": 0}

    def torso(cod):
        return LayerScore(score=0.35, confidence=0.60)   # por debajo de gray_high

    def vlm(cod):
        calls["vlm"] += 1
        return LayerScore(score=0.90, confidence=0.90)

    ctx = CascadeContext(torso=torso, vlm=vlm)
    res = run_cascade({"A": 0.33, "B": 0.30}, ctx, cfg,
                      LayerScore(score=0.33, confidence=0.45),
                      situation=Situation(pose=None, sharpness=60.0))
    assert calls["vlm"] == 1
    assert res.verdict == "match" and res.person == "A"


def test_todo_gris_uncertain():
    cfg = _cfg()
    ctx = CascadeContext(torso=lambda cod: LayerScore(score=0.35, confidence=0.50))
    res = run_cascade({"A": 0.33, "B": 0.31}, ctx, cfg,
                      LayerScore(score=0.33, confidence=0.40),
                      situation=Situation(pose=None, sharpness=60.0))
    assert res.verdict == "uncertain"


# ------------------------------------------- confianza mínima de apoyo (min_layer_conf)

def test_torso_caduco_no_confirma():
    """Torso con score alto pero confianza baja (ropa caduca) NO corrobora."""
    cfg = _cfg()
    ctx = CascadeContext(torso=lambda cod: LayerScore(score=0.90, confidence=0.05))
    res = run_cascade({"A": 0.33, "B": 0.30}, ctx, cfg,
                      LayerScore(score=0.33, confidence=0.45),
                      situation=Situation(pose=None, sharpness=60.0))
    assert res.verdict == "uncertain"


def test_torso_confiado_confirma():
    cfg = _cfg()
    ctx = CascadeContext(torso=lambda cod: LayerScore(score=0.90, confidence=0.80))
    res = run_cascade({"A": 0.33, "B": 0.30}, ctx, cfg,
                      LayerScore(score=0.33, confidence=0.45),
                      situation=Situation(pose=None, sharpness=60.0))
    assert res.verdict == "match"


# --------------------------------------------------------- early-exit (ahorro)

def test_early_exit_frontal_nitida_no_llama_capas_caras():
    """Frontal nítida: ni silueta ni LLM se llaman (efficiencia)."""
    cfg = _cfg()
    calls = {"silueta": 0, "vlm": 0, "openai": 0, "torso": 0}

    def _count(name):
        def fn(cod):
            calls[name] += 1
            return LayerScore(available=False)
        return fn

    ctx = CascadeContext(silueta=_count("silueta"), torso=_count("torso"),
                         vlm=_count("vlm"), openai=_count("openai"))
    res = run_cascade({"A": 0.85, "B": 0.20}, ctx, cfg,
                      LayerScore(score=0.85, confidence=0.95),
                      situation=Situation(pose="f", sharpness=120.0))
    assert res.verdict == "match"
    assert calls == {"silueta": 0, "vlm": 0, "openai": 0, "torso": 0}


# ----------------------------------------------------------- sin cara (F7)

def test_sin_cara_nunca_new():
    cfg = _cfg()
    ctx = CascadeContext(
        torso=lambda cod: LayerScore(score=0.90, confidence=0.90),
        vlm=lambda cod: LayerScore(score=0.85, confidence=0.90),
    )
    res = run_cascade({"A": 0.90}, ctx, cfg,
                      LayerScore(score=0.90, confidence=0.90),
                      situation=Situation(has_face=False))
    assert res.verdict in ("match", "uncertain")
    assert res.verdict != "new"


def test_cascade_with_numpy_imports():
    layers = {"cara": LayerScore(score=0.4, confidence=0.5)}
    S, _ = fuse(layers, {"cara": 0.6})
    assert isinstance(S, float)


# ------------------------------------------------ banda baja (anti-fragmentación)

def test_banda_baja_sin_acuerdo_sigue_new():
    """s1 < match_threshold sin corroboración fuerte -> new (sin cambio)."""
    cfg = _cfg()
    ctx = CascadeContext(
        torso=lambda cod: LayerScore(score=0.20, confidence=0.20),
        vlm=lambda cod: LayerScore(score=0.30, confidence=0.50),
    )
    res = run_cascade({"A": 0.20, "B": 0.18}, ctx, cfg,
                      LayerScore(score=0.20, confidence=0.50),
                      situation=Situation(pose="f", sharpness=60.0))
    assert res.verdict == "new"
    assert res.person is None


def test_banda_baja_acuerdo_doble_match():
    """Perfil/espaldas: coseno 0.20 contra todo, pero torso+VLM coinciden fuerte
    -> asocia a top1 en vez de crear persona nueva (anti-fragmentación)."""
    cfg = _cfg()
    ctx = CascadeContext(
        torso=lambda cod: LayerScore(score=0.85, confidence=0.80),
        vlm=lambda cod: LayerScore(score=0.88, confidence=0.90),
    )
    res = run_cascade({"A": 0.20, "B": 0.18}, ctx, cfg,
                      LayerScore(score=0.20, confidence=0.50),
                      situation=Situation(pose="f", sharpness=60.0))
    assert res.verdict == "match"
    assert res.person == "A"


def test_banda_baja_acuerdo_llm_solo_match():
    """1 solo acuerdo LLM con confianza >= veto_conf también asocia (robustez
    si el otro LLM está caído)."""
    cfg = _cfg()
    ctx = CascadeContext(
        torso=lambda cod: LayerScore(available=False),
        vlm=lambda cod: LayerScore(score=0.90, confidence=0.95),
    )
    res = run_cascade({"A": 0.19, "B": 0.17}, ctx, cfg,
                      LayerScore(score=0.19, confidence=0.50),
                      situation=Situation(pose="f", sharpness=60.0))
    assert res.verdict == "match"
    assert res.person == "A"


def test_banda_baja_con_silueta_y_llm_positivo_pasa_a_revision():
    """Incidente cámara 19: no crear un duplicado con evidencia favorable incompleta."""
    cfg = _cfg()
    ctx = CascadeContext(
        silueta=lambda cod: LayerScore(score=0.646360, confidence=0.646360),
        torso=lambda cod: LayerScore(available=False),
        openai=lambda cod: LayerScore(score=0.725, confidence=0.60),
    )
    res = run_cascade({"A": 0.236954, "B": 0.218139}, ctx, cfg,
                      LayerScore(score=0.236954, confidence=0.365127),
                      situation=Situation(pose="aba", sharpness=161.69))
    assert res.verdict == "review"
    assert res.person == "A"


def test_banda_baja_por_debajo_del_suelo_new_directo():
    """s1 < new_low_floor: 'new' directo, sin gastar capas caras."""
    cfg = _cfg()
    calls = {"vlm": 0}

    def vlm(cod):
        calls["vlm"] += 1
        return LayerScore(score=0.90, confidence=0.95)

    ctx = CascadeContext(vlm=vlm)
    res = run_cascade({"A": 0.10, "B": 0.09}, ctx, cfg,
                      LayerScore(score=0.10, confidence=0.30),
                      situation=Situation(pose="f", sharpness=60.0))
    assert res.verdict == "new"
    assert calls["vlm"] == 0


# ------------------------------------- early-exit con margen top1-top2 pequeño

def test_early_exit_margen_limpio_no_llama_capas():
    """Frontal nítida con margen >= early_exit_min_margin: sigue early-exit."""
    cfg = _cfg(early_exit_min_margin=0.06)
    calls = {"silueta": 0, "vlm": 0, "openai": 0, "torso": 0}

    def _count(name):
        def fn(cod):
            calls[name] += 1
            return LayerScore(available=False)
        return fn

    ctx = CascadeContext(silueta=_count("silueta"), torso=_count("torso"),
                         vlm=_count("vlm"), openai=_count("openai"))
    res = run_cascade({"A": 0.85, "B": 0.20}, ctx, cfg,
                      LayerScore(score=0.85, confidence=0.95),
                      situation=Situation(pose="f", sharpness=120.0))
    assert res.verdict == "match"
    assert calls == {"silueta": 0, "vlm": 0, "openai": 0, "torso": 0}


def test_early_exit_margen_pequeno_corrobora_y_veta():
    """Frontal nítida pero con el 2º candidato cerca (0.55 vs 0.51): ya no decide
    la cara sola; las capas de apoyo pueden VETAR el match (falso merge)."""
    cfg = _cfg(early_exit_min_margin=0.06)
    ctx = CascadeContext(
        torso=lambda cod: LayerScore(score=0.10, confidence=0.90),
        vlm=lambda cod: LayerScore(score=0.05, confidence=0.90),
    )
    res = run_cascade({"A": 0.55, "B": 0.51}, ctx, cfg,
                      LayerScore(score=0.55, confidence=0.90),
                      situation=Situation(pose="f", sharpness=120.0))
    assert res.verdict == "uncertain"
    assert res.person == "A"


def test_early_exit_margen_pequeno_corrobora_match():
    """Margen pequeño pero torso confirma -> match (no se descarta por margen)."""
    cfg = _cfg(early_exit_min_margin=0.06)
    ctx = CascadeContext(torso=lambda cod: LayerScore(score=0.90, confidence=0.90))
    res = run_cascade({"A": 0.55, "B": 0.51}, ctx, cfg,
                      LayerScore(score=0.55, confidence=0.90),
                      situation=Situation(pose="f", sharpness=120.0))
    assert res.verdict == "match"
    assert res.person == "A"


# ------------------------------------------------- zonas ya no corrobora sola

def test_zonas_no_es_evidencia_independiente():
    """El proveedor legacy `zonas` re-reporta s_face: NO debe confirmar match
    por sí solo (evidencia circular). En zona gris sin capas reales -> uncertain."""
    cfg = _cfg()
    ctx = CascadeContext(
        zonas=lambda cod: LayerScore(score=0.80, confidence=0.80),   # alto pero circular
    )
    res = run_cascade({"A": 0.35, "B": 0.33}, ctx, cfg,
                      LayerScore(score=0.35, confidence=0.60),
                      situation=Situation(pose="arr", sharpness=80.0))
    # silueta (co-autoridad) no está -> no bloquea; zonas NO confirma -> uncertain
    assert res.verdict == "uncertain"
