from __future__ import annotations

import os
import re
import time
from typing import Any

import httpx

from societyxai.models.base import ModelBackend, ModelResponse


class OpenAICompatError(RuntimeError):
    """Raised when an OpenAI-compatible chat backend cannot complete a request."""


PROVIDER_ENDPOINTS: dict[str, tuple[str, str]] = {
    "openai": ("OPENAI_API_KEY", "https://api.openai.com/v1"),
    "deepseek": ("DEEPSEEK_API_KEY", "https://api.deepseek.com/v1"),
    "qwen": ("DASHSCOPE_API_KEY", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
    "dashscope": ("DASHSCOPE_API_KEY", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"),
    "openrouter": ("OPENROUTER_API_KEY", "https://openrouter.ai/api/v1"),
}


def resolve_openrouter_key() -> str | None:
    """Prefer OPENROUTER_API_KEY; accept a DashScope slot that is actually an OpenRouter key."""
    key = (os.environ.get("OPENROUTER_API_KEY") or "").strip()
    if key:
        return key
    dash = (os.environ.get("DASHSCOPE_API_KEY") or "").strip()
    if dash.startswith("sk-or-"):
        return dash
    return None


class OpenAICompatBackend(ModelBackend):
    """Chat Completions client for OpenAI, DeepSeek, and Qwen (DashScope)."""

    def __init__(
        self,
        model_id: str,
        provider: str,
        api_key: str | None = None,
        base_url: str | None = None,
        default_temperature: float | None = None,
        default_max_tokens: int | None = None,
        default_seed: int | None = None,
        json_mode: bool = True,
    ):
        super().__init__(model_id=model_id, provider=provider)
        env_key, default_url = PROVIDER_ENDPOINTS.get(
            provider.lower(), ("OPENAI_API_KEY", "https://api.openai.com/v1")
        )
        if provider.lower() == "openrouter" and api_key is None:
            self.api_key = resolve_openrouter_key()
        else:
            self.api_key = api_key if api_key is not None else os.environ.get(env_key)
        self.api_key_env = env_key
        self.base_url = (base_url or default_url).rstrip("/")
        self.default_temperature = default_temperature
        self.default_max_tokens = default_max_tokens
        self.default_seed = default_seed
        self.json_mode = json_mode

    def generate(
        self,
        messages: list[dict[str, Any]] | Any,
        temperature: float | None = None,
        max_tokens: int | None = None,
        seed: int | None = None,
        format: str | None = None,
    ) -> ModelResponse:
        if not self.api_key:
            raise OpenAICompatError(f"{self.api_key_env} is missing.")

        request_temperature = self.default_temperature if temperature is None else temperature
        request_max_tokens = self.default_max_tokens if max_tokens is None else max_tokens
        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": list(messages),
            "temperature": float(request_temperature if request_temperature is not None else 0.2),
            "max_tokens": int(request_max_tokens if request_max_tokens is not None else 256),
        }
        if self.json_mode or format == "json":
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.provider.lower() == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/societyxai"
            headers["X-Title"] = "SocietyXAI"
        try:
            content = self._post(payload, headers)
        except OpenAICompatError:
            if "response_format" in payload:
                payload.pop("response_format", None)
                content = self._post(payload, headers)
            else:
                raise
        return ModelResponse(text=content)

    def _post(self, payload: dict[str, Any], headers: dict[str, str]) -> str:
        last_error: OpenAICompatError | None = None
        for attempt in range(6):
            try:
                response = httpx.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=120.0,
                )
            except httpx.TimeoutException as exc:
                raise OpenAICompatError(f"{self.provider} timed out contacting {self.base_url}.") from exc
            except httpx.HTTPError as exc:
                raise OpenAICompatError(f"{self.provider} HTTP request failed: {exc}") from exc

            if response.status_code == 429:
                wait_s = 8.0 * (attempt + 1)
                match = re.search(r"try again in ([0-9.]+)s", response.text or "", flags=re.I)
                if match:
                    wait_s = float(match.group(1)) + 1.0
                last_error = OpenAICompatError(f"{self.provider} HTTP 429")
                time.sleep(wait_s)
                continue
            if response.status_code >= 400:
                raise OpenAICompatError(
                    f"{self.provider} HTTP {response.status_code}: "
                    f"{(response.text or 'no body')[:300]}"
                )
            try:
                message = response.json()["choices"][0]["message"]
                content = message.get("content") or ""
                if isinstance(content, list):
                    content = "".join(
                        part.get("text", "") if isinstance(part, dict) else str(part)
                        for part in content
                    )
                if not content:
                    content = message.get("reasoning") or message.get("reasoning_content") or ""
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                raise OpenAICompatError(f"{self.provider} response missing chat content") from exc
            if not isinstance(content, str) or not content.strip():
                last_error = OpenAICompatError(f"{self.provider} returned an empty completion")
                time.sleep(2.0)
                continue
            return content
        raise last_error or OpenAICompatError(f"{self.provider} retries exhausted")
