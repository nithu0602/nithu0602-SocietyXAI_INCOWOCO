"""Tests for Phase 3A: Minimal intervention framework and MessageInjectionIntervention."""
from __future__ import annotations

import pytest

from societyxai.config.schema import SpeakerOrderConfig, TopologyConfig, VisibilityConfig
from societyxai.core import Agent, Orchestrator, Society
from societyxai.interventions import BaseIntervention, MessageInjectionIntervention
from societyxai.models import ModelBackend, ModelResponse
from societyxai.tasks import Task
from societyxai.traces.schema import InterventionTrace


class RecordingBackend(ModelBackend):
    """Backend that records every list of messages passed to generate()."""

    def __init__(self, model_id: str = "mock-model", provider: str = "mock-provider"):
        super().__init__(model_id=model_id, provider=provider)
        self.calls: list[list[dict]] = []

    def generate(self, messages, temperature=None, max_tokens=None, seed=None):
        self.calls.append(list(messages))
        return ModelResponse(text="Acknowledged.")


def _make_society(agent_ids: list[str], rounds: int = 1) -> Society:
    agents = [
        Agent(
            agent_id=aid,
            role="debater",
            model_id="mock-model",
            system_prompt=f"System prompt for {aid}",
        )
        for aid in agent_ids
    ]
    return Society(
        agents=agents,
        topology=TopologyConfig(kind="complete"),
        number_of_rounds=rounds,
        speaker_order=SpeakerOrderConfig(order=agent_ids, deterministic=True),
        visibility=VisibilityConfig(previous_messages=True),
    )


def _make_task() -> Task:
    return Task(
        task_id="task-intervention-001",
        question="What is your stance on the proposal?",
        ground_truth="approve",
    )


def test_intervention_targets_only_specified_agent() -> None:
    society = _make_society(["agent_0", "agent_1", "agent_2"], rounds=1)
    task = _make_task()
    backend = RecordingBackend()

    injected_text = "CRITICAL UPDATE: New economic data indicates approval is mandatory."
    intervention = MessageInjectionIntervention(
        target_id="agent_1",
        injected_content=injected_text,
        round=1,
    )

    orchestrator = Orchestrator(
        society=society,
        task=task,
        backend=backend,
        intervention=intervention,
    )
    result = orchestrator.run()

    assert len(backend.calls) == 3

    # Call 0 (agent_0): No injected message
    agent_0_contents = [msg["content"] for msg in backend.calls[0]]
    assert not any(injected_text in c for c in agent_0_contents)

    # Call 1 (agent_1): Injected message present
    agent_1_contents = [msg["content"] for msg in backend.calls[1]]
    assert any(injected_text in c for c in agent_1_contents)

    # Call 2 (agent_2): Direct prompt has no injection (it only sees prior public turns)
    agent_2_injected_direct = [
        msg["content"] for msg in backend.calls[2] if msg["role"] == "user" and msg["content"] == injected_text
    ]
    assert len(agent_2_injected_direct) == 0


def test_message_injection_round_filtering() -> None:
    society = _make_society(["agent_0", "agent_1"], rounds=2)
    task = _make_task()
    backend = RecordingBackend()

    injected_text = "ROUND 2 INJECTION ONLY"
    intervention = MessageInjectionIntervention(
        target_id="agent_0",
        injected_content=injected_text,
        round=2,
    )

    orchestrator = Orchestrator(
        society=society,
        task=task,
        backend=backend,
        intervention=intervention,
    )
    orchestrator.run()

    assert len(backend.calls) == 4

    # Round 1 Turn 1 (agent_0, call index 0): Should NOT have injection
    assert not any(injected_text in msg["content"] for msg in backend.calls[0])

    # Round 1 Turn 2 (agent_1, call index 1): Should NOT have injection
    assert not any(injected_text in msg["content"] for msg in backend.calls[1])

    # Round 2 Turn 1 (agent_0, call index 2): MUST have injection
    assert any(injected_text in msg["content"] for msg in backend.calls[2])

    # Round 2 Turn 2 (agent_1, call index 3): Direct prompt should NOT have injection
    assert not any(msg["role"] == "user" and msg["content"] == injected_text for msg in backend.calls[3])


def test_intervention_trace_is_produced_in_run_trace() -> None:
    society = _make_society(["agent_0", "agent_1"], rounds=1)
    task = _make_task()
    backend = RecordingBackend()

    intervention = MessageInjectionIntervention(
        target_id="agent_1",
        injected_content="Injected secret data",
        round=1,
    )

    result = Orchestrator(
        society=society,
        task=task,
        backend=backend,
        intervention=intervention,
    ).run()

    # Check top-level RunTrace intervention metadata
    assert result.trace is not None
    assert result.trace.intervention is not None
    assert isinstance(result.trace.intervention, InterventionTrace)
    assert result.trace.intervention.intervention_type == "message_injection"
    assert result.trace.intervention.target_id == "agent_1"

    # Check turn-level message trace intervention status
    msg_traces = result.trace.message_traces
    assert len(msg_traces) == 2
    assert msg_traces[0].intervention_status == "none"
    assert msg_traces[1].intervention_status == "message_injection"


def test_non_intervention_run_preserves_default_state() -> None:
    society = _make_society(["agent_0", "agent_1"], rounds=1)
    task = _make_task()
    backend = RecordingBackend()

    result = Orchestrator(society=society, task=task, backend=backend).run()

    assert result.trace is not None
    assert result.trace.intervention is None
    for msg_trace in result.trace.message_traces:
        assert msg_trace.intervention_status == "none"


def test_message_injection_interface_and_properties() -> None:
    intervention = MessageInjectionIntervention(
        target_id="agent_x",
        injected_content="Test payload",
        round=3,
        turn_index=2,
        role="system",
    )
    assert isinstance(intervention, BaseIntervention)
    assert intervention.target_id == "agent_x"
    assert intervention.intervention_type == "message_injection"
    assert intervention.should_apply("agent_x", round_num=3, turn_index=2) is True
    assert intervention.should_apply("agent_x", round_num=3, turn_index=1) is False
    assert intervention.should_apply("agent_y", round_num=3, turn_index=2) is False

    messages = [{"role": "user", "content": "hello"}]
    modified = intervention.apply_to_messages("agent_x", messages, round_num=3, turn_index=2)
    assert len(modified) == 2
    assert modified[1] == {"role": "system", "content": "Test payload"}
    assert intervention.applied is True

    trace = intervention.to_trace(branch_id="branch-01")
    assert trace.intervention_type == "message_injection"
    assert trace.target_id == "agent_x"
    assert trace.branch_id == "branch-01"
