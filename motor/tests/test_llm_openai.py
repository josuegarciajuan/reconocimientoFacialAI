"""Tests del cliente OpenAI (F5, L3) con HTTP mockeado (sin red ni key)."""
import json

from motor.core.config import Config
from motor.core.llm_openai import OpenAICompare
from motor.core.matching import LayerScore


def _make_cfg(tmp_path, **over):
    cfg = Config(openai_enabled=True, llm_api_key="sk-test-no-real",
                 llm_model="gpt-4o-mini", llm_daily_budget=10,
                 openai_timeout_s=5.0, openai_retries=0)
    for k, v in over.items():
        setattr(cfg, k, v)
    return cfg


def _img(tmp_path, name="a.jpg", color=(60, 120, 180)):
    import cv2
    import numpy as np
    p = tmp_path / name
    img = np.zeros((64, 64, 3), dtype=np.uint8)
    img[:, :] = color
    cv2.imwrite(str(p), img)
    return str(p)


def test_openai_parses_json(monkeypatch, tmp_path):
    cfg = _make_cfg(tmp_path)
    client = OpenAICompare(cfg, str(tmp_path))

    def fake_post(url, **kwargs):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"choices": [{"message": {"content": json.dumps(
                    {"probability_same": 0.95, "confidence": 0.9, "reasoning": "ok", "skip": False})}}]}
        return R()

    monkeypatch.setattr("requests.post", fake_post)
    ls = client.compare(_img(tmp_path, "a.jpg"), _img(tmp_path, "b.jpg"))
    assert isinstance(ls, LayerScore)
    assert ls.available and abs(ls.score - 0.95) < 1e-9


def test_openai_budget_exhausted_degrades(monkeypatch, tmp_path):
    cfg = _make_cfg(tmp_path)
    client = OpenAICompare(cfg, str(tmp_path))
    # gastamos todo el presupuesto
    while client.budget_remaining() > 0:
        client._spend()
    called = []

    def fake_post(url, **kwargs):
        called.append(1)
        raise AssertionError("no debe llamar")
    monkeypatch.setattr("requests.post", fake_post)
    ls = client.compare(_img(tmp_path, "a.jpg"), _img(tmp_path, "b.jpg"))
    assert not called
    assert not ls.available


def test_openai_cache_avoids_spend(monkeypatch, tmp_path):
    cfg = _make_cfg(tmp_path)
    client = OpenAICompare(cfg, str(tmp_path))
    calls = {"n": 0}

    def fake_post(url, **kwargs):
        calls["n"] += 1
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"choices": [{"message": {"content": json.dumps(
                    {"probability_same": 0.8, "confidence": 0.7, "reasoning": "ok", "skip": False})}}]}
        return R()

    monkeypatch.setattr("requests.post", fake_post)
    a, b = _img(tmp_path, "a.jpg"), _img(tmp_path, "b.jpg")
    used_before = client._read_budget()
    client.compare(a, b)
    client.compare(a, b)
    assert calls["n"] == 1
    assert client._read_budget() == used_before + 1   # solo una llamada con señal


def test_openai_retry_then_succeed(monkeypatch, tmp_path):
    cfg = _make_cfg(tmp_path, openai_retries=2)
    client = OpenAICompare(cfg, str(tmp_path))
    state = {"n": 0}

    def fake_post(url, **kwargs):
        state["n"] += 1
        if state["n"] < 2:
            raise ConnectionError("red caída")
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"choices": [{"message": {"content": json.dumps(
                    {"probability_same": 0.7, "confidence": 0.6, "reasoning": "ok", "skip": False})}}]}
        return R()

    monkeypatch.setattr("requests.post", fake_post)
    ls = client.compare(_img(tmp_path, "a.jpg"), _img(tmp_path, "b.jpg"))
    assert state["n"] == 2
    assert ls.available


def test_openai_disabled_without_key(tmp_path):
    cfg = _make_cfg(tmp_path, openai_enabled=True, llm_api_key="")
    client = OpenAICompare(cfg, str(tmp_path))
    assert not client.compare(_img(tmp_path, "a.jpg"), _img(tmp_path, "b.jpg")).available
