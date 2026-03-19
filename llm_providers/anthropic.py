# llm_providers/anthropic.py
"""Anthropic Claude provider — wraps existing AnthropicClient with unified interface."""
from __future__ import annotations

import os
from typing import Any, Dict, List

import requests

from config import CONFIG


class AnthropicProvider:
    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self.model = model

    @property
    def api_key(self) -> str:
        return (
            os.environ.get("ANTHROPIC_API_KEY")
            or CONFIG.get("anthropic_api_key", "")
        )

    def _headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    def chat(
        self,
        messages: List[Dict[str, Any]],
        system: str,
        max_tokens: int = 900,
    ) -> str:
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": messages,
        }
        r = requests.post(
            self.API_URL,
            headers=self._headers(),
            json=payload,
            timeout=70,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"Anthropic {r.status_code}: {r.text[:400]}")

        data = r.json()
        return "".join(
            p.get("text", "")
            for p in data.get("content", [])
            if p.get("type") == "text"
        ).strip()
