import pytest
import httpx

from societyxai.models import ModelResponse, OllamaBackend
from societyxai.models.ollama import (
    OllamaMalformedResponseError,
    OllamaRequestError,
    OllamaTimeoutError,
)


class FakeTransport(httpx.BaseTransport):
    def __init__(self, payload, *, status_code=200):
        self.payload = payload
        self.status_code = status_code

    def handle_request(self, request):
        if self.status_code >= 400:
            return httpx.Response(self.status_code, request=request)
        return httpx.Response(200, json=self.payload, request=request)


def test_ollama_backend_can_be_instantiated() -> None:
    backend = OllamaBackend(model_id="llama3.2")
    assert backend.model_id == "llama3.2"


def test_model_id_is_exposed_correctly() -> None:
    backend = OllamaBackend(model_id="mistral")
    assert backend.model_id == "mistral"


def test_provider_identifies_ollama() -> None:
    backend = OllamaBackend(model_id="phi3")
    assert backend.provider == "ollama"


def test_default_base_url_is_correct() -> None:
    backend = OllamaBackend(model_id="tinyllama")
    assert backend.base_url == "http://localhost:11434"


def test_successful_mocked_response_becomes_model_response(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = OllamaBackend(model_id="tinyllama")

    def fake_post(url, json, timeout):
        assert url.endswith("/api/chat")
        assert json["model"] == "tinyllama"
        assert json["stream"] is False
        return httpx.Response(200, json={"message": {"content": "hello from ollama"}})

    monkeypatch.setattr(httpx, "post", fake_post)
    response = backend.generate(messages=[{"role": "user", "content": "hi"}])
    assert isinstance(response, ModelResponse)
    assert response.text == "hello from ollama"


def test_request_contains_expected_model(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = OllamaBackend(model_id="llama3")

    captured = {}

    def fake_post(url, json, timeout):
        captured["json"] = json
        return httpx.Response(200, json={"message": {"content": "ok"}})

    monkeypatch.setattr(httpx, "post", fake_post)
    backend.generate(messages=[{"role": "user", "content": "hello"}], temperature=0.3)
    assert captured["json"]["model"] == "llama3"


def test_stream_is_false(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = OllamaBackend(model_id="llama3")

    captured = {}

    def fake_post(url, json, timeout):
        captured["stream"] = json["stream"]
        return httpx.Response(200, json={"message": {"content": "ok"}})

    monkeypatch.setattr(httpx, "post", fake_post)
    backend.generate(messages=[{"role": "user", "content": "hello"}])
    assert captured["stream"] is False


def test_generation_options_are_passed_correctly(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = OllamaBackend(model_id="llama3", default_temperature=0.2, default_max_tokens=42, default_seed=7)

    captured = {}

    def fake_post(url, json, timeout):
        captured["json"] = json
        return httpx.Response(200, json={"message": {"content": "ok"}})

    monkeypatch.setattr(httpx, "post", fake_post)
    backend.generate(messages=[{"role": "user", "content": "hello"}])
    assert captured["json"]["options"]["temperature"] == 0.2
    assert captured["json"]["options"]["num_predict"] == 42
    assert captured["json"]["options"]["seed"] == 7


def test_json_output_mode_is_requested(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = OllamaBackend(model_id="llama3")

    captured = {}

    def fake_post(url, json, timeout):
        captured["json"] = json
        return httpx.Response(200, json={"message": {"content": "ok"}})

    monkeypatch.setattr(httpx, "post", fake_post)
    backend.generate(messages=[{"role": "user", "content": "hello"}], format="json")
    assert captured["json"]["format"] == "json"


def test_http_errors_are_converted_into_clear_exceptions(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = OllamaBackend(model_id="llama3")

    def fake_post(url, json, timeout):
        return httpx.Response(500, text="server error")

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(OllamaRequestError, match="Ollama HTTP request failed"):
        backend.generate(messages=[{"role": "user", "content": "hello"}])


def test_timeout_and_network_failures_are_handled(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = OllamaBackend(model_id="llama3")

    def fake_post(url, json, timeout):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(OllamaTimeoutError, match="timed out"):
        backend.generate(messages=[{"role": "user", "content": "hello"}])

    def fake_network_error(url, json, timeout):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", fake_network_error)
    with pytest.raises(OllamaRequestError, match="connection refused"):
        backend.generate(messages=[{"role": "user", "content": "hello"}])


def test_malformed_ollama_responses_are_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = OllamaBackend(model_id="llama3")

    def fake_post(url, json, timeout):
        return httpx.Response(200, json={"bad": "response"})

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(OllamaMalformedResponseError):
        backend.generate(messages=[{"role": "user", "content": "hello"}])
