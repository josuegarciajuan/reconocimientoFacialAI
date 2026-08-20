"""Calibración y refinamiento de pesos de la cascada (F3, §5).

Para cada capa i se acumula de cada decisión ETIQUETADA (feedback humano):
  hits_i / total_i          (cuántas veces acertó)
  E[c_i | acierto] - E[c_i | fallo]

Actualización diaria:
  accuracy_i = EWMA(hits_i / total_i)
  calib_i    = 1 - | E[c|acierto] - E[c|fallo] |
  p_i        = normalize(accuracy_i * calib_i + epsilon)

  - Capa que acierta mucho y con confianza alta => SUBE su p_i.
  - Capa que falla con confianza alta (sobreconfiada) => BAJA su p_i.
  - Capa que acierta con confianza baja => su confianza se recalibra al alza.

GUARDAS ANTI-DRIFT:
  - Calibrar SOLO sobre etiquetas humanas/held-out.
  - Cap al delta diario de pesos (calib_lr).
  - Modelo versionado (pickle + journal) => reversible.
  - Validar TAR/FAR en held-out ANTES de desplegar; si no mejora, no se aplica.
"""
from __future__ import annotations

import json
import os
import pickle
import time

import numpy as np

from .config import Config

FEATURE_NAMES = ["s_cara", "c_cara", "s_torso", "c_torso", "s_zona", "c_zona",
                 "s_vlm", "c_vlm", "s_openai", "c_openai"]
EPS = 1e-6

# F4: clases de situación para la calibración condicionada a la pose.
PERFIL_CLASSES = {"pi", "pd"}
ANGULOS_CLASSES = {"m45i", "m45d", "arr", "aba"}


def situation_class(pose: str | None) -> str:
    """Clase de situación del query: perfil / angulos / frontal / otro."""
    if pose in PERFIL_CLASSES:
        return "perfil"
    if pose in ANGULOS_CLASSES:
        return "angulos"
    if pose == "f":
        return "frontal"
    return "otro"


def layer_stats_by_situation(X: np.ndarray, y: np.ndarray, situ: list[str]) -> dict:
    """Fiabilidad por capa CONDICIONADA a la clase de situación.

    Devuelve {clase: {capa: {hits, total, conf_hit, conf_fail}}} con el mismo
    esquema que _layer_stats de calibrar.py, pero agrupando las filas por la
    situación registrada en la decisión (F4). Permite detectar, por ejemplo,
    si el LLM acierta en frontal pero falla en perfil (sobreconfianza por
    situación) y decidir después si una capa puede subir a autoridad.
    """
    names = ["cara", "cara", "torso", "torso", "zona", "zona",
             "vlm", "vlm", "openai", "openai"]
    out: dict[str, dict[str, dict]] = {}
    for i in range(len(y)):
        sc = situation_class(situ[i]) if i < len(situ) else "otro"
        layers = out.setdefault(sc, {})
        for layer in set(names):
            layers.setdefault(layer, {"hits": 0, "total": 0,
                                      "conf_hit": 0.0, "conf_fail": 0.0})
        label = int(y[i])
        for j, layer in enumerate(names):
            if j % 2 == 0:
                continue
            d = layers[layer]
            d["total"] += 1
            c = float(X[i, j])
            if label == 1:
                d["hits"] += 1
                d["conf_hit"] += c
            else:
                d["conf_fail"] += c
    for sc, layers in out.items():
        for layer, d in layers.items():
            if d["total"]:
                d["conf_hit"] /= max(1, d["hits"])
                d["conf_fail"] /= max(1, d["total"] - d["hits"])
    return out


def logistic_fit(X: np.ndarray, y: np.ndarray, epochs: int = 400,
                 lr: float = 0.1) -> tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    """Regresión logística con numpy puro (sin dependencias nuevas).

    X: (n, d) features; y: (n,) etiquetas 0/1.
    Estandariza X (z-score) para convergencia estable en features heterogéneas
    (scores 0..1 y confianzas). Devuelve (w, b, mean, std) para predict_proba.
    """
    n, d = X.shape
    mean = np.zeros(d, dtype=np.float64)
    std = np.ones(d, dtype=np.float64)
    if n == 0:
        return np.zeros(d, dtype=np.float64), 0.0, mean, std
    X = X.astype(np.float64)
    y = y.astype(np.float64)
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std < 1e-9] = 1.0
    Xs = (X - mean) / std
    w = np.zeros(d, dtype=np.float64)
    b = 0.0
    for _ in range(epochs):
        z = Xs @ w + b
        p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
        err = p - y
        gw = (Xs.T @ err) / n
        gb = float(err.mean())
        w -= lr * gw
        b -= lr * gb
    return w, b, mean, std


def predict_proba(w: np.ndarray, b: float, X: np.ndarray,
                  mean: np.ndarray | None = None, std: np.ndarray | None = None) -> np.ndarray:
    X = np.asarray(X, dtype=np.float64)
    if X.ndim == 1:
        X = X[None, :]
    if mean is not None and std is not None:
        X = (X - mean) / std
    z = X @ w + b
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def update_prior_weights(stats: dict[str, dict], priors: dict[str, float],
                         cfg: Config) -> tuple[dict[str, float], bool]:
    """p_i = normalize(accuracy_i * calib_i + eps) con cap anti-drift.

    stats: {capa: {hits, total, conf_hit, conf_fail}} (acumulado diario).
    Devuelve (pesos, aplicado) — aplicado=False si no hay datos suficientes.
    """
    raw: dict[str, float] = {}
    for name, p in priors.items():
        st = stats.get(name)
        if not st or st.get("total", 0) < 5:
            raw[name] = p
            continue
        acc = st["hits"] / max(1, st["total"])
        calib = 1.0 - abs(st.get("conf_hit", 0.5) - st.get("conf_fail", 0.5))
        raw[name] = max(EPS, acc * calib + EPS)
    total = sum(raw.values())
    if total <= 0:
        return dict(priors), False
    # cap anti-drift: |Δp_i| <= calib_lr por día (aplicado sobre el target normalizado)
    out: dict[str, float] = {}
    applied = False
    capped = False
    for name, p in priors.items():
        target = raw[name] / total
        delta = target - p
        clipped = p + np.clip(delta, -cfg.calib_lr, cfg.calib_lr)
        if abs(delta) > cfg.calib_lr + 1e-12:
            capped = True
        if abs(clipped - p) > 1e-9:
            applied = True
        out[name] = float(clipped)
    # re-normalizar SOLO si ningún cap se ha disparado (si no, el cap se rompe)
    if not capped:
        s = sum(out.values())
        if s > 0:
            out = {k: v / s for k, v in out.items()}
    return out, applied


def validate_held_out(w: np.ndarray, b: float, X: np.ndarray, y: np.ndarray,
                      far_target: float = 0.01,
                      mean: np.ndarray | None = None, std: np.ndarray | None = None) -> tuple[float, float, float]:
    """TAR/FAR en held-out para decidir si se despliega la calibración.

    Devuelve (tar, far, umbral) con umbral en probabilidad [0..1].
    """
    if len(X) == 0 or len(set(y)) < 2:
        return float("nan"), float("nan"), float("nan")
    p = predict_proba(w, b, X, mean, std).ravel()
    pos = p[y == 1]
    neg = p[y == 0]
    if len(neg) == 0 or len(pos) == 0:
        return float("nan"), float("nan"), float("nan")
    thr = float(np.percentile(neg, 100 * (1 - far_target)))
    tar = float(np.mean(pos >= thr))
    far = float(np.mean(neg >= thr))
    return tar, far, thr


class CalibrationModel:
    """Modelo de calibración versionado (pickle + journal) y reversible."""

    def __init__(self, calib_dir: str):
        self.calib_dir = calib_dir
        self.w: np.ndarray | None = None
        self.b: float = 0.0
        self.mean: np.ndarray | None = None
        self.std: np.ndarray | None = None
        self.weights: dict[str, float] = {}
        self.weights_applied: bool = False

    @property
    def path(self) -> str:
        return os.path.join(self.calib_dir, "calib_model.pkl")

    def save(self, meta: dict | None = None) -> str:
        os.makedirs(self.calib_dir, exist_ok=True)
        ts = time.time()
        fname = f"calib_{ts:.0f}.pkl"
        path = os.path.join(self.calib_dir, fname)
        with open(path, "wb") as fh:
            pickle.dump({"w": self.w, "b": self.b, "mean": self.mean, "std": self.std,
                         "weights": self.weights, "applied": self.weights_applied,
                         "meta": meta or {}}, fh)
        # journal (append-only) para reversibilidad
        with open(os.path.join(self.calib_dir, "journal.jsonl"), "a") as fh:
            fh.write(json.dumps({"ts": ts, "file": fname, "applied": self.weights_applied,
                                 "weights": self.weights}) + "\n")
        return path

    def load(self, path: str | None = None) -> bool:
        path = path or self.path
        if not os.path.exists(path):
            return False
        with open(path, "rb") as fh:
            data = pickle.load(fh)
        self.w = data.get("w")
        self.b = data.get("b", 0.0)
        self.mean = data.get("mean")
        self.std = data.get("std")
        self.weights = data.get("weights", {})
        self.weights_applied = data.get("applied", False)
        return True
