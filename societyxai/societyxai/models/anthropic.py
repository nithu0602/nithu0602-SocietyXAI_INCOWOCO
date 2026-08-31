from __future__ import annotations

import os
from typing import Any

import httpx

from societyxai.models.base import ModelBackend, ModelResponse


class AnthropicError(RuntimeError):
    """Raised when the Anthropic Messages API cannot complete a request."""


class AnthropicBackend(ModelBackend):
    """Minimal Anthropic Messages backend (Claude Sonnet 5 and siblings)."""

    DEFAULT_BASE_URL = "https://api.anthropic.com/v1"

    def __init__(
        self,
        model_id: str,
        api_key: str | None = None,
        default_temperature: float | None = None,
        default_max_tokens: int | None = None,
        default_seed: int | None = None,
    ):
        super().__init__(model_id=model_id, provider="anthropic")
        self.api_key = api_key if api_key is not None else os.environ.get("ANTHROPIC_API_KEY")
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
            raise AnthropicError("ANTHROPIC_API_KEY is missing.")

        system = ""
        chat: list[dict[str, str]] = []
        for item in list(messages):
            role = item.get("role", "user")
            content = item.get("content", "")
            if role == "system":
                system = f"{system}\n{content}".strip() if system else content
            else:
                chat.append({"role": "user" if role != "assistant" else "assistant", "content": content})
        if not chat:
            chat = [{"role": "user", "content": "Reply with JSON only."}]

        payload: dict[str, Any] = {
            "model": self.model_id,
            "max_tokens": int(
                (self.default_max_tokens if max_tokens is None else max_tokens) or 256
            ),
            "temperature": float(
                (self.default_temperature if temperature is None else temperature) or 0.2
            ),
            "messages": chat,
        }
        if system:
            payload["system"] = system

        try:
            response = httpx.post(
                f"{self.DEFAULT_BASE_URL}/messages",
                json=payload,
                headers={
                    "x-api-key": self.api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                timeout=120.0,
            )
        except httpx.HTTPError as exc:
            raise AnthropicError(f"Anthropic HTTP request failed: {exc}") from exc
        if response.status_code >= 400:
            raise AnthropicError(
                f"Anthropic HTTP {response.status_code}: {(response.text or 'no body')[:300]}"
            )
        try:
            blocks = response.json().get("content") or []
            text = "".join(
                block.get("text", "") for block in blocks if isinstance(block, dict)
            )
        except (ValueError, TypeError) as exc:
            raise AnthropicError("Anthropic response missing content text") from exc
        if not text.strip():
            raise AnthropicError("Anthropic returned an empty completion")
        return ModelResponse(text=text)
