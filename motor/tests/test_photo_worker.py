"""Tests de motor/photo_worker.py — parser de jobs y limpieza, sin modelos reales.

Se monkeypatchean `photo_busto` / `photo_busto_fused` para aislar el contrato del
worker (lectura del JSON, selección MF-SR, escritura `<out>.hq` y borrado de
fuentes). No se toca `main()` ni `/proc/loadavg`.
"""
from __future__ import annotations

import json
import os
import time

import cv2
import numpy as np

import motor.photo_worker as pw
from motor.core.config import Config


# ------------------------------------------------------------------ helpers

def _write_png(path, w: int = 20, h: int = 20) -> str:
    """Escribe un PNG real (cv2.imwrite) y devuelve su ruta como str."""
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[5:15, 5:15] = 200
    assert cv2.imwrite(str(path), img)
    return str(path)


def _write_job(path, job: dict) -> str:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(job, fh)
    return str(path)


def _install_fakes(monkeypatch, calls: dict) -> None:
    """Sustituye los dos productores por fakes que cuentan llamadas."""
    def fake_busto(*_a, **_k):
        calls["busto"] += 1
        return np.zeros((10, 10, 3), np.uint8)

    def fake_fused(*a, **_k):
        calls["fused"] += 1
        calls["fused_frames"] = a[0] if a else None
        if calls.get("fused_returns_none"):
            return None
        return np.zeros((10, 10, 3), np.uint8)

    monkeypatch.setattr(pw, "photo_busto", fake_busto)
    monkeypatch.setattr(pw, "photo_busto_fused", fake_fused)


def _hq(out: str) -> str:
    return out + ".hq"


# --------------------------------------------------- _process_job: 1 frame

def test_process_job_single_frame_new_format(tmp_path, monkeypatch):
    """Formato nuevo `{frames:[...], out}` con 1 frame -> photo_busto + limpieza."""
    cfg = Config()
    cfg.sr_mf_enabled = True                 # con 1 frame no debe usar MF-SR
    calls = {"busto": 0, "fused": 0}
    _install_fakes(monkeypatch, calls)

    src = _write_png(tmp_path / "f0.png")
    out = str(tmp_path / "photo.jpg")
    jp = _write_job(tmp_path / "job.json",
                    {"frames": [{"src": src, "bbox": [2, 2, 18, 18]}],
                     "out": out, "ts": 0})

    pw._process_job(jp, cfg)

    assert os.path.exists(_hq(out))
    assert not os.path.exists(jp)
    assert not os.path.exists(src)
    assert calls["busto"] == 1
    assert calls["fused"] == 0


def test_process_job_legacy_single_frame(tmp_path, monkeypatch):
    """Formato legacy `{src, out, bbox}`: misma ruta de un frame."""
    cfg = Config()
    calls = {"busto": 0, "fused": 0}
    _install_fakes(monkeypatch, calls)

    src = _write_png(tmp_path / "legacy.png")
    out = str(tmp_path / "legacy.jpg")
    jp = _write_job(tmp_path / "legacy.json",
                    {"src": src, "out": out, "bbox": [2, 2, 18, 18]})

    pw._process_job(jp, cfg)

    assert os.path.exists(_hq(out))
    assert not os.path.exists(jp)
    assert not os.path.exists(src)
    assert calls["busto"] == 1
    assert calls["fused"] == 0


# --------------------------------------------------- _process_job: 2 frames

def test_process_job_two_frames_uses_fused_when_enabled(tmp_path, monkeypatch):
    """>=2 frames + sr_mf_enabled -> photo_busto_fused; borra TODAS las fuentes."""
    cfg = Config()
    cfg.sr_mf_enabled = True
    calls = {"busto": 0, "fused": 0}
    _install_fakes(monkeypatch, calls)

    s0 = _write_png(tmp_path / "a.png")
    s1 = _write_png(tmp_path / "b.png")
    out = str(tmp_path / "mf.jpg")
    jp = _write_job(tmp_path / "mf.json",
                    {"frames": [{"src": s0, "bbox": [2, 2, 18, 18]},
                                {"src": s1, "bbox": [2, 2, 18, 18]}],
                     "out": out})

    pw._process_job(jp, cfg)

    assert os.path.exists(_hq(out))
    assert not os.path.exists(jp)
    assert not os.path.exists(s0) and not os.path.exists(s1)
    assert calls["fused"] == 1
    assert calls["busto"] == 0
    assert len(calls["fused_frames"]) == 2


def test_process_job_two_frames_mf_disabled_uses_single(tmp_path, monkeypatch):
    """Con sr_mf_enabled=False, >=2 frames caen a photo_busto(frame 0)."""
    cfg = Config()
    cfg.sr_mf_enabled = False
    calls = {"busto": 0, "fused": 0}
    _install_fakes(monkeypatch, calls)

    s0 = _write_png(tmp_path / "a.png")
    s1 = _write_png(tmp_path / "b.png")
    out = str(tmp_path / "single.jpg")
    jp = _write_job(tmp_path / "single.json",
                    {"frames": [{"src": s0, "bbox": [2, 2, 18, 18]},
                                {"src": s1, "bbox": [2, 2, 18, 18]}],
                     "out": out})

    pw._process_job(jp, cfg)

    assert os.path.exists(_hq(out))
    assert calls["fused"] == 0
    assert calls["busto"] == 1
    assert not os.path.exists(s0) and not os.path.exists(s1)


def test_process_job_mf_none_falls_back_to_busto(tmp_path, monkeypatch):
    """Si MF-SR devuelve None (sin material), el worker cae a photo_busto."""
    cfg = Config()
    cfg.sr_mf_enabled = True
    calls = {"busto": 0, "fused": 0, "fused_returns_none": True}
    _install_fakes(monkeypatch, calls)

    s0 = _write_png(tmp_path / "a.png")
    s1 = _write_png(tmp_path / "b.png")
    out = str(tmp_path / "fallback.jpg")
    jp = _write_job(tmp_path / "fallback.json",
                    {"frames": [{"src": s0, "bbox": [2, 2, 18, 18]},
                                {"src": s1, "bbox": [2, 2, 18, 18]}],
                     "out": out})

    pw._process_job(jp, cfg)

    assert os.path.exists(_hq(out))
    assert calls["fused"] == 1
    assert calls["busto"] == 1


# --------------------------------------------------- _process_job: degradación

def test_process_job_missing_out_cleans_up(tmp_path, monkeypatch):
    """Job sin `out` no lanza, no genera HQ y limpia la fuente."""
    cfg = Config()
    calls = {"busto": 0, "fused": 0}
    _install_fakes(monkeypatch, calls)

    src = _write_png(tmp_path / "noout.png")
    jp = _write_job(tmp_path / "noout.json",
                    {"src": src, "bbox": [2, 2, 18, 18]})

    pw._process_job(jp, cfg)

    assert not os.path.exists(jp)
    assert not os.path.exists(src)
    assert calls["busto"] == 0 and calls["fused"] == 0


def test_process_job_no_valid_frames_cleans_up(tmp_path, monkeypatch):
    """Frames con bbox inválido / src inexistente: no lanza y descarta el job."""
    cfg = Config()
    calls = {"busto": 0, "fused": 0}
    _install_fakes(monkeypatch, calls)

    src = _write_png(tmp_path / "declared.png")
    out = str(tmp_path / "none.jpg")
    jp = _write_job(tmp_path / "none.json",
                    {"frames": [{"src": str(tmp_path / "missing.png"),
                                 "bbox": [1, 2, 3, 4]},
                                {"src": src, "bbox": [1, 2, 3]},   # bbox inválido
                                {"src": "", "bbox": [1, 2, 3, 4]}],
                     "out": out})

    pw._process_job(jp, cfg)

    assert not os.path.exists(jp)
    assert not os.path.exists(_hq(out))
    # _discard_job borra toda fuente declarada, aunque su bbox sea inválido
    assert not os.path.exists(src)
    assert calls["busto"] == 0 and calls["fused"] == 0


def test_process_job_expired_ttl_discards(tmp_path, monkeypatch):
    """Un job más viejo que JOB_TTL_S se descarta sin procesar."""
    cfg = Config()
    calls = {"busto": 0, "fused": 0}
    _install_fakes(monkeypatch, calls)

    src = _write_png(tmp_path / "old.png")
    out = str(tmp_path / "old.jpg")
    jp = _write_job(tmp_path / "old.json",
                    {"frames": [{"src": src, "bbox": [2, 2, 18, 18]}], "out": out})
    old = time.time() - pw.JOB_TTL_S - 60
    os.utime(jp, (old, old))

    pw._process_job(jp, cfg)

    assert not os.path.exists(jp)
    assert not os.path.exists(src)
    assert not os.path.exists(_hq(out))
    assert calls["busto"] == 0 and calls["fused"] == 0


# ------------------------------------------------------------- _discard_job

def test_discard_job_removes_all_frames_sources(tmp_path):
    """_discard_job borra todas las fuentes declaradas (frames + src legacy)."""
    s0 = _write_png(tmp_path / "d0.png")
    s1 = _write_png(tmp_path / "d1.png")
    legacy = _write_png(tmp_path / "legacy_discard.png")
    jp = _write_job(tmp_path / "discard.json",
                    {"frames": [{"src": s0, "bbox": [0, 0, 5, 5]},
                                {"src": s1, "bbox": [0, 0, 5, 5]}],
                     "src": legacy, "out": "x"})

    pw._discard_job(jp)

    assert not os.path.exists(jp)
    assert not os.path.exists(s0)
    assert not os.path.exists(s1)
    assert not os.path.exists(legacy)


def test_discard_job_corrupt_json_still_removes_job(tmp_path):
    """JSON ilegible: se ignora el error y el JSON se elimina igualmente."""
    jp = tmp_path / "corrupt.json"
    jp.write_text("{no es json", encoding="utf-8")

    pw._discard_job(str(jp))

    assert not jp.exists()
