from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Any, Iterable, Sequence

from societyxai.interventions.branching import CounterfactualComparison
from societyxai.traces.schema import RunTrace


def consensus_accuracy(trace: RunTrace) -> float:
    """Return 1.0 when final consensus matches ground truth, else 0.0."""
    return 1.0 if trace.correctness is True else 0.0


def conformity_index(trace: RunTrace) -> float:
    """Return the share of belief flips that occur after majority exposure."""
    if not trace.agent_traces:
        return 0.0

    ordered = sorted(trace.agent_traces, key=lambda at: (at.round, at.turn_index))
    previous: dict[str, str] = {}
    total_flips = 0
    conformity_flips = 0

    for agent_trace in ordered:
        prior = previous.get(agent_trace.agent_id)
        if prior is not None and agent_trace.belief.position != prior:
            total_flips += 1
            if agent_trace.exposed_majority_position is not None:
                conformity_flips += 1
        previous[agent_trace.agent_id] = agent_trace.belief.position

    if total_flips == 0:
        return 0.0
    return conformity_flips / total_flips


def counterfactual_agent_effect(comparisons: Sequence[CounterfactualComparison]) -> float:
    """Fraction of agent-removal trials whose final consensus changes."""
    if not comparisons:
        return 0.0
    changed = sum(
        1
        for comparison in comparisons
        if comparison.baseline_trace.final_decision != comparison.intervention_trace.final_decision
    )
    return changed / len(comparisons)


def counterfactual_message_effect(comparisons: Sequence[CounterfactualComparison]) -> float:
    """Fraction of message-removal trials that change a downstream belief or decision."""
    if not comparisons:
        return 0.0
    changed = 0
    for comparison in comparisons:
        agent_ids = set(comparison.baseline_final_beliefs) | set(comparison.intervention_final_beliefs)
        belief_changed = any(comparison.belief_changed(agent_id) for agent_id in agent_ids)
        if belief_changed or comparison.decision_changed:
            changed += 1
    return changed / len(comparisons)


def false_consensus_rate(traces: Sequence[RunTrace]) -> float:
    """Return the fraction of 5-agent runs with >=4-of-5 agreement on an incorrect decision."""
    if not traces:
        return 0.0

    false_consensus = 0
    for trace in traces:
        final_positions = _final_positions(trace)
        if len(final_positions) != 5:
            raise ValueError("false_consensus_rate requires 5-agent runs")
        counts = _counts(final_positions)
        if counts and max(counts.values()) >= 4 and trace.correctness is False:
            false_consensus += 1
    return false_consensus / len(traces)


def minority_recovery_rate(traces: Sequence[RunTrace]) -> float:
    """Fraction of debates where a lone initially correct minority ends in a correct decision."""
    if not traces:
        return 0.0

    recovered = 0
    eligible = 0
    for trace in traces:
        if trace.ground_truth is None or not trace.initial_beliefs:
            continue
        correct_initial = sum(
            1
            for belief in trace.initial_beliefs.values()
            if belief.position.strip().lower() == trace.ground_truth.strip().lower()
        )
        if correct_initial != 1:
            continue
        if len(trace.initial_beliefs) != 5:
            raise ValueError("minority_recovery_rate requires 5-agent debates")
        eligible += 1
        if trace.correctness is True:
            recovered += 1

    if eligible == 0:
        return 0.0
    return recovered / eligible


def counterfactual_minority_recovery_rate(comparisons: Sequence[CounterfactualComparison]) -> float:
    """Fraction of controlled trials where the intervention corrects an incorrect baseline."""
    if not comparisons:
        return 0.0
    recovered = sum(
        1
        for comparison in comparisons
        if comparison.baseline_correctness is False and comparison.intervention_correctness is True
    )
    return recovered / len(comparisons)


def confidence_shift(trace: RunTrace) -> dict[str, float]:
    """Return per-agent final-minus-initial confidence deltas when initial beliefs exist."""
    if not trace.initial_beliefs:
        return {}

    final_beliefs = _final_beliefs(trace)
    deltas: dict[str, float] = {}
    for agent_id, initial in trace.initial_beliefs.items():
        final = final_beliefs.get(agent_id)
        if final is None:
            continue
        deltas[agent_id] = final.confidence - initial.confidence
    return deltas


def mean_confidence_shift(trace: RunTrace) -> float:
    """Return the mean final-minus-initial confidence delta across agents."""
    deltas = list(confidence_shift(trace).values())
    if not deltas:
        return 0.0
    return fmean(deltas)


def gini_coefficient(values: Sequence[float] | dict[str, float]) -> float:
    """Return the deterministic Gini coefficient for a non-negative value sequence."""
    data = list(values.values()) if isinstance(values, dict) else list(values)
    if not data:
        return 0.0
    if any(value < 0 for value in data):
        raise ValueError("gini_coefficient requires non-negative values")

    ordered = sorted(data)
    total = sum(ordered)
    if total == 0:
        return 0.0

    n = len(ordered)
    weighted = sum(index * value for index, value in enumerate(ordered, start=1))
    return (2 * weighted) / (n * total) - (n + 1) / n


@dataclass(frozen=True)
class CounterfactualMetricAggregate:
    """Typed aggregation of repeated traces and counterfactual comparisons."""

    traces: tuple[RunTrace, ...] = ()
    comparisons: tuple[CounterfactualComparison, ...] = ()

    @classmethod
    def from_traces(cls, traces: Iterable[RunTrace]) -> CounterfactualMetricAggregate:
        return cls(traces=tuple(traces))

    @classmethod
    def from_comparisons(
        cls,
        comparisons: Iterable[CounterfactualComparison],
        traces: Iterable[RunTrace] | None = None,
    ) -> CounterfactualMetricAggregate:
        return cls(traces=tuple(traces or ()), comparisons=tuple(comparisons))

    @property
    def consensus_accuracy_mean(self) -> float:
        if not self.traces:
            return 0.0
        return fmean(consensus_accuracy(trace) for trace in self.traces)

    @property
    def conformity_index_mean(self) -> float:
        if not self.traces:
            return 0.0
        return fmean(conformity_index(trace) for trace in self.traces)

    @property
    def false_consensus_rate(self) -> float:
        return false_consensus_rate(self.traces)

    @property
    def minority_recovery_rate(self) -> float:
        return minority_recovery_rate(self.traces)

    @property
    def counterfactual_agent_effect(self) -> float:
        return counterfactual_agent_effect(self.comparisons)

    @property
    def counterfactual_message_effect(self) -> float:
        return counterfactual_message_effect(self.comparisons)

    @property
    def influence_concentration(self) -> float:
        effects = self.agent_effect_sizes()
        return gini_coefficient(effects)

    @property
    def confidence_shift_mean(self) -> float:
        shifts: list[float] = []
        for trace in self.traces:
            shifts.extend(confidence_shift(trace).values())
        if not shifts:
            return 0.0
        return fmean(shifts)

    def agent_effect_sizes(self) -> dict[str, float]:
        """Return per-agent effect rates derived from agent-removal comparisons."""
        buckets: dict[str, list[float]] = {}
        for comparison in self.comparisons:
            intervention = comparison.intervention
            if intervention is None or intervention.intervention_type != "agent_removal" or intervention.target_id is None:
                continue
            buckets.setdefault(intervention.target_id, []).append(
                1.0 if comparison.decision_changed else 0.0
            )
        return {agent_id: fmean(values) for agent_id, values in buckets.items() if values}

    def message_effect_sizes(self) -> dict[str, float]:
        """Return per-message effect rates derived from message-removal comparisons."""
        buckets: dict[str, list[float]] = {}
        for comparison in self.comparisons:
            intervention = comparison.intervention
            if intervention is None or intervention.intervention_type != "message_removal" or intervention.target_id is None:
                continue
            buckets.setdefault(intervention.target_id, []).append(
                1.0 if counterfactual_message_effect((comparison,)) > 0 else 0.0
            )
        return {message_id: fmean(values) for message_id, values in buckets.items() if values}

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_count": len(self.traces),
            "comparison_count": len(self.comparisons),
            "consensus_accuracy_mean": self.consensus_accuracy_mean,
            "conformity_index_mean": self.conformity_index_mean,
            "false_consensus_rate": self.false_consensus_rate,
            "minority_recovery_rate": self.minority_recovery_rate,
            "counterfactual_agent_effect": self.counterfactual_agent_effect,
            "counterfactual_message_effect": self.counterfactual_message_effect,
            "influence_concentration": self.influence_concentration,
            "confidence_shift_mean": self.confidence_shift_mean,
        }


def _counts(values: Sequence[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _final_positions(trace: RunTrace) -> list[str]:
    last_by_agent: dict[str, str] = {}
    for at in trace.agent_traces:
        last_by_agent[at.agent_id] = at.belief.position
    return list(last_by_agent.values())


def _final_beliefs(trace: RunTrace) -> dict[str, Any]:
    last_by_agent: dict[str, Any] = {}
    for at in trace.agent_traces:
        last_by_agent[at.agent_id] = at.belief
    return last_by_agent
