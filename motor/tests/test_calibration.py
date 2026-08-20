"""Tests de calibración (F3, §5): regresión logística, anti-drift, versionado."""
import numpy as np

from motor.core.calibration import (CalibrationModel, layer_stats_by_situation,
                                    logistic_fit, predict_proba,
                                    situation_class, update_prior_weights,
                                    validate_held_out)


def test_situation_class():
    assert situation_class("pi") == "perfil"
    assert situation_class("pd") == "perfil"
    assert situation_class("m45i") == "angulos"
    assert situation_class("arr") == "angulos"
    assert situation_class("f") == "frontal"
    assert situation_class(None) == "otro"


def test_layer_stats_by_situation_groups_by_pose():
    """Fiabilidad por capa condicionada a la situación (F4)."""
    # 2 filas: una perfil genuina (acierto) y una frontal impostora (fallo)
    X = np.array([
        [0.5, 0.8, 0.4, 0.3, 0.4, 0.2, 0.5, 0.0, 0.5, 0.0],   # s_cara,c_cara,...
        [0.4, 0.6, 0.3, 0.5, 0.4, 0.2, 0.5, 0.0, 0.5, 0.0],
    ])
    y = np.array([1, 0])
    situ = ["pi", "f"]
    stats = layer_stats_by_situation(X, y, situ)
    assert set(stats) == {"perfil", "frontal"}
    # la columna de confianza de cara (índice 1) acumula c_hit en perfil
    assert stats["perfil"]["cara"]["hits"] == 1
    assert stats["frontal"]["cara"]["hits"] == 0
    assert stats["perfil"]["cara"]["conf_hit"] == 0.8

def test_logistic_fit_separable():
    rng = np.random.default_rng(7)
    pos = rng.uniform(0.6, 1.0, (30, 2))
    neg = rng.uniform(0.0, 0.4, (30, 2))
    X = np.vstack([pos, neg])
    y = np.array([1] * 30 + [0] * 30)
    w, b, mean, std = logistic_fit(X, y, epochs=500, lr=0.1)
    p = predict_proba(w, b, X, mean, std).ravel()
    assert p[:30].mean() > 0.9
    assert p[30:].mean() < 0.1


def test_update_weights_rewards_accurate_confident():
    cfg = type("Cfg", (), {"calib_lr": 0.15})()
    priors = {"cara": 0.60, "torso": 0.15, "llm": 0.25}
    stats = {
        "cara": {"hits": 90, "total": 100, "conf_hit": 0.6, "conf_fail": 0.5},
        # acierta mucho y su confianza es estable (calibrada) -> sube
        "torso": {"hits": 50, "total": 100, "conf_hit": 0.6, "conf_fail": 0.5},
        "llm": {"hits": 10, "total": 100, "conf_hit": 0.9, "conf_fail": 0.1},
        # falla casi siempre y con confianza alta cuando falla (sobreconfiada) -> baja
    }
    out, applied = update_prior_weights(stats, priors, cfg)
    assert applied
    # con caps activos la suma puede desviarse ligeramente de 1 (por diseño:
    # re-normalizar rompería el cap anti-drift); la fusión re-normaliza al usar.
    assert abs(sum(out.values()) - 1.0) < 0.1
    assert out["cara"] > priors["cara"]          # acierta mucho y con confianza -> sube
    assert out["llm"] < priors["llm"]            # falla con confianza alta -> baja


def test_update_weights_insufficient_data_not_applied():
    cfg = type("Cfg", (), {"calib_lr": 0.15})()
    priors = {"cara": 0.60, "torso": 0.15, "llm": 0.25}
    stats = {"cara": {"hits": 2, "total": 3, "conf_hit": 0.9, "conf_fail": 0.3}}
    out, applied = update_prior_weights(stats, priors, cfg)
    assert not applied
    assert out == priors


def test_update_weights_caps_delta():
    cfg = type("Cfg", (), {"calib_lr": 0.05})()
    priors = {"cara": 0.60, "torso": 0.15, "llm": 0.25}
    stats = {"cara": {"hits": 100, "total": 100, "conf_hit": 0.7, "conf_fail": 0.6}}
    out, _ = update_prior_weights(stats, priors, cfg)
    assert abs(out["cara"] - priors["cara"]) <= cfg.calib_lr + 1e-9


def test_validate_held_out():
    rng = np.random.default_rng(7)
    X = rng.uniform(0, 1, (40, 2))
    y = (X[:, 0] > 0.5).astype(int)
    w, b, mean, std = logistic_fit(X, y, epochs=400, lr=0.1)
    tar, far, thr = validate_held_out(w, b, X, y, far_target=0.05, mean=mean, std=std)
    assert tar >= 0.9
    assert far <= 0.06


def test_model_versioned_save_load(tmp_path):
    m = CalibrationModel(str(tmp_path))
    m.w = np.array([1.0, -1.0])
    m.b = 0.1
    m.mean = np.array([0.5, 0.5])
    m.std = np.array([1.0, 1.0])
    m.weights = {"cara": 0.7}
    m.weights_applied = True
    path = m.save(meta={"n": 10})
    m2 = CalibrationModel(str(tmp_path))
    assert m2.load(path)
    np.testing.assert_allclose(m2.w, m.w)
    np.testing.assert_allclose(m2.mean, m.mean)
    assert m2.weights == m.weights and m2.weights_applied
