# llm_providers/gemini.py
"""Google Gemini provider for ARIA."""
from __future__ import annotations

import os
from typing import Any, Dict, List

import requests

from config import CONFIG


# Remap deprecated/unavailable models to working alternatives
_MODEL_ALIASES: Dict[str, str] = {
    "gemini-2.0-flash": "gemini-2.0-flash-lite",
    "gemini-1.5-flash": "gemini-2.0-flash-lite",
    "gemini-1.5-pro": "gemini-2.0-flash-lite",
}

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiProvider:
    def __init__(self, model: str = "gemini-2.0-flash-lite"):
        self.model = _MODEL_ALIASES.get(model, model)

    @property
    def api_key(self) -> str:
        return (
            os.environ.get("GEMINI_API_KEY")
            or CONFIG.get("gemini_api_key", "")
        )

    def chat(
        self,
        messages: List[Dict[str, Any]],
        system: str,
        max_tokens: int = 900,
    ) -> str:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY not set")

        url = f"{_BASE_URL}/{self.model}:generateContent?key={self.api_key}"

        # Build Gemini contents from messages
        contents: List[Dict[str, Any]] = []

        # Prepend system instruction as first user turn if needed
        if system:
            contents.append({
                "role": "user",
                "parts": [{"text": f"[System instruction]: {system}"}],
            })
            contents.append({
                "role": "model",
                "parts": [{"text": "Understood. I will follow these instructions."}],
            })

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if isinstance(content, list):
                text = " ".join(
                    part.get("text", "")
                    for part in content
                    if part.get("type") == "text"
                )
            else:
                text = str(content)

            # Gemini uses "model" instead of "assistant"
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": text}]})

        payload = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.7,
            },
        }

        r = requests.post(url, json=payload, timeout=70)
        if r.status_code >= 400:
            raise RuntimeError(f"Gemini {r.status_code}: {r.text[:400]}")

        data = r.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")

        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(p.get("text", "") for p in parts).strip()
