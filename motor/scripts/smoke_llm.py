#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Smoke test de las capas VLM (F0): worker local Ollama y OpenAI.

Envía la MISMA pareja de imágenes con el prompt de identidad validado y
comprueba que ambos devuelven JSON estricto con las claves esperadas.

Uso:
    motor/venv/bin/python motor/scripts/smoke_llm.py \
        --img-a motor/eval/data/persona_a/a_1.jpg \
        --img-b motor/eval/data/persona_b/b_1.jpg \
        [--provider both|local|openai] [--ruta /root/reconocimientoFacial]

Requiere el worker Ollama activo y (para openai) RF_LLM_API_KEY en .env.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

import requests  # noqa: E402

from motor.core.config import Config  # noqa: E402
from motor.core.prompts import SYSTEM_PROMPT, USER_PROMPT  # noqa: E402


def _b64(path: str) -> str:
    with open(path, "rb") as fh:
        return base64.b64encode(fh.read()).decode()


def _valid(result: dict) -> bool:
    for k in ("probability_same", "confidence", "reasoning", "skip"):
        if k not in result:
            return False
    p = result["probability_same"]
    c = result["confidence"]
    return isinstance(p, (int, float)) and isinstance(c, (int, float)) and 0.0 <= p <= 1.0 and 0.0 <= c <= 1.0


def smoke_local(cfg: Config, img_a: str, img_b: str) -> dict:
    url = f"{cfg.vlm_base_url}/api/chat"
    payload = {
        "model": cfg.vlm_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_PROMPT, "images": [_b64(img_a), _b64(img_b)]},
        ],
        "stream": False,
        "options": {"num_ctx": cfg.vlm_num_ctx, "num_gpu": cfg.vlm_num_gpu},
        "keep_alive": cfg.vlm_keep_alive_s,
    }
    r = requests.post(url, json=payload, timeout=cfg.vlm_timeout_s)
    r.raise_for_status()
    content = r.json()["message"]["content"]
    # el modelo puede devolver ```json ... ```; extraer el primer objeto JSON
    start = content.find("{")
    end = content.rfind("}") + 1
    return json.loads(content[start:end]) if start >= 0 and end > start else {}


def smoke_openai(cfg: Config, img_a: str, img_b: str) -> dict:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {cfg.llm_api_key}"}
    payload = {
        "model": cfg.llm_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": USER_PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(img_a)}"}},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{_b64(img_b)}"}},
                ],
            },
        ],
        "max_tokens": 400,
        "response_format": {"type": "json_object"},
    }
    r = requests.post(url, headers=headers, json=payload, timeout=cfg.openai_timeout_s)
    r.raise_for_status()
    return json.loads(r.json()["choices"][0]["message"]["content"])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--img-a", required=True)
    ap.add_argument("--img-b", required=True)
    ap.add_argument("--provider", default="both", choices=["local", "openai", "both"])
    ap.add_argument("--ruta", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    args = ap.parse_args()

    cfg = Config.from_env(args.ruta)
    ok = True

    if args.provider in ("local", "both"):
        try:
            res = smoke_local(cfg, args.img_a, args.img_b)
            valid = _valid(res)
            print(f"[local]   JSON valido: {valid}  -> {json.dumps(res, ensure_ascii=False)[:160]}")
            ok = ok and valid
        except Exception as e:  # noqa: BLE001
            print(f"[local]   ERROR: {e}")
            ok = False

    if args.provider in ("openai", "both"):
        if not cfg.llm_api_key:
            print("[openai]  RF_LLM_API_KEY vacía: omitido (añádela al .env para activar L3)")
        else:
            try:
                res = smoke_openai(cfg, args.img_a, args.img_b)
                valid = _valid(res)
                print(f"[openai]  JSON valido: {valid}  -> {json.dumps(res, ensure_ascii=False)[:160]}")
                ok = ok and valid
            except Exception as e:  # noqa: BLE001
                print(f"[openai]  ERROR: {e}")
                ok = False

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
