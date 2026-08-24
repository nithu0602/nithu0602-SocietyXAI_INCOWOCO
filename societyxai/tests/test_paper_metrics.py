"""Tests for paper-scoped metrics and repeated-run aggregation."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from societyxai.config.schema import TopologyConfig
from societyxai.interventions.branching import CounterfactualComparison
from societyxai.traces import AgentTrace, BeliefState, MessageTrace, RunTrace
from societyxai.traces.schema import InterventionTrace
from societyxai.utils.paper_metrics import (
    CounterfactualMetricAggregate,
    confidence_shift,
    consensus_accuracy,
    conformity_index,
    counterfactual_agent_effect,
    counterfactual_minority_recovery_rate,
    counterfactual_message_effect,
    false_consensus_rate,
    gini_coefficient,
    mean_confidence_shift,
    minority_recovery_rate,
)


def _belief(position: str, confidence: float) -> BeliefState:
    return BeliefState(position=position, confidence=confidence, evidence_ids=[], reasoning_trace="")


def _agent_trace(
    agent_id: str,
    round_: int,
    turn_index: int,
    position: str,
    confidence: float = 1.0,
    exposed_majority_position: str | None = None,
) -> AgentTrace:
    return AgentTrace(
        agent_id=agent_id,
        role="speaker",
        round=round_,
        turn_index=turn_index,
        belief=_belief(position, confidence),
        exposed_majority_position=exposed_majority_position,
    )


def _message_trace(message_id: str, agent_id: str, round_: int, turn_index: int) -> MessageTrace:
    return MessageTrace(
        message_id=message_id,
        agent_id=agent_id,
        round=round_,
        turn_index=turn_index,
        content="content",
    )


def _run_trace(
    agent_traces: list[AgentTrace],
    *,
    final_decision: str | None = None,
    correctness: bool | None = None,
    initial_beliefs: dict[str, BeliefState] | None = None,
    ground_truth: str | None = "support",
) -> RunTrace:
    return RunTrace(
        run_id="run-1",
        task_id="task-1",
        seed=1,
        timestamp=datetime.now(timezone.utc),
        model_id="m",
        provider="p",
        temperature=0.0,
        topology=TopologyConfig(kind="complete"),
        agent_traces=agent_traces,
        message_traces=[],
        final_decision=final_decision,
        correctness=correctness,
        initial_beliefs=initial_beliefs,
        ground_truth=ground_truth,
        speaker_order=["a1", "a2", "a3", "a4", "a5"],
    )


def _comparison(
    baseline: RunTrace,
    intervention: RunTrace,
    intervention_type: str,
    target_id: str,
) -> CounterfactualComparison:
    return CounterfactualComparison(
        run_id="cmp-1",
        baseline_trace=baseline,
        intervention_trace=intervention,
        intervention=InterventionTrace(
            intervention_type=intervention_type,
            target_id=target_id,
            branch_id="branch",
        ),
        baseline_decision=baseline.final_decision,
        intervention_decision=intervention.final_decision,
        baseline_correctness=baseline.correctness,
        intervention_correctness=intervention.correctness,
        baseline_final_beliefs={at.agent_id: at.belief for at in baseline.agent_traces},
        intervention_final_beliefs={at.agent_id: at.belief for at in intervention.agent_traces},
    )


def test_consensus_accuracy_uses_final_correctness() -> None:
    trace = _run_trace([_agent_trace("a1", 1, 1, "support")], final_decision="support", correctness=True)
    assert consensus_accuracy(trace) == 1.0
    trace = _run_trace([_agent_trace("a1", 1, 1, "support")], final_decision="support", correctness=False)
    assert consensus_accuracy(trace) == 0.0


def test_conformity_index_counts_flips_after_majority_exposure() -> None:
    trace = _run_trace(
        [
            _agent_trace("a1", 1, 1, "support"),
            _agent_trace("a2", 1, 2, "support"),
            _agent_trace("a1", 2, 1, "reject", exposed_majority_position="support"),
            _agent_trace("a2", 2, 2, "reject"),
        ]
    )
    assert conformity_index(trace) == 0.5


def test_confidence_shift_and_mean_shift_use_initial_beliefs() -> None:
    initial = {
        "a1": _belief("support", 0.2),
        "a2": _belief("reject", 0.8),
    }
    trace = _run_trace(
        [
            _agent_trace("a1", 1, 1, "support", confidence=0.7),
            _agent_trace("a2", 1, 2, "reject", confidence=0.4),
        ],
        initial_beliefs=initial,
    )
    shifts = confidence_shift(trace)
    assert shifts["a1"] == pytest.approx(0.5)
    assert shifts["a2"] == pytest.approx(-0.4)
    assert mean_confidence_shift(trace) == pytest.approx(0.05)


def test_false_consensus_rate_uses_four_of_five_threshold() -> None:
    false_consensus = _run_trace(
        [
            _agent_trace("a1", 1, 1, "support"),
            _agent_trace("a2", 1, 2, "support"),
            _agent_trace("a3", 1, 3, "support"),
            _agent_trace("a4", 1, 4, "support"),
            _agent_trace("a5", 1, 5, "reject"),
        ],
        final_decision="support",
        correctness=False,
    )
    normal = _run_trace(
        [
            _agent_trace("a1", 1, 1, "support"),
            _agent_trace("a2", 1, 2, "support"),
            _agent_trace("a3", 1, 3, "support"),
            _agent_trace("a4", 1, 4, "reject"),
            _agent_trace("a5", 1, 5, "reject"),
        ],
        final_decision="support",
        correctness=True,
    )
    assert false_consensus_rate([false_consensus, normal]) == 0.5


def test_false_consensus_rate_rejects_non_five_agent_runs() -> None:
    trace = _run_trace(
        [_agent_trace("a1", 1, 1, "support"), _agent_trace("a2", 1, 2, "support")],
        final_decision="support",
        correctness=True,
    )
    with pytest.raises(ValueError, match="5-agent"):
        false_consensus_rate([trace])


def test_counterfactual_agent_and_message_effects_use_comparisons() -> None:
    baseline = _run_trace([_agent_trace("a1", 1, 1, "support"), _agent_trace("a2", 1, 2, "reject")], final_decision="support", correctness=False)
    agent_intervention = _run_trace([_agent_trace("a1", 1, 1, "support"), _agent_trace("a2", 1, 2, "support")], final_decision="reject", correctness=True)
    message_intervention = _run_trace([_agent_trace("a1", 1, 1, "support"), _agent_trace("a2", 1, 2, "reject")], final_decision="support", correctness=False)

    comparisons = [
        _comparison(baseline, agent_intervention, "agent_removal", "a2"),
        _comparison(baseline, message_intervention, "message_removal", "r1_t1_a1"),
    ]

    assert counterfactual_agent_effect(comparisons) == 0.5
    assert counterfactual_message_effect(comparisons) == 0.5
    assert counterfactual_minority_recovery_rate(comparisons) == 0.5


def test_minority_recovery_rate_uses_initial_beliefs_and_ground_truth() -> None:
    recovered = _run_trace(
        [
            _agent_trace("a1", 1, 1, "support"),
            _agent_trace("a2", 1, 2, "reject"),
            _agent_trace("a3", 1, 3, "reject"),
            _agent_trace("a4", 1, 4, "reject"),
            _agent_trace("a5", 1, 5, "reject"),
        ],
        final_decision="support",
        correctness=True,
        ground_truth="support",
        initial_beliefs={
            "a1": _belief("support", 0.9),
            "a2": _belief("reject", 0.9),
            "a3": _belief("reject", 0.9),
            "a4": _belief("reject", 0.9),
            "a5": _belief("reject", 0.9),
        },
    )
    not_recovered = _run_trace(
        [
            _agent_trace("a1", 1, 1, "reject"),
            _agent_trace("a2", 1, 2, "reject"),
            _agent_trace("a3", 1, 3, "reject"),
            _agent_trace("a4", 1, 4, "reject"),
            _agent_trace("a5", 1, 5, "reject"),
        ],
        final_decision="reject",
        correctness=False,
        ground_truth="support",
        initial_beliefs={
            "a1": _belief("support", 0.9),
            "a2": _belief("reject", 0.9),
            "a3": _belief("reject", 0.9),
            "a4": _belief("reject", 0.9),
            "a5": _belief("reject", 0.9),
        },
    )
    assert minority_recovery_rate([recovered, not_recovered]) == 0.5


def test_gini_coefficient_is_deterministic_and_non_negative() -> None:
    assert gini_coefficient([0.0, 1.0]) == pytest.approx(0.5)
    assert gini_coefficient({"a": 0.0, "b": 1.0}) == pytest.approx(0.5)
    with pytest.raises(ValueError):
        gini_coefficient([-1.0, 0.0])


def test_aggregate_reports_summary_metrics() -> None:
    trace_a = _run_trace(
        [
            _agent_trace("a1", 1, 1, "support", confidence=0.2),
            _agent_trace("a2", 1, 2, "support", confidence=0.4),
            _agent_trace("a3", 1, 3, "support", confidence=0.4),
            _agent_trace("a4", 1, 4, "support", confidence=0.4),
            _agent_trace("a5", 1, 5, "support", confidence=0.4),
        ],
        final_decision="support",
        correctness=True,
        ground_truth="support",
        initial_beliefs={
            "a1": _belief("support", 0.1),
            "a2": _belief("reject", 0.1),
            "a3": _belief("reject", 0.1),
            "a4": _belief("reject", 0.1),
            "a5": _belief("reject", 0.1),
        },
    )
    trace_b = _run_trace(
        [
            _agent_trace("a1", 1, 1, "reject", confidence=0.9),
            _agent_trace("a2", 1, 2, "reject", confidence=0.8),
            _agent_trace("a3", 1, 3, "reject", confidence=0.8),
            _agent_trace("a4", 1, 4, "reject", confidence=0.8),
            _agent_trace("a5", 1, 5, "reject", confidence=0.8),
        ],
        final_decision="reject",
        correctness=False,
        initial_beliefs={
            "a1": _belief("support", 0.9),
            "a2": _belief("reject", 0.7),
            "a3": _belief("reject", 0.7),
            "a4": _belief("reject", 0.7),
            "a5": _belief("reject", 0.7),
        },
    )
    comparisons = [
        _comparison(trace_a, trace_b, "agent_removal", "a1"),
        _comparison(trace_a, trace_b, "message_removal", "r1_t1_a1"),
    ]

    aggregate = CounterfactualMetricAggregate.from_comparisons(comparisons, traces=[trace_a, trace_b])
    payload = aggregate.to_dict()

    assert payload["trace_count"] == 2
    assert payload["comparison_count"] == 2
    assert payload["consensus_accuracy_mean"] == pytest.approx(0.5)
    assert payload["counterfactual_agent_effect"] == pytest.approx(1.0)
    assert payload["counterfactual_message_effect"] == pytest.approx(1.0)
    assert payload["influence_concentration"] == pytest.approx(0.0)
    assert payload["minority_recovery_rate"] == pytest.approx(0.5)
