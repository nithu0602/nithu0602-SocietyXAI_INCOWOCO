from __future__ import annotations

import os

from societyxai.models.base import ModelBackend
from societyxai.models.groq import GroqBackend
from societyxai.models.ollama import OllamaBackend

SUPPORTED_PROVIDERS = (
    "ollama",
    "groq",
    "openai",
    "anthropic",
    "gemini",
    "google",
    "deepseek",
    "qwen",
    "dashscope",
    "openrouter",
)

_ENV_BY_PROVIDER = {
    "groq": "GROQ_API_KEY",
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "google": "GEMINI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "qwen": "DASHSCOPE_API_KEY",
    "dashscope": "DASHSCOPE_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def provider_has_credentials(provider: str) -> bool:
    """Return True when the named provider can run locally or has an API key."""
    name = provider.lower()
    if name == "ollama":
        return True
    if name == "openrouter":
        from societyxai.models.openai_compat import resolve_openrouter_key

        return bool(resolve_openrouter_key())
    env_name = _ENV_BY_PROVIDER.get(name)
    return bool(env_name and os.environ.get(env_name))


def build_backend(
    provider: str,
    model_id: str,
    *,
    default_temperature: float | None = None,
    default_max_tokens: int | None = None,
    default_seed: int | None = None,
) -> ModelBackend:
    """Instantiate a backend for *provider* / *model_id*."""
    name = provider.lower()
    kwargs = dict(
        default_temperature=default_temperature,
        default_max_tokens=default_max_tokens,
        default_seed=default_seed,
    )
    if name == "ollama":
        return OllamaBackend(model_id=model_id, **kwargs)
    if name == "groq":
        return GroqBackend(model_id=model_id, **kwargs)
    if name in {"openai", "deepseek", "qwen", "dashscope", "openrouter"}:
        from societyxai.models.openai_compat import OpenAICompatBackend

        return OpenAICompatBackend(model_id=model_id, provider=name, **kwargs)
    if name == "anthropic":
        from societyxai.models.anthropic import AnthropicBackend

        return AnthropicBackend(model_id=model_id, **kwargs)
    if name in {"gemini", "google"}:
        from societyxai.models.gemini import GeminiBackend

        return GeminiBackend(model_id=model_id, **kwargs)
    raise ValueError(
        f"Unsupported provider '{provider}'. "
        f"Supported providers: {', '.join(SUPPORTED_PROVIDERS)}."
    )
