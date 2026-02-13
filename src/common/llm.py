from __future__ import annotations

import json
from typing import Any

import requests


class LLMClient:
    def __init__(self, model_cfg: dict[str, Any]):
        self.model = str(model_cfg.get("model_name", ""))
        self.base_url = str(model_cfg.get("api_base", "http://127.0.0.1:8000/v1")).rstrip("/")
        self.api_key = str(model_cfg.get("api_key", "EMPTY"))
        self.timeout_seconds = int(model_cfg.get("timeout_seconds", 120))

    def healthcheck(self) -> bool:
        try:
            resp = requests.get(f"{self.base_url}/models", timeout=10)
            return resp.ok
        except Exception:
            return False

    def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        response_format: dict[str, Any] | None = None,
    ) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format is not None:
            payload["response_format"] = response_format

        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            data=json.dumps(payload),
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"].strip()


def maybe_make_vllm_client(model_cfg: dict[str, Any]) -> LLMClient | None:
    backend = str(model_cfg.get("backend", "")).lower()
    if backend != "vllm":
        return None
    return LLMClient(model_cfg)
