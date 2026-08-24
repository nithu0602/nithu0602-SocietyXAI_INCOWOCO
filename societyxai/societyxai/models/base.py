from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Sequence


class ModelResponse:
    """Simple structured response container for model-generated output."""

    def __init__(self, text: str):
        self.text = text


class ModelBackend(ABC):
    """Abstract interface for model providers used by SocietyXAI."""

    def __init__(self, model_id: str, provider: str):
        self.model_id = model_id
        self.provider = provider

    @abstractmethod
    def generate(
        self,
        messages: Sequence[dict[str, Any]] | list[dict[str, Any]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        seed: int | None = None,
    ) -> str | ModelResponse:
        """Generate a response from a model backend.

        Future implementations may accept structured conversation inputs and
        generation settings while still supporting a simple string response.
        """
        raise NotImplementedError
