"""Cliente OpenAI (L3, gpt-4o-mini) — SOLO último recurso (F5).

Reglas:
  - Solo tras L2 (VLM local) y en gris.
  - PRESUPUESTO DIARIO (RF_LLM_DAILY_BUDGET): contador persistente por fecha;
    agotado => capa no disponible (degradación, no bloqueo).
  - CACHE por par (hash de las 2 imágenes): no reenviar lo ya preguntado.
  - timeout/retry configurables.
  - Privacidad: no se persisten las fotos; solo hash + resultado en cache.
  - La key vive en .env (RF_LLM_API_KEY), nunca en código ni commits.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time

import requests

from .config import Config
from .matching import LayerScore
from .prompts import SYSTEM_PROMPT, USER_PROMPT, map_to_layer
from .attributes import ATTRIBUTES_PROMPT, parse_attributes_response
from .vlm_local import _pair_key

URL = "https://api.openai.com/v1/chat/completions"


class OpenAICompare:
    def __init__(self, cfg: Config, ruta: str):
        self.cfg = cfg
        self.cache_dir = os.path.join(ruta, cfg.llm_cache_dir, "openai")
        self.budget_file = os.path.join(self.cache_dir, "budget.json")
        os.makedirs(self.cache_dir, exist_ok=True)

    # --- presupuesto diario ---

    def _today(self) -> str:
        return time.strftime("%Y-%m-%d")

    def _read_budget(self) -> int:
        try:
            with open(self.budget_file) as fh:
                data = json.load(fh)
            if data.get("date") == self._today():
                return int(data.get("used", 0))
        except (OSError, json.JSONDecodeError, ValueError):
            pass
        return 0

    def _spend(self) -> None:
        used = self._read_budget() + 1
        tmp = self.budget_file + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"date": self._today(), "used": used}, fh)
        os.replace(tmp, self.budget_file)

    def budget_remaining(self) -> int:
        return max(0, self.cfg.llm_daily_budget - self._read_budget())

    # --- cache por par ---

    def _cache_path(self, key: str) -> str:
        return os.path.join(self.cache_dir, key + ".json")

    def _read_cache(self, key: str):
        p = self._cache_path(key)
        if os.path.exists(p):
            try:
                with open(p) as fh:
                    return json.load(fh)
            except (OSError, json.JSONDecodeError):
                return None
        return None

    def _write_cache(self, key: str, s: float, c: float) -> None:
        p = self._cache_path(key)
        tmp = p + ".tmp"
        with open(tmp, "w") as fh:
            json.dump({"s": s, "c": c, "ts": time.time()}, fh)
        os.replace(tmp, p)

    # --- llamada ---

    def compare(self, img_a: str, img_b: str) -> LayerScore:
        if not self.cfg.openai_enabled or not self.cfg.llm_api_key:
            return LayerScore(available=False)
        if self.budget_remaining() <= 0:
            return LayerScore(available=False)          # presupuesto agotado: degradar
        key = _pair_key(img_a, img_b)
        cached = self._read_cache(key)
        if cached is not None:
            return LayerScore(score=cached["s"], confidence=cached["c"], available=True)

        headers = {"Authorization": f"Bearer {self.cfg.llm_api_key}"}
        payload = {
            "model": self.cfg.llm_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(img_a)}"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(img_b)}"}},
                ]},
            ],
            "max_tokens": 400,
            "response_format": {"type": "json_object"},
        }
        last_err: Exception | None = None
        for attempt in range(1 + self.cfg.openai_retries):
            try:
                r = requests.post(URL, headers=headers, json=payload,
                                  timeout=self.cfg.openai_timeout_s)
                r.raise_for_status()
                content = r.json()["choices"][0]["message"]["content"]
                result = json.loads(content)
                s, c = map_to_layer(result)
                if c > 0:
                    self._spend()                        # solo se descuenta si aporta señal
                    self._write_cache(key, s, c)
                return LayerScore(score=s, confidence=c, available=c > 0.0)
            except Exception as e:  # noqa: BLE001
                last_err = e
                time.sleep(1.0 * (attempt + 1))
        return LayerScore(available=False)

    def attributes(self, image: str) -> dict | None:
        """Extract only the versioned structured attribute contract."""
        if not self.cfg.attributes_enabled or not self.cfg.openai_enabled or not self.cfg.llm_api_key:
            return None
        if self.budget_remaining() <= 0:
            return None
        try:
            r = requests.post(URL, headers={"Authorization": f"Bearer {self.cfg.llm_api_key}"},
                json={"model": self.cfg.llm_model,
                      "messages": [{"role": "system", "content": ATTRIBUTES_PROMPT},
                                   {"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(image)}"}}]}],
                      "max_tokens": 180, "response_format": {"type": "json_object"}},
                timeout=self.cfg.openai_timeout_s)
            r.raise_for_status()
            result = parse_attributes_response(r.json()["choices"][0]["message"]["content"])
            if result is not None:
                self._spend()
            return result
        except Exception:  # noqa: BLE001
            return None


def _b64(path: str) -> str:
    """Base64 de la imagen REDIMENSIONADA (misma política que el VLM local).

    Reduce tokens de visión (coste y latencia) en gpt-4o-mini. Si no se puede
    leer con cv2, se envía el fichero tal cual (fallback).
    """
    import cv2
    from .vlm_local import VLM_IMG_JPEG_QUALITY, VLM_IMG_MAX_SIDE
    img = cv2.imread(path)
    if img is None:
        with open(path, "rb") as fh:
            return base64.b64encode(fh.read()).decode()
    h, w = img.shape[:2]
    m = max(h, w)
    if m > VLM_IMG_MAX_SIDE:
        sc = VLM_IMG_MAX_SIDE / m
        img = cv2.resize(img, (max(1, int(w * sc)), max(1, int(h * sc))),
                         interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, VLM_IMG_JPEG_QUALITY])
    if not ok:
        with open(path, "rb") as fh:
            return base64.b64encode(fh.read()).decode()
    return base64.b64encode(buf.tobytes()).decode()
