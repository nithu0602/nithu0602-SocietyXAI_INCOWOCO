from __future__ import annotations

from typing import Any

import httpx

from societyxai.models.base import ModelBackend, ModelResponse


class OllamaError(RuntimeError):
    """Raised when the Ollama backend cannot complete a request."""


class OllamaRequestError(OllamaError):
    """Raised when the underlying HTTP request fails."""


class OllamaTimeoutError(OllamaError):
    """Raised when the local Ollama API does not respond in time."""


class OllamaMalformedResponseError(OllamaError):
    """Raised when the Ollama response schema is not usable."""


class OllamaBackend(ModelBackend):
    """Concrete backend adapter for a locally running Ollama server."""

    DEFAULT_BASE_URL = "http://localhost:11434"

    def __init__(
        self,
        model_id: str,
        base_url: str = DEFAULT_BASE_URL,
        default_temperature: float | None = None,
        default_max_tokens: int | None = None,
        default_seed: int | None = None,
    ):
        super().__init__(model_id=model_id, provider="ollama")
        self.base_url = base_url.rstrip("/")
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
        """Generate a response from a local Ollama chat endpoint."""
        request_temperature = self.default_temperature if temperature is None else temperature
        request_max_tokens = self.default_max_tokens if max_tokens is None else max_tokens
        request_seed = self.default_seed if seed is None else seed

        payload: dict[str, Any] = {
            "model": self.model_id,
            "messages": list(messages),
            "stream": False,
            "options": {},
        }

        if request_temperature is not None:
            payload["options"]["temperature"] = float(request_temperature)
        if request_max_tokens is not None:
            payload["options"]["num_predict"] = int(request_max_tokens)
        if request_seed is not None:
            payload["options"]["seed"] = int(request_seed)
        if format is not None:
            payload["format"] = format

        try:
            response = httpx.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=60.0,
            )
        except httpx.TimeoutException as exc:
            raise OllamaTimeoutError(f"Ollama request timed out while contacting {self.base_url}.") from exc
        except httpx.HTTPError as exc:
            raise OllamaRequestError(f"Ollama HTTP request failed: {exc}") from exc

        if response.status_code >= 400:
            raise OllamaRequestError(
                f"Ollama HTTP request failed with status {response.status_code}: "
                f"{response.text[:200] if response.text else 'no response body'}"
            )

        try:
            data = response.json()
        except ValueError as exc:
            raise OllamaMalformedResponseError("Ollama response was not valid JSON.") from exc

        if not isinstance(data, dict):
            raise OllamaMalformedResponseError("Ollama response is not a JSON object.")

        try:
            message = data["message"]
            content = message["content"]
        except (KeyError, TypeError) as exc:
            raise OllamaMalformedResponseError("Ollama response missing expected 'message.content'.") from exc

        if not isinstance(content, str):
            raise OllamaMalformedResponseError("Ollama response content was not a string.")

        return ModelResponse(text=content)
