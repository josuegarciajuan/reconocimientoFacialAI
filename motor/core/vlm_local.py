"""Cliente del worker VLM local (L2) — Ollama, UN ÚNICO worker compartido.

Reglas de entorno (F0-F7, §8): CPU-only, 18.5 GiB RAM, 10 clasificadores.
El modelo (qwen2.5vl:3b, ~3.2 GB) se carga UNA sola vez en el servicio Ollama
(puerto 11434); los clasificadores le hacen peticiones HTTP. NUNCA una copia
por daemon.

MEDIDAS ANTI-DESBORDE:
  - memory guard: RAM libre < vlm_ram_skip_gb => omitir (c_vlm=0);
    < vlm_ram_defer_gb => no llamar (diferir; el par queda para la siguiente pasada).
  - mutex global (FileLock): solo UNA llamada VLM en curso entre todos los
    procesos (protege RAM y serializa el worker).
  - timeout por llamada (vlm_timeout_s); si se supera => c=0 para ese par.
  - cache por hash-de-par: no reenviar lo ya preguntado.
  - si el lock no se consigue en ~5 s => degradar (available=False), no bloquear.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time

import requests
from filelock import FileLock

from .config import Config
from .matching import LayerScore
from .prompts import SYSTEM_PROMPT, USER_PROMPT, map_to_layer

LOCK_TIMEOUT_S = 5.0


def _mem_free_gb() -> float:
    """RAM libre (MemAvailable) en GiB, leyendo /proc/meminfo (sin psutil)."""
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                if line.startswith("MemAvailable:"):
                    return float(line.split()[1]) / (1024.0 * 1024.0)
    except OSError:
        return 99.0
    return 99.0


class VLMClient:
    def __init__(self, cfg: Config, ruta: str):
        self.cfg = cfg
        self.cache_dir = os.path.join(ruta, cfg.llm_cache_dir, "vlm")
        self.url = f"{cfg.vlm_base_url}/api/chat"
        os.makedirs(self.cache_dir, exist_ok=True)

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

    def compare(self, img_a: str, img_b: str) -> LayerScore:
        """Compara dos imágenes de la persona candidata. Nunca bloquea el flujo."""
        if not self.cfg.vlm_enabled:
            return LayerScore(available=False)
        key = _pair_key(img_a, img_b)
        cached = self._read_cache(key)
        if cached is not None:
            return LayerScore(score=cached["s"], confidence=cached["c"], available=True)

        # MEMORY GUARD
        free = _mem_free_gb()
        if free < self.cfg.vlm_ram_skip_gb:
            return LayerScore(available=False)          # omitir
        if free < self.cfg.vlm_ram_defer_gb:
            return LayerScore(available=False)          # diferir (siguiente pasada)

        # MUTEX GLOBAL: solo 1 llamada VLM en curso (entre todos los daemons)
        lock_path = os.path.join(self.cache_dir, ".vlm.lock")
        try:
            with FileLock(lock_path, timeout=LOCK_TIMEOUT_S):
                result = self._call(img_a, img_b)
        except TimeoutError:
            return LayerScore(available=False)          # cola llena: degradar
        except Exception:  # noqa: BLE001 — red/worker caído: degradar
            return LayerScore(available=False)

        s, c = map_to_layer(result)
        if c > 0:
            self._write_cache(key, s, c)
        return LayerScore(score=s, confidence=c, available=c > 0.0)

    def _call(self, img_a: str, img_b: str) -> dict:
        payload = {
            "model": self.cfg.vlm_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT, "images": [_b64(img_a), _b64(img_b)]},
            ],
            "stream": False,
            "options": {"num_ctx": self.cfg.vlm_num_ctx, "num_gpu": self.cfg.vlm_num_gpu},
            "keep_alive": self.cfg.vlm_keep_alive_s,
        }
        r = requests.post(self.url, json=payload, timeout=self.cfg.vlm_timeout_s)
        r.raise_for_status()
        content = r.json()["message"]["content"]
        start = content.find("{")
        end = content.rfind("}") + 1
        if start < 0 or end <= start:
            return {"probability_same": 0.5, "skip": True}
        return json.loads(content[start:end])


def _b64(path: str) -> str:
    with open(path, "rb") as fh:
        return base64.b64encode(fh.read()).decode()


def _pair_key(img_a: str, img_b: str) -> str:
    h = hashlib.sha256()
    for p in sorted([img_a, img_b]):
        with open(p, "rb") as fh:
            h.update(fh.read())
    return h.hexdigest()
