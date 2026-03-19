# llm_providers/openai.py
"""OpenAI GPT provider for ARIA."""
from __future__ import annotations

import os
from typing import Any, Dict, List

import requests

from config import CONFIG


class OpenAIProvider:
    API_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self, model: str = "gpt-4o"):
        self.model = model

    @property
    def api_key(self) -> str:
        return (
            os.environ.get("OPENAI_API_KEY")
            or CONFIG.get("openai_api_key", "")
        )

    def _headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        messages: List[Dict[str, Any]],
        system: str,
        max_tokens: int = 900,
    ) -> str:
        # OpenAI uses "system" as a role in messages array
        openai_messages: List[Dict[str, str]] = [
            {"role": "system", "content": system}
        ]
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if isinstance(content, list):
                # Extract text from content blocks
                text = " ".join(
                    part.get("text", "")
                    for part in content
                    if part.get("type") == "text"
                )
            else:
                text = str(content)
            openai_messages.append({"role": role, "content": text})

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": openai_messages,
        }

        r = requests.post(
            self.API_URL,
            headers=self._headers(),
            json=payload,
            timeout=70,
        )
        if r.status_code >= 400:
            raise RuntimeError(f"OpenAI {r.status_code}: {r.text[:400]}")

        data = r.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("OpenAI returned no choices")

        return choices[0].get("message", {}).get("content", "").strip()
