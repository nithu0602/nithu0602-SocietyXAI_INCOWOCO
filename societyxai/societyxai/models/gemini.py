from __future__ import annotations

import os
from typing import Any

import httpx

from societyxai.models.base import ModelBackend, ModelResponse


class GeminiError(RuntimeError):
    """Raised when the Gemini generateContent API cannot complete a request."""


class GeminiBackend(ModelBackend):
    """Minimal Gemini generateContent backend."""

    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def __init__(
        self,
        model_id: str,
        api_key: str | None = None,
        default_temperature: float | None = None,
        default_max_tokens: int | None = None,
        default_seed: int | None = None,
    ):
        super().__init__(model_id=model_id, provider="gemini")
        self.api_key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY")
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens
        self.default_seed = default_seed

    def generate(
        self,
        messages: list[dict[str, Any]] | Any,
        temperature: float | None = None,
        max_tokens: int | None = None,
        seed: int | None = None,
        format: str | None = None,
    ) -> ModelResponse:
        if not self.api_key:
            raise GeminiError("GEMINI_API_KEY is missing.")

        system = ""
        contents: list[dict[str, Any]] = []
        for item in list(messages):
            role = item.get("role", "user")
            text = item.get("content", "")
            if role == "system":
                system = f"{system}\n{text}".strip() if system else text
                continue
            gemini_role = "model" if role == "assistant" else "user"
            contents.append({"role": gemini_role, "parts": [{"text": text}]})
        if not contents:
            contents = [{"role": "user", "parts": [{"text": "Reply with JSON only."}]}]

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": float(
                    (self.default_temperature if temperature is None else temperature) or 0.2
                ),
                "maxOutputTokens": int(
                    (self.default_max_tokens if max_tokens is None else max_tokens) or 256
                ),
                "responseMimeType": "application/json",
            },
        }
        if system:
            payload["systemInstruction"] = {"parts": [{"text": system}]}

        url = f"{self.DEFAULT_BASE_URL}/models/{self.model_id}:generateContent"
        try:
            response = httpx.post(
                url,
                params={"key": self.api_key},
                json=payload,
                timeout=120.0,
            )
        except httpx.HTTPError as exc:
            raise GeminiError(f"Gemini HTTP request failed: {exc}") from exc
        if response.status_code >= 400:
            raise GeminiError(
                f"Gemini HTTP {response.status_code}: {(response.text or 'no body')[:300]}"
            )
        try:
            parts = response.json()["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise GeminiError("Gemini response missing candidates[0].content.parts") from exc
        if not text.strip():
            raise GeminiError("Gemini returned an empty completion")
        return ModelResponse(text=text)
