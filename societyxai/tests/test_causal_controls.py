"""Focused tests for speaker-order and visibility counterfactual interventions."""
from __future__ import annotations

from societyxai.config.schema import SpeakerOrderConfig, TopologyConfig, VisibilityConfig
from societyxai.core import Agent, Orchestrator, Society
from societyxai.interventions import (
    ConfidenceVisibilityIntervention,
    CounterfactualExperiment,
    MajorityVisibilityIntervention,
    SpeakerOrderingIntervention,
)
from societyxai.models import ModelBackend, ModelResponse
from societyxai.tasks import Task
from societyxai.traces.schema import BeliefState


class RecordingBackend(ModelBackend):
    def __init__(self, model_id: str = "m", provider: str = "p"):
        super().__init__(model_id=model_id, provider=provider)
        self.calls: list[list[dict]] = []

    def generate(self, messages, temperature=None, max_tokens=None, seed=None):
        self.calls.append(list(messages))
        return ModelResponse(text="support")


def _agent(agent_id: str) -> Agent:
    return Agent(agent_id=agent_id, role="speaker", model_id="m", system_prompt=agent_id.upper())


def _task() -> Task:
    return Task(task_id="task-visibility-001", question="Q?", ground_truth="support")


def _society(visibility: VisibilityConfig, order: list[str] | None = None) -> Society:
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    return Society(
        agents=agents,
        topology=TopologyConfig(kind="line", adjacency=[[1], [0, 2], [1]]),
        number_of_rounds=1,
        speaker_order=SpeakerOrderConfig(order=order or ["a1", "a2", "a3"], deterministic=True),
        visibility=visibility,
    )


def test_speaker_ordering_intervention_changes_execution_order() -> None:
    backend = RecordingBackend()
    society = _society(VisibilityConfig(previous_messages=True), order=["a1", "a2", "a3"])
    experiment = CounterfactualExperiment(society=society, task=_task(), backend=backend)
    comparison = experiment.run_counterfactual(SpeakerOrderingIntervention(["a3", "a2", "a1"]))

    assert comparison.baseline_trace.speaker_order == ["a1", "a2", "a3"]
    assert comparison.intervention_trace.speaker_order == ["a3", "a2", "a1"]
    assert [turn.agent_id for turn in comparison.baseline_trace.agent_traces] == ["a1", "a2", "a3"]
    assert [turn.agent_id for turn in comparison.intervention_trace.agent_traces] == ["a3", "a2", "a1"]
    assert comparison.intervention_trace.topology.adjacency == [[1], [2, 0], [1]]
    assert society.speaker_order.order == ["a1", "a2", "a3"]
    assert len(society.agents) == 3


def test_confidence_visibility_intervention_toggles_prompt_section() -> None:
    backend = RecordingBackend()
    society = _society(VisibilityConfig(previous_messages=True, confidence=True))
    experiment = CounterfactualExperiment(society=society, task=_task(), backend=backend)
    comparison = experiment.run_counterfactual(ConfidenceVisibilityIntervention(False))

    assert comparison.baseline_trace.visibility is not None
    assert comparison.baseline_trace.visibility.confidence is True
    assert comparison.intervention_trace.visibility is not None
    assert comparison.intervention_trace.visibility.confidence is False
    assert any(msg["content"].startswith("Confidence levels") for msg in backend.calls[1] if msg["role"] == "user")
    assert not any(msg["content"].startswith("Confidence levels") for msg in backend.calls[4] if msg["role"] == "user")


def test_majority_visibility_intervention_toggles_prompt_section() -> None:
    backend = RecordingBackend()
    society = _society(VisibilityConfig(previous_messages=True, majority_position=True))
    experiment = CounterfactualExperiment(society=society, task=_task(), backend=backend)
    comparison = experiment.run_counterfactual(MajorityVisibilityIntervention(False))

    assert comparison.baseline_trace.visibility is not None
    assert comparison.baseline_trace.visibility.majority_position is True
    assert comparison.intervention_trace.visibility is not None
    assert comparison.intervention_trace.visibility.majority_position is False
    assert any(msg["content"].startswith("Current majority position") for msg in backend.calls[1] if msg["role"] == "user")
    assert not any(msg["content"].startswith("Current majority position") for msg in backend.calls[4] if msg["role"] == "user")


def test_visible_agent_metadata_respects_explicit_adjacency_order() -> None:
    agents = [_agent("a0"), _agent("a1"), _agent("a2")]
    agents[0].current_belief = BeliefState(position="reject", confidence=0.25, evidence_ids=[])
    agents[2].current_belief = BeliefState(position="support", confidence=0.75, evidence_ids=[])

    society = Society(
        agents=agents,
        topology=TopologyConfig(kind="custom", adjacency=[[1], [2, 0], [1]]),
        number_of_rounds=1,
        speaker_order=SpeakerOrderConfig(order=["a0", "a1", "a2"], deterministic=True),
        visibility=VisibilityConfig(previous_messages=True, confidence=True, majority_position=True),
    )
    orchestrator = Orchestrator(society=society, task=_task(), backend=RecordingBackend())
    adjacency_lookup = orchestrator._build_adjacency_lookup()
    agent_by_id = {agent.agent_id: agent for agent in society.agents}

    confidence_info = orchestrator._collect_confidence_info("a1", adjacency_lookup, agent_by_id)
    assert [item["agent_id"] for item in confidence_info] == ["a2", "a0"]
    assert confidence_info[0]["confidence"] == 0.75
    assert confidence_info[1]["confidence"] == 0.25

    majority_position = orchestrator._compute_majority_position("a1", adjacency_lookup, agent_by_id)
    assert majority_position == "support"
