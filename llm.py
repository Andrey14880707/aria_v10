# llm.py
from pathlib import Path
from typing import Dict, List, Any
import base64

import requests

from config import API_KEY, MODEL


class LLMError(Exception):
    pass


class AnthropicClient:
    API_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self, api_key: str = API_KEY, model: str = MODEL):
        self.api_key = api_key
        self.model = model

    def _headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise LLMError("ANTHROPIC_API_KEY not set")
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

        try:
            r = requests.post(
                self.API_URL,
                headers=self._headers(),
                json=payload,
                timeout=70,
            )
            if r.status_code >= 400:
                raise LLMError(f"{r.status_code}: {r.text[:400]}")

            data = r.json()
            if "content" not in data:
                raise LLMError(f"bad_response:{data}")

            parts = data["content"]
            text_chunks = []
            for part in parts:
                if part.get("type") == "text":
                    text_chunks.append(part.get("text", ""))

            return "".join(text_chunks).strip()

        except requests.RequestException as e:
            raise LLMError(str(e)) from e

    def vision(
        self,
        image_path: Path,
        question: str,
        system: str,
        max_tokens: int = 600,
    ) -> str:
        if not image_path.exists():
            raise LLMError("image_not_found")

        data_b64 = base64.standard_b64encode(image_path.read_bytes()).decode("utf-8")
        ext = image_path.suffix.lower().replace(".", "")
        media_type = "image/jpeg" if ext in {"jpg", "jpeg"} else f"image/{ext}"

        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": data_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": question,
                        },
                    ],
                }
            ],
        }

        try:
            r = requests.post(
                self.API_URL,
                headers=self._headers(),
                json=payload,
                timeout=70,
            )
            if r.status_code >= 400:
                raise LLMError(f"{r.status_code}: {r.text[:400]}")

            data = r.json()
            if "content" not in data:
                raise LLMError(f"bad_response:{data}")

            return "".join(
                part.get("text", "")
                for part in data["content"]
                if part.get("type") == "text"
            ).strip()

        except requests.RequestException as e:
            raise LLMError(str(e)) from e
