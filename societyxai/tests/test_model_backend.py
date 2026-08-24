import pytest

from societyxai.models import ModelBackend, ModelResponse


class FakeBackend(ModelBackend):
    def generate(
        self,
        messages,
        temperature=None,
        max_tokens=None,
        seed=None,
    ) -> str | ModelResponse:
        return ModelResponse(text="fake-response")


def test_model_backend_is_abstract() -> None:
    with pytest.raises(TypeError):
        ModelBackend("test-model", "test-provider")


def test_fake_backend_can_inherit_from_model_backend() -> None:
    backend = FakeBackend("fake-model", "fake-provider")
    assert isinstance(backend, ModelBackend)


def test_fake_backend_satisfies_interface() -> None:
    backend = FakeBackend("fake-model", "fake-provider")
    result = backend.generate(
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.7,
        max_tokens=64,
        seed=42,
    )
    assert isinstance(result, ModelResponse)
    assert result.text == "fake-response"


def test_model_metadata_is_available() -> None:
    backend = FakeBackend("fake-model", "fake-provider")
    assert backend.model_id == "fake-model"
    assert backend.provider == "fake-provider"


def test_generation_parameters_are_expected() -> None:
    backend = FakeBackend("fake-model", "fake-provider")
    response = backend.generate(
        messages=[{"role": "assistant", "content": "hi"}],
        temperature=0.2,
        max_tokens=32,
        seed=7,
    )
    assert isinstance(response, ModelResponse)
