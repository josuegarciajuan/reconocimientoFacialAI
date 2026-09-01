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
  - IMÁGENES REDIMENSIONADAS (max side VLM_IMG_MAX_SIDE): la codificación de
    visión en CPU es cara; a tamaño completo 2 imágenes generan ~2100 tokens
    (superaban num_ctx y tardaban minutos bajo carga). 384px -> ~500-900 tokens.
  - cache por hash-de-par: no reenviar lo ya preguntado.
  - si el lock no se consigue en ~5 s => degradar (available=False), no bloquear.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time

import cv2
import requests
from filelock import FileLock

from .config import Config
from .matching import LayerScore
from .prompts import SYSTEM_PROMPT, USER_PROMPT, map_to_layer, validate_identity_response
from .attributes import ATTRIBUTES_PROMPT, parse_attributes_response

LOCK_TIMEOUT_S = 5.0
VLM_IMG_MAX_SIDE = 384
VLM_IMG_JPEG_QUALITY = 85


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
        result = json.loads(content[start:end])
        if not validate_identity_response(result):
            return {"probability_same": 0.5, "confidence": 0.0, "skip": True}
        return result

    def attributes(self, image: str) -> dict | None:
        """Extract versioned visible attributes; unavailable on any failure."""
        if not self.cfg.attributes_enabled or not self.cfg.vlm_enabled:
            return None
        try:
            with FileLock(os.path.join(self.cache_dir, ".vlm.lock"), timeout=LOCK_TIMEOUT_S):
                r = requests.post(self.url, json={"model": self.cfg.vlm_model,
                    "messages": [{"role": "user", "content": ATTRIBUTES_PROMPT,
                                  "images": [_b64(image)]}], "stream": False,
                    "options": {"num_ctx": self.cfg.vlm_num_ctx, "num_gpu": self.cfg.vlm_num_gpu}},
                    timeout=self.cfg.vlm_timeout_s)
                r.raise_for_status()
                return parse_attributes_response(r.json()["message"]["content"])
        except Exception:  # noqa: BLE001
            return None


def _b64(path: str) -> str:
    """Base64 de la imagen REDIMENSIONADA (máx. 384px) para reducir tokens de visión."""
    if not os.path.isfile(path) or os.path.getsize(path) > 5 * 1024 * 1024:
        raise ValueError("image rejected by size/type policy")
    img = cv2.imread(path)
    if img is None:
        raise ValueError("image rejected by type policy")
    h, w = img.shape[:2]
    m = max(h, w)
    if m > VLM_IMG_MAX_SIDE:
        sc = VLM_IMG_MAX_SIDE / m
        img = cv2.resize(img, (max(1, int(w * sc)), max(1, int(h * sc))),
                         interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, VLM_IMG_JPEG_QUALITY])
    if not ok:
        raise ValueError("image encoding failed")
    return base64.b64encode(buf.tobytes()).decode()


def _pair_key(img_a: str, img_b: str) -> str:
    h = hashlib.sha256()
    for p in sorted([img_a, img_b]):
        with open(p, "rb") as fh:
            h.update(fh.read())
    return h.hexdigest()
