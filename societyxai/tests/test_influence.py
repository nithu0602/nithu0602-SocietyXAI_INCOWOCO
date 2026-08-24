"""Focused tests for Phase 6A: deterministic influence tracking.

Covers: direct influence, no-influence cases, belief-change condition,
first-belief adoption, multi-message/multi-round, multiple sources,
determinism, empty trace, immutability, and export check.
"""
from __future__ import annotations

from datetime import datetime, timezone

from societyxai.config.schema import TopologyConfig
from societyxai.traces.schema import AgentTrace, BeliefState, MessageTrace, RunTrace
from societyxai.utils.influence import influence_matrix


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _belief(position: str, confidence: float = 1.0) -> BeliefState:
    return BeliefState(position=position, confidence=confidence, evidence_ids=[], reasoning_trace="")


def _msg(message_id: str, agent_id: str, round_: int, turn_index: int) -> MessageTrace:
    return MessageTrace(
        message_id=message_id, agent_id=agent_id,
        round=round_, turn_index=turn_index, content=f"content of {message_id}",
    )


def _at(agent_id: str, round_: int, turn_index: int, position: str,
        received: list[str] | None = None) -> AgentTrace:
    return AgentTrace(
        agent_id=agent_id, role="speaker", round=round_, turn_index=turn_index,
        belief=_belief(position),
        received_message_ids=received or [],
    )


def _trace(agent_traces: list[AgentTrace], message_traces: list[MessageTrace] | None = None,
           **kw) -> RunTrace:
    defaults = dict(
        run_id="r1", task_id="t1", seed=0,
        timestamp=datetime.now(timezone.utc),
        model_id="m", provider="p", temperature=0.0,
        topology=TopologyConfig(kind="complete"),
    )
    defaults.update(kw)
    return RunTrace(
        agent_traces=agent_traces,
        message_traces=message_traces or [],
        **defaults,
    )


# ======================================================================
# 1. Direct influence through a visible message
# ======================================================================


def test_direct_influence_visible_message():
    """A's message is visible to B and B's belief changes -> influence recorded."""
    # R1: a1 speaks (turn 1), a2 speaks (turn 2)
    # a1 sees nothing (first turn), a2 sees a1's message
    # a2's belief changes from None to 'support' -> a1 influenced a2
    at_a1 = _at("a1", 1, 1, "support", received=[])
    at_a2 = _at("a2", 1, 2, "support", received=["r1_t1_a1"])
    msg_a1 = _msg("r1_t1_a1", "a1", 1, 1)
    msg_a2 = _msg("r1_t2_a2", "a2", 1, 2)

    trace = _trace([at_a1, at_a2], [msg_a1, msg_a2])
    im = influence_matrix(trace)
    assert im == {"a1": {"a2": 1}}


# ======================================================================
# 2. No influence when no message was visible
# ======================================================================


def test_no_influence_no_visible_message():
    """B receives no messages -> no influence from anyone."""
    at_a1 = _at("a1", 1, 1, "support", received=[])
    at_a2 = _at("a2", 1, 2, "reject", received=[])
    msg_a1 = _msg("r1_t1_a1", "a1", 1, 1)

    trace = _trace([at_a1, at_a2], [msg_a1])
    im = influence_matrix(trace)
    assert im == {}


# ======================================================================
# 3. Unchanged belief produces no influence
# ======================================================================


def test_no_influence_unchanged_belief():
    """B receives A's message but belief position is the same -> no influence."""
    # R1: a1=support, a2=support (a2 saw a1 but didn't change)
    # R2: a2 still sees a1's messages, still support -> no new influence
    at_a1_r1 = _at("a1", 1, 1, "support", received=[])
    at_a2_r1 = _at("a2", 1, 2, "support", received=["r1_t1_a1"])
    at_a1_r2 = _at("a1", 2, 1, "support", received=["r1_t1_a1", "r1_t2_a2"])
    at_a2_r2 = _at("a2", 2, 2, "support", received=["r1_t1_a1", "r1_t2_a2", "r2_t1_a1"])
    msg_a1_r1 = _msg("r1_t1_a1", "a1", 1, 1)
    msg_a2_r1 = _msg("r1_t2_a2", "a2", 1, 2)
    msg_a1_r2 = _msg("r2_t1_a1", "a1", 2, 1)

    trace = _trace(
        [at_a1_r1, at_a2_r1, at_a1_r2, at_a2_r2],
        [msg_a1_r1, msg_a2_r1, msg_a1_r2],
    )
    im = influence_matrix(trace)
    # a1 influenced a2 in R1T2 (first belief for a2), but NOT in R2T2 (same position)
    assert im == {"a1": {"a2": 1}}


# ======================================================================
# 4. First-belief adoption counts as influence
# ======================================================================


def test_first_belief_adoption_counts():
    """B had no previous belief and adopts a position after seeing A's message."""
    at_a1 = _at("a1", 1, 1, "reject", received=[])
    at_a2 = _at("a2", 1, 2, "reject", received=["r1_t1_a1"])
    msg = _msg("r1_t1_a1", "a1", 1, 1)

    trace = _trace([at_a1, at_a2], [msg])
    im = influence_matrix(trace)
    # a2 had no previous belief, sees a1's message, adopts 'reject' -> a1 influenced a2
    assert im == {"a1": {"a2": 1}}


# ======================================================================
# 5. Multiple messages / multiple rounds
# ======================================================================


def test_multiple_messages_multiple_rounds():
    """Influence accumulates across rounds when belief changes each time."""
    # R1: a1=support (no prev), a2 sees a1 -> a2 first belief -> influence
    # R2: a1 changes to reject, a2 sees a1 -> a2 changes to reject -> influence
    at_a1_r1 = _at("a1", 1, 1, "support", received=[])
    at_a2_r1 = _at("a2", 1, 2, "support", received=["r1_t1_a1"])
    at_a1_r2 = _at("a1", 2, 1, "reject", received=["r1_t1_a1", "r1_t2_a2"])
    at_a2_r2 = _at("a2", 2, 2, "reject", received=["r1_t1_a1", "r1_t2_a2", "r2_t1_a1"])
    msgs = [
        _msg("r1_t1_a1", "a1", 1, 1),
        _msg("r1_t2_a2", "a2", 1, 2),
        _msg("r2_t1_a1", "a1", 2, 1),
    ]

    trace = _trace([at_a1_r1, at_a2_r1, at_a1_r2, at_a2_r2], msgs)
    im = influence_matrix(trace)
    # a1 influenced a2 in R1T2 (first belief) and R2T2 (belief changed) = 2
    # a2 influenced a1 in R2T1 (a1's belief changed and a2's message was visible) = 1
    assert im["a1"]["a2"] == 2
    assert im["a2"]["a1"] == 1


# ======================================================================
# 6. Multiple sources influencing one target
# ======================================================================


def test_multiple_sources_influence_one_target():
    """Two different agents' messages are visible and target changes belief."""
    # R1: a1 speaks, a2 speaks, a3 speaks (sees a1 + a2)
    # a3's first belief -> both a1 and a2 influenced a3
    at_a1 = _at("a1", 1, 1, "support", received=[])
    at_a2 = _at("a2", 1, 2, "reject", received=["r1_t1_a1"])
    at_a3 = _at("a3", 1, 3, "support", received=["r1_t1_a1", "r1_t2_a2"])
    msgs = [
        _msg("r1_t1_a1", "a1", 1, 1),
        _msg("r1_t2_a2", "a2", 1, 2),
    ]

    trace = _trace([at_a1, at_a2, at_a3], msgs)
    im = influence_matrix(trace)
    assert im["a1"]["a3"] == 1
    assert im["a2"]["a3"] == 1


# ======================================================================
# 7. Deterministic repeated calculation
# ======================================================================


def test_deterministic_repeated_calculation():
    """Calling influence_matrix twice on the same trace yields identical results."""
    at_a1 = _at("a1", 1, 1, "support", received=[])
    at_a2 = _at("a2", 1, 2, "reject", received=["r1_t1_a1"])
    msgs = [_msg("r1_t1_a1", "a1", 1, 1)]
    trace = _trace([at_a1, at_a2], msgs)

    im1 = influence_matrix(trace)
    im2 = influence_matrix(trace)
    assert im1 == im2


# ======================================================================
# 8. Empty trace
# ======================================================================


def test_empty_trace():
    """Empty agent_traces -> empty influence matrix."""
    trace = _trace([], [])
    im = influence_matrix(trace)
    assert im == {}


# ======================================================================
# 9. Metrics do not mutate the trace
# ======================================================================


def test_influence_does_not_mutate_trace():
    """Calling influence_matrix never modifies the input trace."""
    at_a1 = _at("a1", 1, 1, "support", received=[])
    at_a2 = _at("a2", 1, 2, "reject", received=["r1_t1_a1"])
    msgs = [_msg("r1_t1_a1", "a1", 1, 1)]
    trace = _trace([at_a1, at_a2], msgs)

    original_agent_count = len(trace.agent_traces)
    original_msg_count = len(trace.message_traces)
    original_positions = [a.belief.position for a in trace.agent_traces]
    original_received = [list(a.received_message_ids) for a in trace.agent_traces]

    influence_matrix(trace)

    assert len(trace.agent_traces) == original_agent_count
    assert len(trace.message_traces) == original_msg_count
    assert [a.belief.position for a in trace.agent_traces] == original_positions
    assert [list(a.received_message_ids) for a in trace.agent_traces] == original_received


# ======================================================================
# 10. Export from societyxai.utils
# ======================================================================


def test_export_from_utils():
    """influence_matrix is importable from societyxai.utils."""
    from societyxai.utils import influence_matrix as im
    assert callable(im)


# ======================================================================
# 11. Source agent's own messages don't count as influence
# ======================================================================


def test_own_message_not_influence():
    """An agent seeing its own previous message should not count as self-influence."""
    # R1: a1 speaks, a2 speaks
    # R2: a1 sees its own R1 message + a2's R1 message, belief changes
    at_a1_r1 = _at("a1", 1, 1, "support", received=[])
    at_a2_r1 = _at("a2", 1, 2, "reject", received=["r1_t1_a1"])
    at_a1_r2 = _at("a1", 2, 1, "reject", received=["r1_t1_a1", "r1_t2_a2"])
    msgs = [
        _msg("r1_t1_a1", "a1", 1, 1),
        _msg("r1_t2_a2", "a2", 1, 2),
    ]
    trace = _trace([at_a1_r1, at_a2_r1, at_a1_r2], msgs)
    im = influence_matrix(trace)
    # a1's own message r1_t1_a1 should NOT count as a1 influencing a1
    assert im.get("a1", {}).get("a1", 0) == 0
    # Only a2 influenced a1 (a2's message visible + belief changed)
    assert im["a2"]["a1"] == 1


# ======================================================================
# 12. Belief changes back and forth counts each time
# ======================================================================


def test_belief_fluctuation_counts_each_change():
    """Each time the target's belief changes, each visible source is counted."""
    # R1: a1 speaks (support), a2 sees a1 -> first belief -> influence
    # R2: a1 speaks (reject), a2 sees a1 -> changes to reject -> influence
    # R3: a1 speaks (support), a2 sees a1 -> changes to support -> influence
    at_a1_r1 = _at("a1", 1, 1, "support", received=[])
    at_a2_r1 = _at("a2", 1, 2, "support", received=["r1_t1_a1"])
    at_a1_r2 = _at("a1", 2, 1, "reject", received=[])
    at_a2_r2 = _at("a2", 2, 2, "reject", received=["r1_t1_a1", "r1_t2_a2", "r2_t1_a1"])
    at_a1_r3 = _at("a1", 3, 1, "support", received=[])
    at_a2_r3 = _at("a2", 3, 2, "support", received=["r2_t1_a1", "r2_t2_a2", "r3_t1_a1"])
    msgs = [
        _msg("r1_t1_a1", "a1", 1, 1),
        _msg("r1_t2_a2", "a2", 1, 2),
        _msg("r2_t1_a1", "a1", 2, 1),
        _msg("r2_t2_a2", "a2", 2, 2),
        _msg("r3_t1_a1", "a1", 3, 1),
    ]
    trace = _trace([at_a1_r1, at_a2_r1, at_a1_r2, at_a2_r2, at_a1_r3, at_a2_r3], msgs)
    im = influence_matrix(trace)
    # a1 influenced a2 in R1T2, R2T2, R3T2 = 3 times
    # a1's received=[] in R2/R3 so a2 never influences a1
    assert im["a1"]["a2"] == 3
    assert "a2" not in im


# ======================================================================
# 13. Received message ID not in message_traces -> ignored
# ======================================================================


def test_unknown_message_id_ignored():
    """A received_message_id with no matching MessageTrace is silently ignored."""
    at_a1 = _at("a1", 1, 1, "support", received=[])
    at_a2 = _at("a2", 1, 2, "reject", received=["nonexistent_msg"])
    trace = _trace([at_a1, at_a2], [])
    im = influence_matrix(trace)
    assert im == {}


# ======================================================================
# 14. Full orchestrator integration
# ======================================================================


def test_influence_on_orchestrator_trace():
    """influence_matrix works on a real RunTrace produced by Orchestrator."""
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
    im = influence_matrix(result.trace)
    # Both agents always say "approve" -> support.  a2's first turn sees a1's
    # message and adopts 'support' for the first time -> a1 influenced a2.
    # In R2 a2's belief is still 'support' (no change) -> no further influence.
    assert im.get("a1", {}).get("a2", 0) == 1
