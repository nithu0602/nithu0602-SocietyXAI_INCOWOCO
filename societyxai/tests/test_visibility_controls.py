"""Tests for Phase 4A: Visibility controls (confidence, majority_position).

Covers: previous_messages=True/False, confidence=True/False,
majority_position=True/False, topology-restricted visibility,
intervention compatibility, and counterfactual branching compatibility.
"""
from __future__ import annotations

from societyxai.config.schema import SpeakerOrderConfig, TopologyConfig, VisibilityConfig
from societyxai.core import Agent, Orchestrator, Society
from societyxai.interventions import MessageInjectionIntervention
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


def _has_section(call: list[dict], prefix: str) -> bool:
    return any(
        msg["role"] == "user" and msg["content"].startswith(prefix)
        for msg in call
    )


def _get_section(call: list[dict], prefix: str) -> str:
    for msg in call:
        if msg["role"] == "user" and msg["content"].startswith(prefix):
            return msg["content"]
    return ""


def _has_conv(call: list[dict]) -> bool:
    return _has_section(call, "Previous messages:")


# ======================================================================
# 1. previous_messages=True
# ======================================================================


def test_previous_messages_true_shows_conversation():
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, "complete", 2, ["a1", "a2"],
                 VisibilityConfig(previous_messages=True))
    be = RecordingBackend()
    _run(s, _task(), backend=be)

    # R1T1 a1: no prior messages
    assert not _has_conv(be.calls[0])
    # R1T2 a2: sees a1's message
    assert "a1:" in _get_section(be.calls[1], "Previous messages:")
    # R2T1 a1: sees both R1 messages
    assert "a1:" in _get_section(be.calls[2], "Previous messages:")
    assert "a2:" in _get_section(be.calls[2], "Previous messages:")


# ======================================================================
# 2. previous_messages=False
# ======================================================================


def test_previous_messages_false_hides_conversation():
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, "complete", 2, ["a1", "a2"],
                 VisibilityConfig(previous_messages=False))
    be = RecordingBackend()
    _run(s, _task(), backend=be)

    for call in be.calls:
        assert not _has_conv(call)


# ======================================================================
# 3. confidence=True
# ======================================================================


def test_confidence_true_includes_confidence_section():
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, "complete", 2, ["a1", "a2"],
                 VisibilityConfig(previous_messages=True, confidence=True))
    be = RecordingBackend()
    _run(s, _task(), backend=be)

    # R1T1 a1: no other agents have beliefs yet -> no confidence
    assert not _has_section(be.calls[0], "Confidence levels")
    # R1T2 a2: a1 has spoken, confidence should appear
    assert _has_section(be.calls[1], "Confidence levels")
    assert "a1:" in _get_section(be.calls[1], "Confidence levels")
    # R2T1 a1: a2 has spoken in R1, confidence should appear
    assert _has_section(be.calls[2], "Confidence levels")
    assert "a2:" in _get_section(be.calls[2], "Confidence levels")


def test_confidence_true_displays_correct_values():
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, "complete", 1, ["a1", "a2", "a3"],
                 VisibilityConfig(previous_messages=True, confidence=True))
    be = RecordingBackend()
    _run(s, _task(), backend=be)

    # a1: no confidence info (first speaker)
    assert not _has_section(be.calls[0], "Confidence levels")
    # a2: sees a1's confidence
    conf2 = _get_section(be.calls[1], "Confidence levels")
    assert "a1:" in conf2
    assert "confidence=1.00" in conf2
    # a3: sees a1 and a2 confidence
    conf3 = _get_section(be.calls[2], "Confidence levels")
    assert "a1:" in conf3
    assert "a2:" in conf3
    assert "confidence=1.00" in conf3


# ======================================================================
# 4. confidence=False
# ======================================================================


def test_confidence_false_excludes_confidence_section():
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, "complete", 2, ["a1", "a2"],
                 VisibilityConfig(previous_messages=True, confidence=False))
    be = RecordingBackend()
    _run(s, _task(), backend=be)

    for call in be.calls:
        assert not _has_section(call, "Confidence levels")


# ======================================================================
# 5. majority_position=True
# ======================================================================


def test_majority_position_true_includes_majority():
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, "complete", 2, ["a1", "a2", "a3"],
                 VisibilityConfig(previous_messages=True, majority_position=True))
    be = RecordingBackend()
    _run(s, _task(), backend=be)

    # R1T1 a1: no other agents spoken -> no majority
    assert not _has_section(be.calls[0], "Current majority position")
    # R1T2 a2: only a1 has spoken -> only 1 position, no tie-break needed
    maj2 = _get_section(be.calls[1], "Current majority position")
    assert "support" in maj2 or "reject" in maj2 or "neutral" in maj2
    # R1T3 a3: a1 and a2 have spoken -> majority from their positions
    maj3 = _get_section(be.calls[2], "Current majority position")
    assert "support" in maj3 or "reject" in maj3 or "neutral" in maj3


def test_majority_position_not_shown_for_first_speaker():
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, "complete", 1, ["a1", "a2"],
                 VisibilityConfig(previous_messages=True, majority_position=True))
    be = RecordingBackend()
    _run(s, _task(), backend=be)

    # a1 is first speaker, no other agents have beliefs
    assert not _has_section(be.calls[0], "Current majority position")


# ======================================================================
# 6. majority_position=False
# ======================================================================


def test_majority_position_false_excludes_majority():
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, "complete", 2, ["a1", "a2", "a3"],
                 VisibilityConfig(previous_messages=True, majority_position=False))
    be = RecordingBackend()
    _run(s, _task(), backend=be)

    for call in be.calls:
        assert not _has_section(call, "Current majority position")


# ======================================================================
# 7. Visibility behavior under topology restrictions
# ======================================================================


def test_confidence_respects_topology():
    """Line topology: a1->a2->a3. a3 should NOT see a1's confidence."""
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, "line", 2, ["a1", "a2", "a3"],
                 VisibilityConfig(previous_messages=True, confidence=True),
                 adj=[[1], [0, 2], [1]])
    be = RecordingBackend()
    _run(s, _task(), backend=be)

    # R1T3 a3: sees a2 only (line topology)
    conf_r1t3 = _get_section(be.calls[2], "Confidence levels")
    assert "a2:" in conf_r1t3
    assert "a1:" not in conf_r1t3

    # R2T1 a1: sees nobody (line topology: a1 only sees [1] which is a2)
    # but a2 hasn't spoken in R2 yet, so only R1 messages visible
    conf_r2t1 = _get_section(be.calls[3], "Confidence levels")
    assert "a2:" in conf_r2t1
    assert "a1:" not in conf_r2t1


def test_majority_position_respects_topology():
    """Line topology: a3 sees a2 but not a1. Majority computed from a2 only."""
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, "line", 1, ["a1", "a2", "a3"],
                 VisibilityConfig(previous_messages=True, majority_position=True),
                 adj=[[1], [0, 2], [1]])
    be = RecordingBackend()
    _run(s, _task(), backend=be)

    # R1T2 a2: sees a1 -> majority from a1 only
    maj_r1t2 = _get_section(be.calls[1], "Current majority position")
    assert "support" in maj_r1t2 or "reject" in maj_r1t2 or "neutral" in maj_r1t2

    # R1T3 a3: sees a2 only (line topology) -> majority from a2 only
    maj_r1t3 = _get_section(be.calls[2], "Current majority position")
    assert "support" in maj_r1t3 or "reject" in maj_r1t3 or "neutral" in maj_r1t3


def test_no_previous_messages_hides_conversation_but_shows_confidence_and_majority():
    """previous_messages=False hides conversation, but confidence/majority still appear."""
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, "complete", 2, ["a1", "a2", "a3"],
                 VisibilityConfig(previous_messages=False, confidence=True, majority_position=True))
    be = RecordingBackend()
    _run(s, _task(), backend=be)

    # No conversation visible in any call
    for call in be.calls:
        assert not _has_conv(call)

    # R1T2 a2: confidence from a1 should appear, majority from a1 should appear
    assert _has_section(be.calls[1], "Confidence levels")
    assert _has_section(be.calls[1], "Current majority position")


# ======================================================================
# 8. Existing intervention behavior remains unchanged
# ======================================================================


def test_intervention_with_visibility_controls():
    """MessageInjectionIntervention still works correctly with confidence/majority enabled."""
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, "complete", 1, ["a1", "a2", "a3"],
                 VisibilityConfig(previous_messages=True, confidence=True, majority_position=True))
    task = _task()
    be = RecordingBackend()

    injected_text = "CRITICAL: New data requires approval."
    intervention = MessageInjectionIntervention(
        target_id="a2",
        injected_content=injected_text,
        round=1,
    )

    result = Orchestrator(
        society=s, task=task, backend=be,
        intervention=intervention,
    ).run()

    # a1: no injection
    assert not any(injected_text in msg["content"] for msg in be.calls[0])
    # a2: injection present
    assert any(injected_text in msg["content"] for msg in be.calls[1])
    # a3: no direct injection, but confidence and majority sections present
    assert not any(injected_text in msg["content"] for msg in be.calls[2])
    # Trace is still produced correctly
    assert result.trace is not None
    assert result.trace.intervention is not None
    assert result.trace.intervention.intervention_type == "message_injection"


# ======================================================================
# 9. Existing counterfactual branching remains unchanged
# ======================================================================


def test_counterfactual_with_visibility_controls():
    """CounterfactualExperiment works correctly with confidence/majority enabled."""
    from societyxai.interventions import CounterfactualExperiment

    class BranchingBackend(ModelBackend):
        def __init__(self):
            super().__init__(model_id="mock", provider="mock")
            self.calls: list[list[dict]] = []

        def generate(self, messages, temperature=None, max_tokens=None, seed=None):
            self.calls.append(list(messages))
            all_text = " ".join(m["content"] for m in messages)
            if "INJECTED_APPROVAL" in all_text or "support the proposal" in all_text:
                return ModelResponse(text="I support the proposal.")
            return ModelResponse(text="I reject the proposal.")

    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, "complete", 1, ["a1", "a2", "a3"],
                 VisibilityConfig(previous_messages=True, confidence=True, majority_position=True))
    task = _task()
    backend = BranchingBackend()

    intervention = MessageInjectionIntervention(
        target_id="a2",
        injected_content="INJECTED_APPROVAL: Emergency.",
        round=1,
    )

    exp = CounterfactualExperiment(society=s, task=task, backend=backend, base_run_id="vis-cf")
    comparison = exp.run_counterfactual(intervention=intervention)

    # Baseline: no injection -> reject
    assert comparison.baseline_decision == "reject"
    # Intervention: injection -> support
    assert comparison.intervention_decision == "support"
    assert comparison.decision_changed is True
    # Both branches produce valid traces
    assert comparison.baseline_trace is not None
    assert comparison.intervention_trace is not None
    # Original society agents untouched
    for agent in s.agents:
        assert agent.current_belief is None
        assert agent.belief_history == []


def test_all_visibility_flags_together():
    """All three visibility flags enabled simultaneously."""
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, "complete", 2, ["a1", "a2", "a3"],
                 VisibilityConfig(previous_messages=True, confidence=True, majority_position=True))
    be = RecordingBackend()
    _run(s, _task(), backend=be)

    # R1T1 a1: first speaker, no prior info
    assert not _has_conv(be.calls[0])
    assert not _has_section(be.calls[0], "Confidence levels")
    assert not _has_section(be.calls[0], "Current majority position")

    # R1T2 a2: sees a1, confidence from a1, majority from a1
    assert _has_conv(be.calls[1])
    assert _has_section(be.calls[1], "Confidence levels")
    assert _has_section(be.calls[1], "Current majority position")

    # R1T3 a3: sees a1+a2, confidence from a1+a2, majority from a1+a2
    assert _has_conv(be.calls[2])
    conf3 = _get_section(be.calls[2], "Confidence levels")
    assert "a1:" in conf3
    assert "a2:" in conf3
    assert _has_section(be.calls[2], "Current majority position")

    # R2T1 a1: sees R1 messages, confidence from a2+a3, majority from a2+a3
    assert _has_conv(be.calls[3])
    conf_r2t1 = _get_section(be.calls[3], "Confidence levels")
    assert "a2:" in conf_r2t1
    assert "a3:" in conf_r2t1
    assert _has_section(be.calls[3], "Current majority position")
