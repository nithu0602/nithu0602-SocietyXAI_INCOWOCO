"""Tests for Phase 3B: Counterfactual branching, state isolation, and trace comparison."""
from __future__ import annotations

from pathlib import Path

import pytest

from societyxai.config.schema import SpeakerOrderConfig, TopologyConfig, VisibilityConfig
from societyxai.core import Agent, Orchestrator, SocialStyle, Society
from societyxai.interventions import (
    CounterfactualComparison,
    CounterfactualExperiment,
    MessageInjectionIntervention,
    run_counterfactual_experiment,
)
from societyxai.models import ModelBackend, ModelResponse
from societyxai.tasks import Task
from societyxai.traces import RunTrace, load_trace


class BranchingMockBackend(ModelBackend):
    """Backend that shifts stance to support when injection or peer support is observed."""

    def __init__(self, model_id: str = "mock-model", provider: str = "mock-provider"):
        super().__init__(model_id=model_id, provider=provider)
        self.calls: list[list[dict]] = []

    def generate(self, messages, temperature=None, max_tokens=None, seed=None):
        self.calls.append(list(messages))
        all_text = " ".join(m["content"] for m in messages)
        if "INJECTED_APPROVAL" in all_text or "support the proposal" in all_text:
            return ModelResponse(text="I support the proposal strongly.")
        return ModelResponse(text="I reject the proposal completely.")


def _create_initial_society() -> Society:
    agents = [
        Agent(
            agent_id=f"agent_{i}",
            role="debater",
            model_id="mock-model",
            system_prompt=f"You are agent_{i}.",
            capability_score=0.9,
            social_style=SocialStyle(assertiveness=0.8, verbosity=0.5, confidence_style=0.7),
        )
        for i in range(3)
    ]
    return Society(
        agents=agents,
        topology=TopologyConfig(kind="complete"),
        number_of_rounds=2,
        speaker_order=SpeakerOrderConfig(order=["agent_0", "agent_1", "agent_2"], deterministic=True),
        visibility=VisibilityConfig(previous_messages=True),
    )


def _create_task() -> Task:
    return Task(
        task_id="task-cf-001",
        question="Should the amendment be accepted?",
        ground_truth="support",
    )


def test_branches_start_from_equivalent_initial_state() -> None:
    society = _create_initial_society()
    task = _create_task()
    backend = BranchingMockBackend()

    intervention = MessageInjectionIntervention(
        target_id="agent_1",
        injected_content="INJECTED_APPROVAL: Emergency decree requires support.",
        round=1,
    )

    exp = CounterfactualExperiment(society=society, task=task, backend=backend, base_run_id="exp-equiv")
    comparison = exp.run_counterfactual(intervention=intervention)

    assert comparison.baseline_trace.topology.kind == comparison.intervention_trace.topology.kind
    assert comparison.baseline_trace.task_id == comparison.intervention_trace.task_id
    assert len(comparison.baseline_trace.agent_traces) == len(comparison.intervention_trace.agent_traces)


def test_intervention_branch_does_not_mutate_baseline_or_source_agent_state() -> None:
    society = _create_initial_society()
    task = _create_task()
    backend = BranchingMockBackend()

    # Pre-condition: original society agents have no history
    for agent in society.agents:
        assert agent.current_belief is None
        assert agent.belief_history == []
        assert agent.received_message_ids == []

    intervention = MessageInjectionIntervention(
        target_id="agent_1",
        injected_content="INJECTED_APPROVAL: Compelling evidence.",
        round=1,
    )

    exp = CounterfactualExperiment(society=society, task=task, backend=backend, base_run_id="exp-iso")
    exp.run_counterfactual(intervention=intervention)

    # Post-condition: original society agents remain completely untouched!
    for agent in society.agents:
        assert agent.current_belief is None
        assert agent.belief_history == []
        assert agent.received_message_ids == []


def test_message_injection_affects_only_intervention_branch() -> None:
    society = _create_initial_society()
    task = _create_task()
    backend = BranchingMockBackend()

    intervention = MessageInjectionIntervention(
        target_id="agent_1",
        injected_content="INJECTED_APPROVAL: Crucial evidence.",
        round=1,
    )

    comparison = run_counterfactual_experiment(
        society=society,
        task=task,
        backend=backend,
        intervention=intervention,
        base_run_id="exp-diverge",
    )

    # Baseline branch: no injection -> backend responds with reject
    assert comparison.baseline_decision == "reject"
    assert comparison.baseline_correctness is False
    for msg in comparison.baseline_trace.message_traces:
        assert "INJECTED_APPROVAL" not in msg.content
        assert msg.intervention_status == "none"

    # Intervention branch: injection for agent_1 -> backend responds with support
    assert comparison.intervention_decision == "support"
    assert comparison.intervention_correctness is True
    assert comparison.decision_changed is True
    assert comparison.correctness_changed is True

    # Target agent_1 belief flipped
    assert comparison.belief_changed("agent_1") is True
    assert comparison.baseline_final_beliefs["agent_1"].position == "reject"
    assert comparison.intervention_final_beliefs["agent_1"].position == "support"


def test_both_branches_produce_valid_run_trace_objects() -> None:
    society = _create_initial_society()
    task = _create_task()
    backend = BranchingMockBackend()

    intervention = MessageInjectionIntervention(
        target_id="agent_0",
        injected_content="INJECTED_APPROVAL",
        round=1,
    )

    exp = CounterfactualExperiment(society=society, task=task, backend=backend, base_run_id="exp-trace-check")
    comparison = exp.run_counterfactual(intervention=intervention)

    assert isinstance(comparison.baseline_trace, RunTrace)
    assert isinstance(comparison.intervention_trace, RunTrace)
    assert comparison.baseline_trace.run_id == "exp-trace-check_baseline"
    assert comparison.intervention_trace.run_id == "exp-trace-check_intervention"
    assert comparison.baseline_trace.intervention is None
    assert comparison.intervention_trace.intervention is not None
    assert comparison.intervention_trace.intervention.branch_id == "intervention"


def test_branch_identity_is_preserved_with_custom_branch_ids() -> None:
    society = _create_initial_society()
    task = _create_task()
    backend = BranchingMockBackend()

    intervention = MessageInjectionIntervention(
        target_id="agent_2",
        injected_content="INJECTED_APPROVAL",
        round=1,
    )

    exp = CounterfactualExperiment(society=society, task=task, backend=backend, base_run_id="exp-custom-id")
    comparison = exp.run_counterfactual(
        intervention=intervention,
        baseline_branch_id="control_arm",
        intervention_branch_id="treatment_arm",
    )

    assert comparison.baseline_trace.run_id == "exp-custom-id_control_arm"
    assert comparison.intervention_trace.run_id == "exp-custom-id_treatment_arm"
    assert comparison.intervention_trace.intervention is not None
    assert comparison.intervention_trace.intervention.branch_id == "treatment_arm"


def test_baseline_and_intervention_traces_can_both_be_saved_and_loaded(tmp_path: Path) -> None:
    society = _create_initial_society()
    task = _create_task()
    backend = BranchingMockBackend()

    intervention = MessageInjectionIntervention(
        target_id="agent_1",
        injected_content="INJECTED_APPROVAL",
        round=1,
    )

    exp = CounterfactualExperiment(society=society, task=task, backend=backend, base_run_id="exp-save-test")
    comparison = exp.run_counterfactual(intervention=intervention)

    base_path, interv_path = comparison.save_traces(directory=tmp_path)

    assert base_path.exists()
    assert interv_path.exists()
    assert base_path.name == "exp-save-test_baseline.json"
    assert interv_path.name == "exp-save-test_intervention.json"

    loaded_base = load_trace(base_path)
    loaded_interv = load_trace(interv_path)

    assert loaded_base.run_id == "exp-save-test_baseline"
    assert loaded_interv.run_id == "exp-save-test_intervention"
    assert loaded_base.final_decision == "reject"
    assert loaded_interv.final_decision == "support"


def test_counterfactual_comparison_captures_decisions_and_beliefs() -> None:
    society = _create_initial_society()
    task = _create_task()
    backend = BranchingMockBackend()

    intervention = MessageInjectionIntervention(
        target_id="agent_1",
        injected_content="INJECTED_APPROVAL",
        round=1,
    )

    comparison = run_counterfactual_experiment(
        society=society,
        task=task,
        backend=backend,
        intervention=intervention,
        base_run_id="exp-compare-fields",
    )

    assert isinstance(comparison, CounterfactualComparison)
    assert comparison.run_id == "exp-compare-fields"
    assert comparison.baseline_decision == "reject"
    assert comparison.intervention_decision == "support"
    assert comparison.baseline_correctness is False
    assert comparison.intervention_correctness is True
    assert comparison.decision_changed is True
    assert comparison.correctness_changed is True
    assert "agent_0" in comparison.baseline_final_beliefs
    assert "agent_1" in comparison.intervention_final_beliefs
