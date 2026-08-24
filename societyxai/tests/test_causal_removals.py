"""Focused tests for agent removal and message removal counterfactual interventions."""
from __future__ import annotations

from pathlib import Path

from societyxai.config.schema import SpeakerOrderConfig, TopologyConfig, VisibilityConfig
from societyxai.core import Agent, Society
from societyxai.interventions import AgentRemovalIntervention, CounterfactualExperiment, MessageRemovalIntervention
from societyxai.models import ModelBackend, ModelResponse
from societyxai.models.registry import BackendRegistry
from societyxai.tasks import Task
from societyxai.traces import RunTrace, load_trace


class BranchBackend(ModelBackend):
    """Backend that exposes whether a target marker is present in the prompt."""

    def __init__(self, model_id: str, provider: str):
        super().__init__(model_id=model_id, provider=provider)
        self.calls: list[list[dict]] = []

    def generate(self, messages, temperature=None, max_tokens=None, seed=None):
        self.calls.append(list(messages))
        if messages[0]["content"] == "A1":
            return ModelResponse(text="I support REMOVE_ME")
        text = "support" if any("REMOVE_ME" in msg["content"] for msg in messages) else "reject"
        return ModelResponse(text=text)


class FixedBackend(ModelBackend):
    """Backend that returns a fixed response and records calls."""

    def __init__(self, model_id: str, provider: str, response: str):
        super().__init__(model_id=model_id, provider=provider)
        self.response = response
        self.calls: list[list[dict]] = []

    def generate(self, messages, temperature=None, max_tokens=None, seed=None):
        self.calls.append(list(messages))
        return ModelResponse(text=self.response)


def _agent(agent_id: str, model_id: str) -> Agent:
    return Agent(agent_id=agent_id, role="speaker", model_id=model_id, system_prompt=agent_id.upper())


def _task() -> Task:
    return Task(task_id="task-removal-001", question="Q?", ground_truth="support")


def test_agent_removal_excludes_target_agent_and_preserves_models() -> None:
    agents = [_agent("a1", "m1"), _agent("a2", "m2"), _agent("a3", "m2")]
    society = Society(
        agents=agents,
        topology=TopologyConfig(kind="line", adjacency=[[1], [0, 2], [1]]),
        number_of_rounds=1,
        speaker_order=SpeakerOrderConfig(order=["a1", "a2", "a3"], deterministic=True),
        visibility=VisibilityConfig(previous_messages=True),
    )
    task = _task()
    backend_1 = FixedBackend("m1", "p1", "support")
    backend_2 = FixedBackend("m2", "p2", "reject")
    registry = BackendRegistry(default=backend_1)
    registry.register("m2", backend_2)

    experiment = CounterfactualExperiment(
        society=society,
        task=task,
        backend=backend_1,
        seed=7,
        temperature=0.3,
        backend_registry=registry,
    )
    comparison = experiment.run_counterfactual(AgentRemovalIntervention(target_id="a2"))

    assert comparison.baseline_trace is not None
    assert comparison.intervention_trace is not None
    assert comparison.baseline_trace.seed == comparison.intervention_trace.seed == 7
    assert comparison.baseline_trace.temperature == comparison.intervention_trace.temperature == 0.3
    assert comparison.baseline_trace.task_id == comparison.intervention_trace.task_id == "task-removal-001"
    assert comparison.baseline_trace.final_decision == "reject"
    assert comparison.intervention_trace.final_decision == "reject"
    assert [turn.agent_id for turn in comparison.baseline_trace.agent_traces] == ["a1", "a2", "a3"]
    assert [turn.agent_id for turn in comparison.intervention_trace.agent_traces] == ["a1", "a3"]
    assert [turn.model_id for turn in comparison.intervention_trace.agent_traces] == ["m1", "m2"]
    assert comparison.intervention_trace.topology.adjacency == [[], []]
    assert comparison.intervention_trace.intervention is not None
    assert comparison.intervention_trace.intervention.intervention_type == "agent_removal"
    assert comparison.intervention_trace.intervention.target_id == "a2"
    assert society.speaker_order.order == ["a1", "a2", "a3"]
    assert len(society.agents) == 3


def test_agent_removal_branch_remains_independently_mutable() -> None:
    agents = [_agent("a1", "m1"), _agent("a2", "m2")]
    society = Society(
        agents=agents,
        topology=TopologyConfig(kind="complete"),
        number_of_rounds=1,
        speaker_order=SpeakerOrderConfig(order=["a1", "a2"], deterministic=True),
        visibility=VisibilityConfig(previous_messages=True),
    )
    backend = FixedBackend("m1", "p1", "support")
    experiment = CounterfactualExperiment(society=society, task=_task(), backend=backend)
    comparison = experiment.run_counterfactual(AgentRemovalIntervention(target_id="a2"))

    comparison.intervention_trace.agent_traces[0].belief.position = "neutral"
    assert comparison.baseline_trace.agent_traces[0].belief.position == "support"


def test_message_removal_excludes_target_from_branch_context_and_round_trips(tmp_path: Path) -> None:
    agents = [_agent("a1", "m1"), _agent("a2", "m1")]
    society = Society(
        agents=agents,
        topology=TopologyConfig(kind="complete"),
        number_of_rounds=1,
        speaker_order=SpeakerOrderConfig(order=["a1", "a2"], deterministic=True),
        visibility=VisibilityConfig(previous_messages=True),
    )
    backend = BranchBackend("m1", "p1")
    experiment = CounterfactualExperiment(society=society, task=_task(), backend=backend)
    comparison = experiment.run_counterfactual(MessageRemovalIntervention(target_id="r1_t1_a1"))

    assert comparison.baseline_trace.final_decision == "support"
    assert comparison.intervention_trace.final_decision == "reject"
    assert comparison.intervention_trace.intervention is not None
    assert comparison.intervention_trace.intervention.intervention_type == "message_removal"
    assert comparison.intervention_trace.intervention.target_id == "r1_t1_a1"
    assert comparison.intervention_trace.message_traces[0].intervention_status == "message_removal"
    assert comparison.intervention_trace.message_traces[1].parent_message_ids == []
    assert len(backend.calls) == 4
    assert not any("REMOVE_ME" in msg["content"] for msg in backend.calls[3])

    saved = comparison.intervention_trace.save(directory=tmp_path, filename="message-removal.json")
    loaded = load_trace(saved)
    assert isinstance(loaded, RunTrace)
    assert loaded.intervention is not None
    assert loaded.intervention.intervention_type == "message_removal"
    assert loaded.intervention.target_id == "r1_t1_a1"
    assert loaded.message_traces[1].parent_message_ids == []
