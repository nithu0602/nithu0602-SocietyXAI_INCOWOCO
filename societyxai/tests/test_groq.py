import os

import httpx
import pytest

from societyxai.models.groq import GroqBackend, GroqError


def test_groq_backend_provider() -> None:
    backend = GroqBackend(model_id="llama-3.3-70b-versatile", api_key="test")
    assert backend.provider == "groq"
    assert backend.model_id == "llama-3.3-70b-versatile"


def test_groq_generate_mocked(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = GroqBackend(model_id="llama-3.3-70b-versatile", api_key="test")

    def fake_post(url, json, headers, timeout):
        assert url.endswith("/chat/completions")
        assert json["model"] == "llama-3.3-70b-versatile"
        assert headers["Authorization"] == "Bearer test"
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"position": "support"}'}}]},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    result = backend.generate([{"role": "user", "content": "hi"}])
    assert result.text.startswith("{")


def test_groq_missing_key_raises() -> None:
    backend = GroqBackend(model_id="llama-3.3-70b-versatile", api_key="")
    with pytest.raises(GroqError, match="GROQ_API_KEY"):
        backend.generate([{"role": "user", "content": "hi"}])
