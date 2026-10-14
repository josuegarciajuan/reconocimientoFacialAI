"""Tests del presupuesto síncrono (P2) — motor/clasificador.py::_CascadeCtx.

Verifican que con `sync_tail_budget_ms=0` (default) NO cambia nada y que, con
presupuesto, las capas de cola larga (VLM/OpenAI) se cortan como "sin señal"
(mismo efecto que proveedor sin respuesta), registrando el diferido.
"""
from __future__ import annotations

import time

import pytest

from motor.clasificador import _CascadeCtx
from motor.core.config import Config


def _ctx(tmp_path, cfg):
    return _CascadeCtx(
        ruta=str(tmp_path), local_id="1", camara_id="9", cfg=cfg, store=None,
        face_scores={}, query_pose=None, rep_face_crop=None, rep_torso_path=None,
        rep_busto_path=None, rep_img=None, rep_face=None,
    )


def test_budget_cero_no_corta(tmp_path):
    cfg = Config()
    cfg.vlm_enabled = True
    cfg.openai_enabled = True
    cfg.sync_tail_budget_ms = 0
    ctx = _ctx(tmp_path, cfg)
    ctx._t0 = time.time() - 1000  # aunque haya pasado mucho tiempo
    assert ctx._tail_budget_exceeded() is False


def test_budget_corta_cuando_se_supera(tmp_path):
    cfg = Config()
    cfg.vlm_enabled = True
    cfg.openai_enabled = True
    cfg.sync_tail_budget_ms = 1000
    ctx = _ctx(tmp_path, cfg)
    ctx._t0 = time.time() - 5  # 5 s > 1 s de presupuesto
    assert ctx._tail_budget_exceeded() is True


def test_vlm_y_openai_devuelven_sin_senal_con_presupuesto(tmp_path):
    cfg = Config()
    cfg.vlm_enabled = True
    cfg.openai_enabled = True
    cfg.sync_tail_budget_ms = 1000
    ctx = _ctx(tmp_path, cfg)
    ctx._t0 = time.time() - 5
    v = ctx.vlm_score("P1")
    o = ctx.openai_score("P1")
    assert v.available is False and v.reason == "presupuesto_sincrono"
    assert o.available is False and o.reason == "presupuesto_sincrono"
    # No se ha inicializado ningún cliente externo (corte ANTES de la llamada).
    assert ctx._vlm is None and ctx._openai is None


def test_budget_no_corta_antes_de_tiempo(tmp_path):
    cfg = Config()
    cfg.vlm_enabled = True
    cfg.sync_tail_budget_ms = 60000
    ctx = _ctx(tmp_path, cfg)
    ctx._t0 = time.time()
    assert ctx._tail_budget_exceeded() is False
