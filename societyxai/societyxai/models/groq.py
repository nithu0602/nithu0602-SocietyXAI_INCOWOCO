from __future__ import annotations

import os
from typing import Any

import httpx

from societyxai.models.base import ModelBackend, ModelResponse


class GroqError(RuntimeError):
    """Raised when the Groq backend cannot complete a request."""


class GroqBackend(ModelBackend):
    """OpenAI-compatible Groq chat backend. Uses the user's GROQ_API_KEY only."""

    DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"

    def __init__(
        self,
        model_id: str,
        api_key: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
        default_temperature: float | None = None,
        default_max_tokens: int | None = None,
        default_seed: int | None = None,
        json_mode: bool = True,
    ):
        super().__init__(model_id=model_id, provider="groq")
        self.api_key = api_key if api_key is not None else os.environ.get("GROQ_API_KEY")
        self.base_url = base_url.rstrip("/")
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
            raise GroqError("GROQ_API_KEY is missing.")

        request_temperature = self.default_temperature if temperature is None else temperature
        request_max_tokens = self.default_max_tokens if max_tokens is None else max_tokens

        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": list(messages),
            "temperature": float(request_temperature if request_temperature is not None else 0.2),
            "max_tokens": int(request_max_tokens if request_max_tokens is not None else 256),
        }
        use_json = self.json_mode or format == "json"
        if use_json:
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        try:
            content = self._post(payload, headers)
        except GroqError:
            if "response_format" in payload:
                payload.pop("response_format", None)
                content = self._post(payload, headers)
            else:
                raise
        return ModelResponse(text=content)

    def _post(self, payload: dict[str, Any], headers: dict[str, str]) -> str:
        last_error: GroqError | None = None
        for attempt in range(6):
            try:
                response = httpx.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=120.0,
                )
            except httpx.TimeoutException as exc:
                raise GroqError(f"Groq request timed out contacting {self.base_url}.") from exc
            except httpx.HTTPError as exc:
                raise GroqError(f"Groq HTTP request failed: {exc}") from exc

            if response.status_code == 429:
                wait_s = 8.0 * (attempt + 1)
                try:
                    message = response.json().get("error", {}).get("message", "")
                    import re

                    match = re.search(r"try again in ([0-9.]+)s", message, flags=re.I)
                    if match:
                        wait_s = float(match.group(1)) + 1.0
                except Exception:
                    pass
                last_error = GroqError(f"Groq HTTP 429: {response.text[:200]}")
                import time

                time.sleep(wait_s)
                continue

            if response.status_code >= 400:
                raise GroqError(
                    f"Groq HTTP {response.status_code}: "
                    f"{response.text[:300] if response.text else 'no body'}"
                )
            try:
                data = response.json()
                message = data["choices"][0]["message"]
                content = message.get("content") or ""
                if isinstance(content, list):
                    content = "".join(
                        part.get("text", "") if isinstance(part, dict) else str(part)
                        for part in content
                    )
                if not content:
                    content = message.get("reasoning") or message.get("reasoning_content") or ""
                if not content and isinstance(message.get("tool_calls"), list):
                    content = str(message["tool_calls"])
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                raise GroqError("Groq response missing choices[0].message.content") from exc
            if not isinstance(content, str) or not content.strip():
                last_error = GroqError("Groq returned an empty completion")
                import time

                time.sleep(2.0)
                continue
            return content
        raise last_error or GroqError("Groq rate limit retries exhausted")
