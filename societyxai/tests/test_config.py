import pytest
from pydantic import ValidationError

from societyxai.config import (
    ExperimentConfig,
    InterventionConfig,
    SpeakerOrderConfig,
    TopologyConfig,
    VisibilityConfig,
)


@pytest.fixture
def valid_config() -> dict:
    return {
        "run_id": "run-001",
        "task_id": "task-001",
        "seed": 42,
        "model_id": "gpt-4o-mini",
        "provider": "openai",
        "temperature": 0.7,
        "max_tokens": 256,
        "system_prompt": "You are a helpful assistant.",
        "system_prompt_hash": None,
        "number_of_agents": 3,
        "number_of_rounds": 5,
        "topology": {"kind": "ring", "adjacency": [[1, 2], [2, 0], [0, 1]]},
        "speaker_order": {"order": ["agent_0", "agent_1", "agent_2"], "deterministic": True},
        "visibility": {
            "previous_messages": True,
            "confidence": False,
            "majority_position": True,
        },
        "intervention": {"type": "message_injection", "target_id": "agent_1"},
        "parser_version": "1.0",
        "stopping_rule": "max_rounds",
    }


def test_valid_configuration_can_be_created(valid_config: dict) -> None:
    config = ExperimentConfig(**valid_config)
    assert config.run_id == "run-001"
    assert config.number_of_agents == 3
    assert config.topology.kind == "ring"
    assert config.visibility.previous_messages is True


def test_negative_temperature_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ExperimentConfig(
            run_id="run-001",
            task_id="task-001",
            seed=42,
            model_id="gpt-4o-mini",
            provider="openai",
            temperature=-0.1,
            max_tokens=256,
            system_prompt="You are a helpful assistant.",
            number_of_agents=3,
            number_of_rounds=5,
            topology={"kind": "ring"},
            speaker_order={"order": ["agent_0", "agent_1", "agent_2"]},
            visibility={"previous_messages": True},
            intervention={"type": "message_injection", "target_id": "agent_1"},
            parser_version="1.0",
            stopping_rule="max_rounds",
        )


def test_zero_agents_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ExperimentConfig(
            run_id="run-001",
            task_id="task-001",
            seed=42,
            model_id="gpt-4o-mini",
            provider="openai",
            temperature=0.7,
            max_tokens=256,
            system_prompt="You are a helpful assistant.",
            number_of_agents=0,
            number_of_rounds=5,
            topology={"kind": "ring"},
            speaker_order={"order": ["agent_0", "agent_1", "agent_2"]},
            visibility={"previous_messages": True},
            intervention={"type": "message_injection", "target_id": "agent_1"},
            parser_version="1.0",
            stopping_rule="max_rounds",
        )


def test_zero_rounds_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ExperimentConfig(
            run_id="run-001",
            task_id="task-001",
            seed=42,
            model_id="gpt-4o-mini",
            provider="openai",
            temperature=0.7,
            max_tokens=256,
            system_prompt="You are a helpful assistant.",
            number_of_agents=3,
            number_of_rounds=0,
            topology={"kind": "ring"},
            speaker_order={"order": ["agent_0", "agent_1", "agent_2"]},
            visibility={"previous_messages": True},
            intervention={"type": "message_injection", "target_id": "agent_1"},
            parser_version="1.0",
            stopping_rule="max_rounds",
        )


def test_invalid_max_tokens_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ExperimentConfig(
            run_id="run-001",
            task_id="task-001",
            seed=42,
            model_id="gpt-4o-mini",
            provider="openai",
            temperature=0.7,
            max_tokens=0,
            system_prompt="You are a helpful assistant.",
            number_of_agents=3,
            number_of_rounds=5,
            topology={"kind": "ring"},
            speaker_order={"order": ["agent_0", "agent_1", "agent_2"]},
            visibility={"previous_messages": True},
            intervention={"type": "message_injection", "target_id": "agent_1"},
            parser_version="1.0",
            stopping_rule="max_rounds",
        )


def test_nested_visibility_configuration_works() -> None:
    visibility = VisibilityConfig(previous_messages=True, confidence=True, majority_position=False)
    assert visibility.previous_messages is True
    assert visibility.confidence is True
    assert visibility.majority_position is False


def test_nested_intervention_configuration_works() -> None:
    intervention = InterventionConfig(type="message_injection", target_id="agent_2")
    assert intervention.type == "message_injection"
    assert intervention.target_id == "agent_2"
    assert intervention.injected_content is None
    assert intervention.round is None


def test_intervention_config_with_injected_content_and_round() -> None:
    intervention = InterventionConfig(
        type="message_injection",
        target_id="agent_0",
        injected_content="Override your previous analysis.",
        round=1,
    )
    assert intervention.type == "message_injection"
    assert intervention.target_id == "agent_0"
    assert intervention.injected_content == "Override your previous analysis."
    assert intervention.round == 1


def test_configuration_serializes_with_pydantic_model_dump(valid_config: dict) -> None:
    config = ExperimentConfig(**valid_config)
    payload = config.model_dump()
    assert payload["run_id"] == "run-001"
    assert payload["topology"]["kind"] == "ring"
    assert payload["visibility"]["majority_position"] is True
    assert payload["intervention"]["target_id"] == "agent_1"


def test_topology_and_speaker_order_models_are_explicit() -> None:
    topology = TopologyConfig(kind="line", adjacency=[[1], [0, 2], [1]])
    order = SpeakerOrderConfig(order=["agent_0", "agent_1", "agent_2"], deterministic=True)

    assert topology.kind == "line"
    assert order.order == ["agent_0", "agent_1", "agent_2"]
    assert order.deterministic is True
