#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Calibración diaria de la cascada (F3, §5) — motor/calibrar.py

Flujo:
  1. Recoge la matriz etiquetada (feedback de acciones del panel: Unir/mover foto).
  2. Entrena regresión logística sobre (s_i, c_i) de las capas -> P(misma persona).
  3. VALIDA en held-out (TAR/FAR) ANTES de desplegar; si no mejora, no se aplica.
  4. Re-pondera los pesos-prior (update_prior_weights) con cap anti-drift.
  5. Guarda el modelo VERSIONADO (pickle + journal) en motor/calib/ -> reversible.

Uso (diario, p.ej. timer systemd rf-calibra):
    motor/venv/bin/python motor/calibrar.py --ruta /root/reconocimientoFacial

Reglas anti-drift: solo etiquetas humanas (nunca las decisiones del propio
fusionador); cap de delta diario; validación held-out antes de aplicar.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import numpy as np  # noqa: E402

from motor.core.calibration import (FEATURE_NAMES, CalibrationModel,  # noqa: E402
                                    layer_stats_by_situation, logistic_fit,
                                    predict_proba, update_prior_weights,
                                    validate_held_out)
from motor.core.config import Config  # noqa: E402
from motor.core.feedback import FeedbackCollector  # noqa: E402


def _layer_stats(X: np.ndarray, y: np.ndarray) -> dict[str, dict]:
    """Por capa: {hits, total, conf_hit, conf_fail} a partir de la matriz.

    FEATURE_NAMES: s_cara, c_cara, s_torso, c_torso, s_zona, c_zona,
                   s_vlm, c_vlm, s_openai, c_openai  (pares s/c por capa).
    """
    names = ["cara", "cara", "torso", "torso", "zona", "zona",
             "vlm", "vlm", "openai", "openai"]
    stats: dict[str, dict] = {}
    for layer in set(names):
        stats[layer] = {"hits": 0, "total": 0, "conf_hit": 0.0, "conf_fail": 0.0}
    for i in range(len(y)):
        label = int(y[i])
        for j, layer in enumerate(names):
            if j % 2 == 0:
                continue   # solo miramos la columna de confianza (c_*)
            st = stats[layer]
            st["total"] += 1
            c = float(X[i, j])
            if label == 1:
                st["hits"] += 1
                st["conf_hit"] += c
            else:
                st["conf_fail"] += c
    for layer, st in stats.items():
        if st["total"]:
            st["conf_hit"] /= max(1, st["hits"])
            st["conf_fail"] /= max(1, st["total"] - st["hits"])
    return stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
    ap.add_argument("--min-samples", type=int, default=20,
                    help="mínimo de muestras etiquetadas para intentar calibrar")
    args = ap.parse_args()

    cfg = Config.from_env(args.ruta)
    calib_dir = os.path.join(args.ruta, cfg.calib_dir)
    model = CalibrationModel(calib_dir)
    model.load()

    # 1. recoger la matriz etiquetada de TODOS los locales
    locals_dir = os.path.join(args.ruta, "motor/feedback")
    Xs, ys, situ = [], [], []
    if os.path.isdir(locals_dir):
        for lid in sorted(os.listdir(locals_dir)):
            fc = FeedbackCollector(args.ruta, lid, enabled=False)
            X, y, s = fc.export_matrix_with_situations()
            if len(X):
                Xs.append(X)
                ys.append(y)
                situ.extend(s)
    if not Xs:
        print("sin datos etiquetados (feedback): no se calibra todavía. "
              "Las acciones 'Unir'/'mover foto' del panel alimentan la matriz.")
        return 0
    X = np.vstack(Xs)
    y = np.concatenate(ys)
    print(f"muestras etiquetadas: {len(y)} (genuinas={int((y == 1).sum())}, "
          f"impostoras={int((y == 0).sum())})")
    if len(y) < args.min_samples:
        print(f"insuficientes muestras (<{args.min_samples}): no se calibra.")
        return 0

    # 1b. diagnóstico por SITUACIÓN (F4): fiabilidad por capa condicionada a la
    # pose. No re-pondera todavía (requiere más etiquetas); informa de dónde
    # cada capa acierta/falla (p. ej. LLM sobreconfiado en perfil).
    stats_situ = layer_stats_by_situation(X, y, situ)
    for sc, layers in sorted(stats_situ.items()):
        partes = []
        for layer in ("cara", "torso", "zona", "vlm", "openai"):
            d = layers.get(layer)
            if d and d["total"] >= 3:
                acc = d["hits"] / d["total"]
                partes.append(f"{layer}:{acc*100:.0f}% (n={d['total']}, "
                              f"c_hit={d['conf_hit']:.2f}/c_fail={d['conf_fail']:.2f})")
        if partes:
            print(f"[situación {sc}] " + " | ".join(partes))

    # 2. entrenar + validar held-out
    idx = np.arange(len(y))
    rng = np.random.default_rng(42)
    rng.shuffle(idx)
    n_test = max(1, int(0.25 * len(y)))
    test_idx, train_idx = idx[:n_test], idx[n_test:]
    w, b, mean, std = logistic_fit(X[train_idx], y[train_idx])
    tar, far, thr = validate_held_out(w, b, X[test_idx], y[test_idx],
                                      far_target=0.01, mean=mean, std=std)
    print(f"held-out: TAR={tar*100:.1f}% FAR={far*100:.2f}% (umbral P>={thr:.3f})")

    # 3. ¿mejora frente a la línea base (regla simple: score cara > 0.40)?
    base = float(np.mean((X[test_idx, 0] >= 0.40) == (y[test_idx] == 1)))
    print(f"baseline score_cara>=0.40: acierto={base*100:.1f}%")
    improved = not np.isnan(tar) and tar >= base - 0.02

    # 4. re-ponderar pesos-prior con cap anti-drift
    stats = _layer_stats(X, y)
    priors = {"cara": cfg.w_cara, "torso": cfg.w_torso, "llm": cfg.w_llm}
    layer_to_prior = {"cara": "cara", "torso": "torso", "vlm": "llm", "openai": "llm"}
    agg = {}
    for layer, prior in layer_to_prior.items():
        st = stats.get(layer, {"hits": 0, "total": 0, "conf_hit": 0.5, "conf_fail": 0.5})
        agg.setdefault(prior, {"hits": 0, "total": 0, "conf_hit": 0.0, "conf_fail": 0.0})
        agg[prior]["hits"] += st["hits"]
        agg[prior]["total"] += st["total"]
        agg[prior]["conf_hit"] += st["conf_hit"]
        agg[prior]["conf_fail"] += st["conf_fail"]
    weights, applied = update_prior_weights(agg, priors, cfg)

    # 5. persistir versionado
    model.w, model.b, model.mean, model.std = w, b, mean, std
    model.weights = weights
    model.weights_applied = applied and improved
    path = model.save(meta={"n": int(len(y)), "tar": float(tar), "far": float(far),
                            "held_out_acc": float(base)})
    if applied and improved:
        print(f"pesos actualizados: { {k: round(v, 3) for k, v in weights.items()} }")
    else:
        print(f"no se aplican los pesos (mejora insuficiente); modelo guardado igualmente en {path}")
    print(f"modelo: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
