"""Typed registry mapping model identifiers to ModelBackend instances."""
from __future__ import annotations

from collections.abc import Iterator

from societyxai.models.base import ModelBackend


class BackendRegistry:
    """Immutable-style mapping from model_id strings to ModelBackend instances.

    Provides per-agent backend resolution for heterogeneous experiments.
    Falls back to a default backend when a model_id is not registered.

    Usage::

        registry = BackendRegistry(default=primary_backend)
        registry.register("llama3.1:8b", llama_backend)
        registry.register("qwen2.5-coder:1.5b-base", qwen_backend)

        backend = registry.resolve("llama3.1:8b")  # -> llama_backend
        backend = registry.resolve("unknown-model") # -> primary_backend
    """

    def __init__(self, default: ModelBackend | None = None):
        self._backends: dict[str, ModelBackend] = {}
        self._default: ModelBackend | None = default

    @property
    def default(self) -> ModelBackend | None:
        """Return the fallback backend used when a model_id is not registered."""
        return self._default

    def register(self, model_id: str, backend: ModelBackend) -> None:
        """Register a backend for the given model_id.

        Raises:
            ValueError: if *model_id* is empty.
            TypeError: if *backend* is not a ModelBackend instance.
        """
        if not model_id:
            raise ValueError("model_id must be a non-empty string")
        if not isinstance(backend, ModelBackend):
            raise TypeError(f"backend must be a ModelBackend instance, got {type(backend).__name__}")
        self._backends[model_id] = backend

    def resolve(self, model_id: str) -> ModelBackend | None:
        """Return the backend registered for *model_id*, or the default.

        Returns ``None`` only when no backend is registered for *model_id*
        **and** no default backend was provided.
        """
        return self._backends.get(model_id, self._default)

    def has_model(self, model_id: str) -> bool:
        """Return True if *model_id* has a registered backend."""
        return model_id in self._backends

    def models(self) -> list[str]:
        """Return a sorted list of all registered model identifiers."""
        return sorted(self._backends.keys())

    def backends(self) -> list[ModelBackend]:
        """Return all registered backend instances (excluding the default)."""
        return list(self._backends.values())

    def __len__(self) -> int:
        return len(self._backends)

    def __contains__(self, model_id: str) -> bool:
        return model_id in self._backends

    def __iter__(self) -> Iterator[str]:
        return iter(self._backends)

    def __repr__(self) -> str:
        models = ", ".join(sorted(self._backends.keys()))
        default_label = self._default.model_id if self._default else "None"
        return f"BackendRegistry(default={default_label!r}, models=[{models}])"
