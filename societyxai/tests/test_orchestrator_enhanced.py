"""Focused tests for enhanced Orchestrator.run() capabilities.

Covers: topology-aware message visibility, evidence visibility,
belief updates / history, received_message_ids, and backward-compatible
ExecutionResult behaviour.
"""
from __future__ import annotations

from societyxai.config.schema import SpeakerOrderConfig, TopologyConfig, VisibilityConfig
from societyxai.core import Agent, Orchestrator, Society
from societyxai.models import ModelBackend, ModelResponse
from societyxai.tasks import Task


class RecordingBackend(ModelBackend):
    """Backend that records every message list passed to generate()."""

    def __init__(self, model_id: str = "m", provider: str = "p"):
        super().__init__(model_id=model_id, provider=provider)
        self.calls: list[list[dict]] = []

    def generate(self, messages, temperature=None, max_tokens=None, seed=None):
        self.calls.append(list(messages))
        return ModelResponse(text="ok")


def _agent(agent_id: str) -> Agent:
    return Agent(agent_id=agent_id, role="speaker", model_id="m", system_prompt="sys")


def _task(**kw):
    defaults = dict(task_id="t1", question="Q?", ground_truth="A")
    defaults.update(kw)
    return Task(**defaults)


def _society(agents, topology, rounds, order, vis, adj=None):
    kwargs = {"kind": topology}
    if adj is not None:
        kwargs["adjacency"] = adj
    t = TopologyConfig(**kwargs)
    return Society(
        agents=agents, topology=t, number_of_rounds=rounds,
        speaker_order=SpeakerOrderConfig(order=order, deterministic=True),
        visibility=vis,
    )


def _run(society, task, backend=None):
    if backend is None:
        backend = RecordingBackend("m", "p")
    return Orchestrator(society=society, task=task, backend=backend).run()


def _conv_text(call: list[dict]) -> str:
    """Extract the conversation message content from a backend call, or ''."""
    for msg in call:
        if msg["role"] == "user" and msg["content"].startswith("Previous messages:"):
            return msg["content"]
    return ""


def _evidence_text(call: list[dict]) -> str:
    """Extract the evidence message content from a backend call, or ''."""
    for msg in call:
        if msg["role"] == "user" and msg["content"].startswith("Evidence:"):
            return msg["content"]
    return ""


def _has_evidence(call: list[dict]) -> bool:
    return any(msg["content"].startswith("Evidence:") for msg in call if msg["role"] == "user")


def _has_conv(call: list[dict]) -> bool:
    return any(msg["content"].startswith("Previous messages:") for msg in call if msg["role"] == "user")


# ======================================================================
# 1. Topology-aware message visibility
# ======================================================================


def test_ring_adjacency_restricts_first_round():
    """Ring adjacency [[1,2],[0,2],[0,1]]: a2 sees a1; a3 sees a1+a2; a1 sees nobody."""
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, "ring", 1, ["a1", "a2", "a3"],
                 VisibilityConfig(previous_messages=True),
                 adj=[[1, 2], [0, 2], [0, 1]])
    be = RecordingBackend()
    _run(s, _task(), backend=be)

    # a1: no visible messages
    assert not _has_conv(be.calls[0])
    # a2: sees a1's message
    assert "a1:" in _conv_text(be.calls[1])
    assert "a2:" not in _conv_text(be.calls[1])
    # a3: sees a1 and a2 messages
    assert "a1:" in _conv_text(be.calls[2])
    assert "a2:" in _conv_text(be.calls[2])


def test_complete_topology_everyone_sees_all():
    """Complete topology: every agent sees every prior message."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, "complete", 2, ["a1", "a2"],
                 VisibilityConfig(previous_messages=True))
    be = RecordingBackend()
    _run(s, _task(), backend=be)

    # R1T1 a1: no prior messages
    assert not _has_conv(be.calls[0])
    # R1T2 a2: sees a1's r1 message
    assert "a1:" in _conv_text(be.calls[1])
    # R2T1 a1: sees a1(r1) + a2(r1)
    conv2 = _conv_text(be.calls[2])
    assert "a1:" in conv2
    assert "a2:" in conv2
    # R2T2 a2: sees a1(r1) + a2(r1) + a1(r2)
    conv3 = _conv_text(be.calls[3])
    assert conv3.count("a1:") == 2
    assert "a2:" in conv3


def test_no_previous_messages_hides_conversation():
    """When previous_messages=False, no conversation appears regardless of topology."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, "complete", 2, ["a1", "a2"],
                 VisibilityConfig(previous_messages=False))
    be = RecordingBackend()
    _run(s, _task(), backend=be)

    for call in be.calls:
        assert not _has_conv(call)


def test_line_topology_adjacency():
    """Line adjacency [[1],[0,2],[1]]: a1 sees nobody; a2 sees a1; a3 sees a2."""
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, "line", 1, ["a1", "a2", "a3"],
                 VisibilityConfig(previous_messages=True),
                 adj=[[1], [0, 2], [1]])
    be = RecordingBackend()
    _run(s, _task(), backend=be)

    # a1: no visible
    assert not _has_conv(be.calls[0])
    # a2: sees a1
    assert "a1:" in _conv_text(be.calls[1])
    # a3: sees a2 (not a1)
    conv3 = _conv_text(be.calls[2])
    assert "a2:" in conv3
    assert "a1:" not in conv3


def test_custom_topology_uses_adjacency():
    """Custom adjacency [[1],[0],[0,1]]: a1 sees a2; a2 sees a1; a3 sees a1+a2."""
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, "custom", 1, ["a1", "a2", "a3"],
                 VisibilityConfig(previous_messages=True),
                 adj=[[1], [0], [0, 1]])
    be = RecordingBackend()
    _run(s, _task(), backend=be)

    # a1: no visible
    assert not _has_conv(be.calls[0])
    # a2: sees a1
    assert "a1:" in _conv_text(be.calls[1])
    # a3: sees a1 + a2
    assert "a1:" in _conv_text(be.calls[2])
    assert "a2:" in _conv_text(be.calls[2])


def test_second_round_accumulates_messages():
    """In round 2 with complete topology, agents see all round 1 messages."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, "complete", 2, ["a1", "a2"],
                 VisibilityConfig(previous_messages=True))
    be = RecordingBackend()
    _run(s, _task(), backend=be)

    # R2T1 a1: sees both R1 messages
    conv = _conv_text(be.calls[2])
    assert conv.count(":") >= 2  # at least 2 agent lines


# ======================================================================
# 2. Evidence visibility
# ======================================================================


def test_evidence_included_when_present():
    """Task with evidence -> evidence section appears in prompt."""
    ev = [{"evidence_id": "e1", "content": "Fact A."},
          {"evidence_id": "e2", "content": "Fact B.", "source": "rpt"}]
    s = _society([_agent("a1")], "ring", 1, ["a1"],
                 VisibilityConfig())
    be = RecordingBackend()
    _run(s, _task(evidence=ev), backend=be)
    assert _has_evidence(be.calls[0])
    ev_text = _evidence_text(be.calls[0])
    assert "Fact A." in ev_text
    assert "Fact B." in ev_text
    assert "rpt" in ev_text


def test_no_evidence_no_section():
    """Task without evidence -> no evidence section."""
    s = _society([_agent("a1")], "ring", 1, ["a1"],
                 VisibilityConfig())
    be = RecordingBackend()
    _run(s, _task(), backend=be)
    assert not _has_evidence(be.calls[0])


def test_evidence_shown_even_when_previous_messages_false():
    """Evidence is included even when previous_messages=False."""
    ev = [{"evidence_id": "e1", "content": "Fact."}]
    s = _society([_agent("a1")], "ring", 1, ["a1"],
                 VisibilityConfig(previous_messages=False))
    be = RecordingBackend()
    _run(s, _task(evidence=ev), backend=be)
    assert _has_evidence(be.calls[0])
    assert not _has_conv(be.calls[0])


def test_evidence_and_conversation_together():
    """Both evidence and visible messages appear in the prompt."""
    ev = [{"evidence_id": "e1", "content": "Fact."}]
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, "complete", 1, ["a1", "a2"],
                 VisibilityConfig(previous_messages=True))
    be = RecordingBackend()
    _run(s, _task(evidence=ev), backend=be)
    # a2's call should have both conversation and evidence
    assert _has_conv(be.calls[1])
    assert _has_evidence(be.calls[1])


# ======================================================================
# 3. Belief updates / history
# ======================================================================


def test_current_belief_set_after_execution():
    agents = [_agent("a1")]
    s = _society(agents, "ring", 1, ["a1"], VisibilityConfig())
    _run(s, _task())
    assert agents[0].current_belief is not None
    assert agents[0].current_belief.position in ("support", "reject", "neutral")
    assert agents[0].current_belief.confidence == 1.0


def test_belief_history_grows_with_rounds():
    agents = [_agent("a1")]
    s = _society(agents, "ring", 3, ["a1"], VisibilityConfig())
    _run(s, _task())
    assert len(agents[0].belief_history) == 3


def test_belief_history_for_multiple_agents():
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, "ring", 2, ["a1", "a2"], VisibilityConfig())
    _run(s, _task())
    assert len(agents[0].belief_history) == 2
    assert len(agents[1].belief_history) == 2


def test_agents_start_with_no_belief():
    agent = _agent("a1")
    assert agent.current_belief is None
    assert agent.belief_history == []


def test_belief_history_entries_are_distinct():
    agents = [_agent("a1")]
    s = _society(agents, "ring", 3, ["a1"], VisibilityConfig())
    _run(s, _task())
    for b in agents[0].belief_history:
        assert b.position in ("support", "reject", "neutral")


# ======================================================================
# 4. received_message_ids
# ======================================================================


def test_received_ids_populated_with_topology():
    """With complete topology, agents see messages from all prior speakers."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, "complete", 2, ["a1", "a2"],
                 VisibilityConfig(previous_messages=True))
    _run(s, _task())
    # a1 spoke first in R1, then both spoke in R1
    # In R2: a1 sees r1 messages from a1 and a2
    assert len(agents[0].received_message_ids) > 0
    # a2 saw a1(r1) in R1, then sees r1+r2 in R2
    assert len(agents[1].received_message_ids) > len(agents[0].received_message_ids)


def test_received_ids_empty_when_previous_messages_false():
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, "complete", 2, ["a1", "a2"],
                 VisibilityConfig(previous_messages=False))
    _run(s, _task())
    for a in agents:
        assert a.received_message_ids == []


def test_received_ids_unique_message_format():
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, "complete", 1, ["a1", "a2"],
                 VisibilityConfig(previous_messages=True))
    _run(s, _task())
    for mid in agents[1].received_message_ids:
        assert mid.startswith("r")
        assert "_t" in mid
        assert "_a" in mid


def test_received_ids_match_topology_restriction():
    """With line topology, a3 should only see a2's messages, not a1's."""
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, "line", 1, ["a1", "a2", "a3"],
                 VisibilityConfig(previous_messages=True),
                 adj=[[1], [0, 2], [1]])
    _run(s, _task())
    # a3 only sees messages from a2
    assert all("_a2" in mid for mid in agents[2].received_message_ids)
    assert not any("_a1" in mid for mid in agents[2].received_message_ids)


# ======================================================================
# 5. Backward-compatible ExecutionResult
# ======================================================================


def test_result_type_unchanged():
    from societyxai.core.orchestrator import ExecutionResult
    agents = [_agent("a1")]
    s = _society(agents, "ring", 1, ["a1"], VisibilityConfig())
    r = _run(s, _task())
    assert isinstance(r, ExecutionResult)


def test_turn_round_numbers_preserved():
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, "ring", 2, ["a1", "a2"], VisibilityConfig())
    r = _run(s, _task())
    assert [t.round for t in r.turns] == [1, 1, 2, 2]
    assert [t.turn_index for t in r.turns] == [1, 2, 1, 2]


def test_agent_ids_preserved():
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, "ring", 1, ["a1", "a2", "a3"],
                 VisibilityConfig(previous_messages=True),
                 adj=[[1, 2], [0, 2], [0, 1]])
    r = _run(s, _task())
    assert r.agent_ids == ["a1", "a2", "a3"]


def test_turn_count_matches_rounds_times_agents():
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, "ring", 3, ["a1", "a2", "a3"],
                 VisibilityConfig(previous_messages=True),
                 adj=[[1, 2], [0, 2], [0, 1]])
    r = _run(s, _task())
    assert len(r.turns) == 9
    assert r.rounds_executed == 3


def test_execution_turn_fields_are_populated():
    agents = [_agent("a1")]
    s = _society(agents, "ring", 1, ["a1"], VisibilityConfig())
    be = RecordingBackend("my-model", "my-provider")
    r = _run(s, _task(), backend=be)
    turn = r.turns[0]
    assert turn.agent_id == "a1"
    assert turn.model_id == "my-model"
    assert turn.provider == "my-provider"
    assert turn.round == 1
    assert turn.turn_index == 1
    assert isinstance(turn.response, str)
