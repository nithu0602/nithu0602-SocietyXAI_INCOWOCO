from __future__ import annotations

from pathlib import Path

import pytest

from societyxai.config import ExperimentConfig, ExperimentLoader, ExperimentLoaderError
from societyxai.core import Agent, Orchestrator, Society
from societyxai.config.schema import SpeakerOrderConfig, TopologyConfig, VisibilityConfig
from societyxai.tasks import Task
from societyxai.models import ModelBackend, ModelResponse


class RecordingBackend(ModelBackend):
    def __init__(self, model_id: str = "fake", provider: str = "fake"):
        super().__init__(model_id=model_id, provider=provider)
        self.calls: list[list[dict[str, str]]] = []

    def generate(self, messages, temperature=None, max_tokens=None, seed=None):
        # record the messages list for inspection
        self.calls.append(list(messages))
        return ModelResponse(text="ok")


@pytest.fixture
def minimal_experiment_dict() -> dict:
    return {
        "run_id": "run-test-ib-001",
        "task_id": "task-test-ib-001",
        "seed": 7,
        "model_id": "llama3",
        "provider": "ollama",
        "temperature": 0.0,
        "max_tokens": 64,
        "system_prompt": "You are a test agent.",
        "number_of_agents": 2,
        "number_of_rounds": 1,
        "topology": {"kind": "complete"},
        "speaker_order": {"order": ["a0", "a1"], "deterministic": True},
        "visibility": {"previous_messages": True, "confidence": False, "majority_position": False},
        "intervention": {"type": "none", "target_id": "a0"},
        "parser_version": "1.0",
        "stopping_rule": "max_rounds",
    }


@pytest.fixture
def minimal_task_dict() -> dict:
    return {
        "task_id": "task-test-ib-001",
        "question": "Is the proposal sound?",
        "ground_truth": "yes",
    }


def test_valid_initial_beliefs_applied(minimal_experiment_dict, minimal_task_dict):
    cfg = dict(minimal_experiment_dict)
    cfg["initial_beliefs"] = {
        "a0": {"position": "support", "confidence": 0.9, "evidence_ids": ["e1"], "reasoning_trace": "init"}
    }
    config = ExperimentConfig(**cfg)
    built = ExperimentLoader.build(config, minimal_task_dict)
    # a0 should have current_belief and belief_history seeded
    a0 = [a for a in built.society.agents if a.agent_id == "a0"][0]
    assert a0.current_belief is not None
    assert a0.current_belief.position == "support"
    assert len(a0.belief_history) == 1


def test_invalid_agent_id_in_initial_beliefs_raises(tmp_path, minimal_task_dict, minimal_experiment_dict):
    bad = dict(minimal_experiment_dict)
    bad["initial_beliefs"] = {"unknown": {"position": "support", "confidence": 0.5}}
    p = tmp_path / "bad.yaml"
    import yaml

    p.write_text(yaml.dump({"experiment": bad, "task": minimal_task_dict}))
    with pytest.raises(ExperimentLoaderError):
        ExperimentLoader.from_yaml(p)


def test_invalid_confidence_in_initial_belief_raises(tmp_path, minimal_task_dict, minimal_experiment_dict):
    bad = dict(minimal_experiment_dict)
    bad["initial_beliefs"] = {"a0": {"position": "support", "confidence": 2.0}}
    p = tmp_path / "bad2.yaml"
    import yaml

    p.write_text(yaml.dump({"experiment": bad, "task": minimal_task_dict}))
    with pytest.raises(ExperimentLoaderError):
        ExperimentLoader.from_yaml(p)


def test_unspecified_agents_retain_behavior(minimal_experiment_dict, minimal_task_dict):
    cfg = dict(minimal_experiment_dict)
    cfg["initial_beliefs"] = {"a0": {"position": "support", "confidence": 0.8}}
    config = ExperimentConfig(**cfg)
    built = ExperimentLoader.build(config, minimal_task_dict)
    a1 = [a for a in built.society.agents if a.agent_id == "a1"][0]
    assert a1.current_belief is None
    assert a1.belief_history == []


def test_initial_belief_visible_only_to_owner_in_round1(minimal_experiment_dict, minimal_task_dict):
    cfg = dict(minimal_experiment_dict)
    cfg["initial_beliefs"] = {"a0": {"position": "support", "confidence": 0.77}}
    config = ExperimentConfig(**cfg)
    built = ExperimentLoader.build(config, minimal_task_dict)

    backend = RecordingBackend()
    orch = Orchestrator(society=built.society, task=built.task, backend=backend)
    result = orch.run()

    # Two calls expected (a0 then a1). First call should include initial belief section.
    assert len(backend.calls) >= 2
    first_messages = backend.calls[0]
    second_messages = backend.calls[1]

    joined_first = "\n".join(m["content"] for m in first_messages)
    joined_second = "\n".join(m["content"] for m in second_messages)

    assert "Your initial belief:" in joined_first
    assert "position: support" in joined_first
    assert "Your initial belief:" not in joined_second

    # RunTrace should include initial_beliefs mapping
    assert result.trace is not None
    assert result.trace.initial_beliefs is not None
    assert "a0" in result.trace.initial_beliefs
    assert result.trace.initial_beliefs["a0"].position == "support"


def test_initial_beliefs_none_preserves_behavior(minimal_experiment_dict, minimal_task_dict):
    config = ExperimentConfig(**minimal_experiment_dict)
    # build society without initial beliefs
    built = ExperimentLoader.build(config, minimal_task_dict)
    backend = RecordingBackend()
    orch = Orchestrator(society=built.society, task=built.task, backend=backend)
    result = orch.run()

    # Ensure no initial belief messages are present
    for call in backend.calls:
        joined = "\n".join(m["content"] for m in call)
        assert "Your initial belief:" not in joined

    assert result.trace is not None
    assert result.trace.initial_beliefs is None
