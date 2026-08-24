"""Tests for RunTrace generation, trace properties, and JSON persistence."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from societyxai.config.schema import SpeakerOrderConfig, TopologyConfig, VisibilityConfig
from societyxai.core import Agent, Orchestrator, SocialStyle, Society
from societyxai.models import ModelBackend, ModelResponse
from societyxai.models.registry import BackendRegistry
from societyxai.tasks import Task
from societyxai.traces import (
    AgentTrace,
    BeliefState,
    MessageTrace,
    RunTrace,
    load_trace,
    save_trace,
)


class MockBackend(ModelBackend):
    def __init__(self, model_id: str = "mock-model", provider: str = "mock-provider", response_text: str = "I support this proposal"):
        super().__init__(model_id=model_id, provider=provider)
        self.response_text = response_text
        self.calls: list[list[dict]] = []

    def generate(self, messages, temperature=None, max_tokens=None, seed=None):
        self.calls.append(list(messages))
        return ModelResponse(text=self.response_text)


def _create_test_society(agent_count: int = 3, rounds: int = 2) -> Society:
    agents = [
        Agent(
            agent_id=f"agent_{i}",
            role="debater",
            model_id="mock-model",
            system_prompt=f"You are agent_{i}.",
            capability_score=0.85,
            social_style=SocialStyle(assertiveness=0.7, verbosity=0.6, confidence_style=0.8),
        )
        for i in range(agent_count)
    ]
    order = [f"agent_{i}" for i in range(agent_count)]
    return Society(
        agents=agents,
        topology=TopologyConfig(kind="complete"),
        number_of_rounds=rounds,
        speaker_order=SpeakerOrderConfig(order=order, deterministic=True),
        visibility=VisibilityConfig(previous_messages=True),
    )


def _create_test_task(task_id: str = "task-001", ground_truth: str = "support") -> Task:
    return Task(
        task_id=task_id,
        question="Should we proceed with the initiative?",
        ground_truth=ground_truth,
    )


def test_orchestrator_generates_valid_run_trace() -> None:
    society = _create_test_society(agent_count=2, rounds=2)
    task = _create_test_task()
    backend = MockBackend()

    orchestrator = Orchestrator(
        society=society,
        task=task,
        backend=backend,
        run_id="run-test-100",
        seed=42,
        temperature=0.5,
    )
    result = orchestrator.run()

    # Verify ExecutionResult has trace attached
    assert result.trace is not None
    assert isinstance(result.trace, RunTrace)
    assert result.to_run_trace() is result.trace
    assert orchestrator.last_trace is result.trace

    # Check top-level RunTrace attributes
    trace = result.trace
    assert trace.run_id == "run-test-100"
    assert trace.task_id == "task-001"
    assert trace.seed == 42
    assert trace.temperature == 0.5
    assert trace.model_id == "mock-model"
    assert trace.provider == "mock-provider"
    assert trace.topology.kind == "complete"
    assert trace.speaker_order == ["agent_0", "agent_1"]
    assert trace.visibility is not None
    assert trace.visibility.previous_messages is True
    assert trace.ground_truth == "support"
    assert trace.system_prompt_hash is not None
    assert len(trace.system_prompt_hash) == 64


def test_message_trace_creation_and_topology_parents() -> None:
    # Use line topology: a0 -> a1 -> a2
    agents = [
        Agent(agent_id=f"a{i}", role="debater", model_id="m", system_prompt="sys")
        for i in range(3)
    ]
    society = Society(
        agents=agents,
        topology=TopologyConfig(kind="line", adjacency=[[1], [0, 2], [1]]),
        number_of_rounds=1,
        speaker_order=SpeakerOrderConfig(order=["a0", "a1", "a2"], deterministic=True),
        visibility=VisibilityConfig(previous_messages=True),
    )
    task = _create_test_task()
    backend = MockBackend()

    result = Orchestrator(society=society, task=task, backend=backend, run_id="run-msg-test").run()
    assert result.trace is not None
    msg_traces = result.trace.message_traces

    assert len(msg_traces) == 3
    assert all(isinstance(m, MessageTrace) for m in msg_traces)

    # Turn 1: a0 speaks, no parents
    assert msg_traces[0].agent_id == "a0"
    assert msg_traces[0].message_id == "r1_t1_a0"
    assert msg_traces[0].parent_message_ids == []
    assert len(msg_traces[0].content_hash) == 64
    assert msg_traces[0].intervention_status == "none"

    # Turn 2: a1 speaks, sees a0's message
    assert msg_traces[1].agent_id == "a1"
    assert msg_traces[1].message_id == "r1_t2_a1"
    assert msg_traces[1].parent_message_ids == ["r1_t1_a0"]

    # Turn 3: a2 speaks, with line topology [[1], [0, 2], [1]], a2 sees a1 (index 1), not a0
    assert msg_traces[2].agent_id == "a2"
    assert msg_traces[2].message_id == "r1_t3_a2"
    assert msg_traces[2].parent_message_ids == ["r1_t2_a1"]


def test_agent_trace_creation_and_belief_snapshots() -> None:
    society = _create_test_society(agent_count=2, rounds=2)
    task = _create_test_task()
    backend = MockBackend(response_text="I approve this plan completely.")

    result = Orchestrator(society=society, task=task, backend=backend, run_id="run-agent-test").run()
    assert result.trace is not None
    agent_traces = result.trace.agent_traces

    assert len(agent_traces) == 4  # 2 agents * 2 rounds
    assert all(isinstance(at, AgentTrace) for at in agent_traces)

    # First turn agent trace
    at0 = agent_traces[0]
    assert at0.agent_id == "agent_0"
    assert at0.role == "debater"
    assert at0.capability_score == 0.85
    assert "assertiveness=0.7" in at0.social_style
    assert at0.round == 1
    assert at0.turn_index == 1
    assert isinstance(at0.belief, BeliefState)
    assert at0.belief.position == "support"
    assert at0.belief.confidence == 1.0


def test_belief_history_tracked_on_agents_and_traces() -> None:
    society = _create_test_society(agent_count=2, rounds=3)
    task = _create_test_task()
    backend = MockBackend(response_text="We must reject this completely.")

    result = Orchestrator(society=society, task=task, backend=backend).run()
    assert result.trace is not None

    # Check belief position across traces
    for at in result.trace.agent_traces:
        assert at.belief.position == "reject"

    # Check agent instance history
    for agent in society.agents:
        assert len(agent.belief_history) == 3
        assert all(b.position == "reject" for b in agent.belief_history)


def test_run_trace_json_roundtrip_serialization() -> None:
    society = _create_test_society(agent_count=2, rounds=1)
    task = _create_test_task()
    backend = MockBackend()

    result = Orchestrator(society=society, task=task, backend=backend, run_id="roundtrip-run").run()
    assert result.trace is not None

    # Serialize to JSON string
    json_data = result.trace.model_dump_json(indent=2)
    assert isinstance(json_data, str)

    parsed_raw = json.loads(json_data)
    assert parsed_raw["run_id"] == "roundtrip-run"
    assert parsed_raw["task_id"] == "task-001"
    assert len(parsed_raw["agent_traces"]) == 2
    assert len(parsed_raw["message_traces"]) == 2

    # Deserialize back into RunTrace
    reconstructed = RunTrace.model_validate_json(json_data)
    assert reconstructed.run_id == result.trace.run_id
    assert reconstructed.task_id == result.trace.task_id
    assert len(reconstructed.agent_traces) == len(result.trace.agent_traces)
    assert len(reconstructed.message_traces) == len(result.trace.message_traces)
    assert reconstructed.topology.kind == result.trace.topology.kind


def test_heterogeneous_trace_attribution_roundtrip(tmp_path: Path) -> None:
    agents = [
        Agent(agent_id="agent_0", role="debater", model_id="model-a", system_prompt="You are agent_0."),
        Agent(agent_id="agent_1", role="debater", model_id="model-b", system_prompt="You are agent_1."),
    ]
    society = Society(
        agents=agents,
        topology=TopologyConfig(kind="complete"),
        number_of_rounds=1,
        speaker_order=SpeakerOrderConfig(order=["agent_0", "agent_1"], deterministic=True),
        visibility=VisibilityConfig(previous_messages=True),
    )
    task = _create_test_task()
    backend_a = MockBackend(model_id="model-a", provider="provider-a", response_text="I support this proposal")
    backend_b = MockBackend(model_id="model-b", provider="provider-b", response_text="I reject this proposal")
    registry = BackendRegistry(default=backend_a)
    registry.register("model-b", backend_b)

    result = Orchestrator(
        society=society,
        task=task,
        backend=backend_a,
        backend_registry=registry,
    ).run()

    assert result.trace is not None
    assert [trace.model_id for trace in result.trace.agent_traces] == ["model-a", "model-b"]
    assert [trace.provider for trace in result.trace.agent_traces] == ["provider-a", "provider-b"]

    saved = result.trace.save(directory=tmp_path, filename="heterogeneous.json")
    loaded = RunTrace.load(saved)
    assert [trace.model_id for trace in loaded.agent_traces] == ["model-a", "model-b"]
    assert [trace.provider for trace in loaded.agent_traces] == ["provider-a", "provider-b"]


def test_legacy_trace_without_nested_model_metadata_still_loads(tmp_path: Path) -> None:
    society = _create_test_society(agent_count=2, rounds=1)
    task = _create_test_task()
    backend = MockBackend()
    result = Orchestrator(society=society, task=task, backend=backend, run_id="legacy-run").run()
    assert result.trace is not None

    payload = json.loads(result.trace.model_dump_json())
    for trace in payload["agent_traces"]:
        trace.pop("model_id", None)
        trace.pop("provider", None)
    for trace in payload["message_traces"]:
        trace.pop("model_id", None)
        trace.pop("provider", None)

    legacy_path = tmp_path / "legacy.json"
    legacy_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    loaded = load_trace(legacy_path)
    assert loaded.run_id == "legacy-run"
    assert all(trace.model_id is None for trace in loaded.agent_traces)
    assert all(trace.provider is None for trace in loaded.agent_traces)
    assert all(trace.model_id is None for trace in loaded.message_traces)
    assert all(trace.provider is None for trace in loaded.message_traces)


def test_trace_save_and_load_persistence(tmp_path: Path) -> None:
    society = _create_test_society(agent_count=2, rounds=1)
    task = _create_test_task()
    backend = MockBackend()

    result = Orchestrator(society=society, task=task, backend=backend, run_id="persist-run-001").run()
    assert result.trace is not None

    # Save using save_trace function
    saved_path = save_trace(result.trace, directory=tmp_path)
    assert saved_path.exists()
    assert saved_path.name == "persist-run-001.json"

    # Load using load_trace function
    loaded = load_trace(saved_path)
    assert isinstance(loaded, RunTrace)
    assert loaded.run_id == "persist-run-001"
    assert loaded.task_id == "task-001"

    # Save using RunTrace.save() method
    custom_saved = result.trace.save(directory=tmp_path, filename="custom_name.json")
    assert custom_saved.exists()
    assert custom_saved.name == "custom_name.json"

    loaded_custom = RunTrace.load(custom_saved)
    assert loaded_custom.run_id == "persist-run-001"

    # Save using ExecutionResult.save_trace()
    result_saved = result.save_trace(directory=tmp_path, filename="from_result.json")
    assert result_saved is not None
    assert result_saved.exists()


def test_load_trace_nonexistent_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        load_trace(tmp_path / "nonexistent.json")


def test_final_decision_and_correctness_evaluation() -> None:
    society = _create_test_society(agent_count=1, rounds=1)

    # Case 1: Ground truth matches decision
    task_support = _create_test_task(ground_truth="support")
    backend_support = MockBackend(response_text="I support this proposal")
    r1 = Orchestrator(society=society, task=task_support, backend=backend_support).run()
    assert r1.trace is not None
    assert r1.trace.final_decision == "support"
    assert r1.trace.correctness is True

    # Case 2: Ground truth opposes decision
    task_reject = _create_test_task(ground_truth="reject")
    r2 = Orchestrator(society=society, task=task_reject, backend=backend_support).run()
    assert r2.trace is not None
    assert r2.trace.final_decision == "support"
    assert r2.trace.correctness is False
