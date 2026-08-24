"""Focused tests for Phase 5B: core research metrics.

Covers: consensus_score, belief_divergence, convergence_round, edge cases,
trace immutability, and baseline/intervention consistency.
"""
from __future__ import annotations

from datetime import datetime, timezone

from societyxai.config.schema import TopologyConfig
from societyxai.traces.schema import AgentTrace, BeliefState, RunTrace
from societyxai.utils.metrics import belief_divergence, consensus_score, convergence_round


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _belief(position: str, confidence: float = 1.0) -> BeliefState:
    return BeliefState(position=position, confidence=confidence, evidence_ids=[], reasoning_trace="")


def _trace(agent_traces: list[AgentTrace], **kw) -> RunTrace:
    """Build a minimal RunTrace with the given agent_traces."""
    defaults = dict(
        run_id="r1", task_id="t1", seed=0,
        timestamp=datetime.now(timezone.utc),
        model_id="m", provider="p", temperature=0.0,
        topology=TopologyConfig(kind="complete"),
    )
    defaults.update(kw)
    return RunTrace(agent_traces=agent_traces, **defaults)


def _at(agent_id: str, round_: int, position: str) -> AgentTrace:
    return AgentTrace(
        agent_id=agent_id, role="speaker", round=round_, turn_index=1,
        belief=_belief(position),
    )


# ======================================================================
# 1. Consensus score — complete consensus
# ======================================================================


def test_consensus_score_all_agree():
    """All agents hold the same position -> score is 1.0."""
    trace = _trace([
        _at("a1", 2, "support"),
        _at("a2", 2, "support"),
        _at("a3", 2, "support"),
    ])
    assert consensus_score(trace) == 1.0


# ======================================================================
# 2. Consensus score — split 2-vs-2
# ======================================================================


def test_consensus_score_split_2v2():
    """Two agents support, two reject -> score = 1 - (2-1)/(4-1) = 2/3."""
    trace = _trace([
        _at("a1", 2, "support"),
        _at("a2", 2, "support"),
        _at("a3", 2, "reject"),
        _at("a4", 2, "reject"),
    ])
    score = consensus_score(trace)
    assert score == pytest.approx(2.0 / 3.0)


# ======================================================================
# 3. Consensus score — all different
# ======================================================================


def test_consensus_score_all_different():
    """Each agent has a unique position -> score is 0.0."""
    trace = _trace([
        _at("a1", 1, "support"),
        _at("a2", 1, "reject"),
        _at("a3", 1, "neutral"),
    ])
    assert consensus_score(trace) == 0.0


# ======================================================================
# 4. Consensus score — single agent
# ======================================================================


def test_consensus_score_single_agent():
    """One agent -> score is 1.0 by convention."""
    trace = _trace([_at("a1", 1, "support")])
    assert consensus_score(trace) == 1.0


# ======================================================================
# 5. Consensus score — empty trace
# ======================================================================


def test_consensus_score_empty():
    """No agent traces -> score is 1.0."""
    trace = _trace([])
    assert consensus_score(trace) == 1.0


# ======================================================================
# 6. Belief divergence — all agree
# ======================================================================


def test_divergence_all_agree():
    """All agents agree -> divergence is 0.0."""
    trace = _trace([
        _at("a1", 2, "support"),
        _at("a2", 2, "support"),
    ])
    assert belief_divergence(trace) == 0.0


# ======================================================================
# 7. Belief divergence — all different
# ======================================================================


def test_divergence_all_different():
    """Three agents with distinct positions -> every pair disagrees -> 1.0."""
    trace = _trace([
        _at("a1", 1, "support"),
        _at("a2", 1, "reject"),
        _at("a3", 1, "neutral"),
    ])
    assert belief_divergence(trace) == 1.0


# ======================================================================
# 8. Belief divergence — split 2v2
# ======================================================================


def test_divergence_split_2v2():
    """2 support, 2 reject -> 4 disagreeing pairs out of 6 total -> 2/3."""
    trace = _trace([
        _at("a1", 1, "support"),
        _at("a2", 1, "support"),
        _at("a3", 1, "reject"),
        _at("a4", 1, "reject"),
    ])
    assert belief_divergence(trace) == pytest.approx(4.0 / 6.0)


# ======================================================================
# 9. Belief divergence — single agent
# ======================================================================


def test_divergence_single_agent():
    """One agent -> no pairs -> divergence is 0.0."""
    trace = _trace([_at("a1", 1, "support")])
    assert belief_divergence(trace) == 0.0


# ======================================================================
# 10. Belief divergence — empty trace
# ======================================================================


def test_divergence_empty():
    """No agent traces -> divergence is 0.0."""
    trace = _trace([])
    assert belief_divergence(trace) == 0.0


# ======================================================================
# 11. Convergence round — round 1
# ======================================================================


def test_convergence_round_1():
    """All agents agree from the start -> converges in round 1."""
    trace = _trace([
        _at("a1", 1, "support"),
        _at("a2", 1, "support"),
    ])
    assert convergence_round(trace) == 1


# ======================================================================
# 12. Convergence round — after multiple rounds
# ======================================================================


def test_convergence_round_later():
    """Disagree in round 1, agree in round 2 -> converges in round 2."""
    trace = _trace([
        _at("a1", 1, "support"),
        _at("a2", 1, "reject"),
        _at("a1", 2, "support"),
        _at("a2", 2, "support"),
    ])
    assert convergence_round(trace) == 2


# ======================================================================
# 13. Convergence round — never converges
# ======================================================================


def test_convergence_round_never():
    """Agents never agree -> returns -1."""
    trace = _trace([
        _at("a1", 1, "support"),
        _at("a2", 1, "reject"),
        _at("a1", 2, "support"),
        _at("a2", 2, "reject"),
    ])
    assert convergence_round(trace) == -1


# ======================================================================
# 14. Convergence round — empty trace
# ======================================================================


def test_convergence_round_empty():
    """No agent traces -> returns -1."""
    trace = _trace([])
    assert convergence_round(trace) == -1


# ======================================================================
# 15. Convergence round — single agent always converges
# ======================================================================


def test_convergence_round_single_agent():
    """Single agent always agrees with itself -> round 1."""
    trace = _trace([_at("a1", 1, "support")])
    assert convergence_round(trace) == 1


# ======================================================================
# 16. Metrics do not mutate traces
# ======================================================================


def test_metrics_do_not_mutate_trace():
    """Calling metrics never modifies the input trace."""
    traces = [
        _at("a1", 1, "support"),
        _at("a2", 1, "reject"),
    ]
    trace = _trace(list(traces))
    original_count = len(trace.agent_traces)
    original_positions = [
        at.belief.position for at in trace.agent_traces
    ]

    consensus_score(trace)
    belief_divergence(trace)
    convergence_round(trace)

    assert len(trace.agent_traces) == original_count
    assert [
        at.belief.position for at in trace.agent_traces
    ] == original_positions


# ======================================================================
# 17. Consistency: baseline and intervention traces
# ======================================================================


def test_consistency_baseline_intervention():
    """Two identical traces produce the same metric values."""
    def _make_trace():
        return _trace([
            _at("a1", 2, "support"),
            _at("a2", 2, "reject"),
        ])

    base = _make_trace()
    interv = _make_trace()

    assert consensus_score(base) == consensus_score(interv)
    assert belief_divergence(base) == belief_divergence(interv)
    assert convergence_round(base) == convergence_round(interv)


# ======================================================================
# 18. Consensus score with multiple rounds (final positions used)
# ======================================================================


def test_consensus_uses_final_round_positions():
    """consensus_score uses the last round for each agent, not the first."""
    trace = _trace([
        _at("a1", 1, "support"),
        _at("a2", 1, "support"),
        _at("a1", 2, "support"),
        _at("a2", 2, "reject"),  # a2 changed in round 2
    ])
    # Final: a1=support, a2=reject -> 2 distinct, 2 agents -> 0.0
    assert consensus_score(trace) == 0.0


# ======================================================================
# 19. Belief divergence with multiple rounds
# ======================================================================


def test_divergence_uses_final_round_positions():
    """belief_divergence uses the last round for each agent."""
    trace = _trace([
        _at("a1", 1, "support"),
        _at("a2", 1, "reject"),
        _at("a1", 2, "reject"),
        _at("a2", 2, "reject"),  # both converged to reject
    ])
    assert belief_divergence(trace) == 0.0


# ======================================================================
# 20. Convergence round picks earliest
# ======================================================================


def test_convergence_round_picks_earliest():
    """If convergence happens in round 1, later rounds don't matter."""
    trace = _trace([
        _at("a1", 1, "support"),
        _at("a2", 1, "support"),
        _at("a1", 2, "reject"),
        _at("a2", 2, "reject"),
    ])
    assert convergence_round(trace) == 1


# ======================================================================
# 21. Consensus score — mixed three positions, four agents
# ======================================================================


def test_consensus_mixed_three_positions():
    """2 support, 1 reject, 1 neutral -> 3 distinct / 4 agents -> 1 - 2/3 = 1/3."""
    trace = _trace([
        _at("a1", 1, "support"),
        _at("a2", 1, "support"),
        _at("a3", 1, "reject"),
        _at("a4", 1, "neutral"),
    ])
    assert consensus_score(trace) == pytest.approx(1.0 / 3.0)


# ======================================================================
# 22. Belief divergence — two agents agree, one differs
# ======================================================================


def test_divergence_two_agree_one_differs():
    """2 support, 1 reject -> 2 disagreeing pairs out of 3 total -> 2/3."""
    trace = _trace([
        _at("a1", 1, "support"),
        _at("a2", 1, "support"),
        _at("a3", 1, "reject"),
    ])
    assert belief_divergence(trace) == pytest.approx(2.0 / 3.0)


# ======================================================================
# 23. Convergence with three agents over three rounds
# ======================================================================


def test_convergence_three_agents_three_rounds():
    """Round 1: mixed. Round 2: still mixed. Round 3: all agree."""
    trace = _trace([
        _at("a1", 1, "support"),
        _at("a2", 1, "reject"),
        _at("a3", 1, "neutral"),
        _at("a1", 2, "support"),
        _at("a2", 2, "support"),
        _at("a3", 2, "reject"),
        _at("a1", 3, "neutral"),
        _at("a2", 3, "neutral"),
        _at("a3", 3, "neutral"),
    ])
    assert convergence_round(trace) == 3


# ======================================================================
# 24. Metrics on real orchestrator trace (integration-style)
# ======================================================================


def test_metrics_on_orchestrator_trace():
    """Metrics work on a real RunTrace produced by Orchestrator."""
    from societyxai.config.schema import SpeakerOrderConfig, VisibilityConfig
    from societyxai.core import Agent, Orchestrator, Society
    from societyxai.models import ModelBackend, ModelResponse
    from societyxai.tasks import Task

    class Backend(ModelBackend):
        def generate(self, messages, temperature=None, max_tokens=None, seed=None):
            return ModelResponse(text="I approve.")

    agents = [Agent(agent_id="a1", role="s", model_id="m", system_prompt="s"),
              Agent(agent_id="a2", role="s", model_id="m", system_prompt="s")]
    society = Society(
        agents=agents,
        topology=TopologyConfig(kind="complete"),
        number_of_rounds=2,
        speaker_order=SpeakerOrderConfig(order=["a1", "a2"], deterministic=True),
        visibility=VisibilityConfig(),
    )
    task = Task(task_id="t1", question="Q?", ground_truth="A")
    result = Orchestrator(society=society, task=task, backend=Backend("m", "p")).run()

    assert result.trace is not None
    assert consensus_score(result.trace) == 1.0
    assert belief_divergence(result.trace) == 0.0
    assert convergence_round(result.trace) == 1


# ======================================================================
# Import check
# ======================================================================


def test_metrics_importable_from_utils():
    """Metrics are importable from societyxai.utils."""
    from societyxai.utils import belief_divergence as bd
    from societyxai.utils import consensus_score as cs
    from societyxai.utils import convergence_round as cr
    assert callable(cs)
    assert callable(bd)
    assert callable(cr)


import pytest
