"""Tests del cliente VLM local (F4, L2) con HTTP mockeado (sin red ni modelo)."""
import json

import pytest

from motor.core.config import Config
from motor.core.matching import LayerScore
from motor.core.vlm_local import VLMClient


def _make_cfg(tmp_path, **over):
    cfg = Config(vlm_enabled=True, vlm_base_url="http://ollama:11434",
                 vlm_model="qwen2.5vl:3b", vlm_timeout_s=5.0, vlm_keep_alive_s=60.0,
                 vlm_ram_skip_gb=0.0, vlm_ram_defer_gb=0.0)   # memory guard desactivado
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


def test_compare_parses_json(monkeypatch, tmp_path):
    cfg = _make_cfg(tmp_path)
    client = VLMClient(cfg, str(tmp_path))

    def fake_post(url, **kwargs):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"message": {"content": json.dumps(
                    {"probability_same": 0.9, "confidence": 0.8, "reasoning": "ok", "skip": False})}}
        return R()

    monkeypatch.setattr("requests.post", fake_post)
    ls = client.compare(_img(tmp_path, "a.jpg"), _img(tmp_path, "b.jpg"))
    assert isinstance(ls, LayerScore)
    assert ls.available and ls.confidence > 0.7    # c = |0.9-0.5|*2 = 0.8
    assert abs(ls.score - 0.9) < 1e-9


def test_compare_cache_avoids_network(monkeypatch, tmp_path):
    cfg = _make_cfg(tmp_path)
    client = VLMClient(cfg, str(tmp_path))
    calls = {"n": 0}

    def fake_post(url, **kwargs):
        calls["n"] += 1
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"message": {"content": json.dumps(
                    {"probability_same": 0.8, "confidence": 0.7, "reasoning": "ok", "skip": False})}}
        return R()

    monkeypatch.setattr("requests.post", fake_post)
    a, b = _img(tmp_path, "a.jpg"), _img(tmp_path, "b.jpg")
    client.compare(a, b)
    client.compare(a, b)
    assert calls["n"] == 1


def test_compare_timeout_degrades(monkeypatch, tmp_path):
    cfg = _make_cfg(tmp_path)
    client = VLMClient(cfg, str(tmp_path))

    def boom(url, json=None, timeout=None):
        raise TimeoutError("timeout")

    monkeypatch.setattr("requests.post", boom)
    ls = client.compare(_img(tmp_path, "a.jpg"), _img(tmp_path, "b.jpg"))
    assert not ls.available


def test_compare_memory_guard_skips(monkeypatch, tmp_path):
    cfg = _make_cfg(tmp_path, vlm_ram_skip_gb=99.0)   # RAM libre simulada < umbral
    client = VLMClient(cfg, str(tmp_path))
    called = []

    def fake_post(url, **kwargs):
        called.append(1)
        raise AssertionError("no debe llamar")
    monkeypatch.setattr("requests.post", fake_post)
    ls = client.compare(_img(tmp_path, "a.jpg"), _img(tmp_path, "b.jpg"))
    assert not called
    assert not ls.available


def test_compare_disabled_flag(tmp_path):
    cfg = _make_cfg(tmp_path, vlm_enabled=False)
    client = VLMClient(cfg, str(tmp_path))
    assert not client.compare(_img(tmp_path, "a.jpg"), _img(tmp_path, "b.jpg")).available


def test_compare_lock_timeout_degrades(monkeypatch, tmp_path):
    """Si el mutex global no se consigue, degrada (no bloquea)."""
    cfg = _make_cfg(tmp_path)
    client = VLMClient(cfg, str(tmp_path))
    lock_path = client.cache_dir + "/.vlm.lock"

    from filelock import FileLock, Timeout
    # ocupamos el lock antes de la llamada
    held = FileLock(lock_path)
    held.acquire()
    try:
        ls = client.compare(_img(tmp_path, "a.jpg"), _img(tmp_path, "b.jpg"))
        assert not ls.available
    finally:
        held.release()
