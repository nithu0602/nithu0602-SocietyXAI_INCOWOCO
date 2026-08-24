"""Focused tests for Phase 5A: pluggable structured belief parsing.

Covers: legacy heuristic unchanged, structured JSON parsing, evidence and
reasoning preservation, fallback on malformed input, agent belief integration,
RunTrace correctness, intervention/counterfactual compatibility, and
parser_version config selection.
"""
from __future__ import annotations

import json

from societyxai.config.schema import SpeakerOrderConfig, TopologyConfig, VisibilityConfig
from societyxai.core import Agent, Orchestrator, Society
from societyxai.interventions import (
    CounterfactualExperiment,
    MessageInjectionIntervention,
    run_counterfactual_experiment,
)
from societyxai.models import ModelBackend, ModelResponse
from societyxai.parsers import BeliefParser, HeuristicBeliefParser, StructuredBeliefParser
from societyxai.tasks import Task
from societyxai.traces.schema import BeliefState, RunTrace


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class RecordingBackend(ModelBackend):
    """Backend that records calls and returns configurable responses."""

    def __init__(self, responses: list[str] | None = None, model_id: str = "m", provider: str = "p"):
        super().__init__(model_id=model_id, provider=provider)
        self._responses = responses
        self._call_idx = 0

    def generate(self, messages, temperature=None, max_tokens=None, seed=None):
        if self._responses:
            text = self._responses[self._call_idx % len(self._responses)]
        else:
            text = "ok"
        self._call_idx += 1
        return ModelResponse(text=text)


def _agent(agent_id: str) -> Agent:
    return Agent(agent_id=agent_id, role="speaker", model_id="m", system_prompt="sys")


def _task(**kw):
    defaults = dict(task_id="t1", question="Q?", ground_truth="A")
    defaults.update(kw)
    return Task(**defaults)


def _society(agents, rounds=1):
    return Society(
        agents=agents,
        topology=TopologyConfig(kind="complete"),
        number_of_rounds=rounds,
        speaker_order=SpeakerOrderConfig(order=[a.agent_id for a in agents], deterministic=True),
        visibility=VisibilityConfig(),
    )


def _json_response(position="support", confidence=0.85, evidence_ids=None, reasoning_trace=""):
    return json.dumps({
        "position": position,
        "confidence": confidence,
        "evidence_ids": evidence_ids or [],
        "reasoning_trace": reasoning_trace,
    })


# ======================================================================
# 1. Legacy heuristic parsing remains unchanged
# ======================================================================


def test_heuristic_support_keyword():
    """Heuristic parser maps 'approve' to support."""
    p = HeuristicBeliefParser()
    b = p.parse("I approve.")
    assert b.position == "support"
    assert b.confidence == 1.0
    assert b.evidence_ids == []


def test_heuristic_reject_keyword():
    """Heuristic parser maps 'oppose' to reject."""
    p = HeuristicBeliefParser()
    b = p.parse("I oppose.")
    assert b.position == "reject"
    assert b.confidence == 1.0


def test_heuristic_neutral_fallback():
    """Heuristic parser maps unrecognised text to neutral."""
    p = HeuristicBeliefParser()
    b = p.parse("The weather is nice.")
    assert b.position == "neutral"


def test_heuristic_without_parser_param_uses_heuristic():
    """Orchestrator without belief_parser defaults to HeuristicBeliefParser."""
    agents = [_agent("a1")]
    s = _society(agents, rounds=1)
    be = RecordingBackend(responses=["I oppose."])
    result = Orchestrator(society=s, task=_task(), backend=be).run()
    assert result.trace is not None
    assert result.trace.agent_traces[0].belief.position == "reject"


# ======================================================================
# 2. Valid structured JSON parses correctly
# ======================================================================


def test_structured_json_parses_correctly():
    """StructuredBeliefParser correctly parses valid JSON output."""
    p = StructuredBeliefParser()
    resp = _json_response(position="reject", confidence=0.92)
    b = p.parse(resp)
    assert b.position == "reject"
    assert b.confidence == 0.92


def test_structured_json_via_orchestrator():
    """StructuredBeliefParser plugged into Orchestrator parses JSON responses."""
    agents = [_agent("a1")]
    s = _society(agents, rounds=1)
    resp = _json_response(position="neutral", confidence=0.4)
    be = RecordingBackend(responses=[resp])
    parser = StructuredBeliefParser()
    result = Orchestrator(
        society=s, task=_task(), backend=be, belief_parser=parser,
    ).run()
    assert result.trace is not None
    belief = result.trace.agent_traces[0].belief
    assert belief.position == "neutral"
    assert belief.confidence == 0.4


# ======================================================================
# 3. Evidence IDs are preserved
# ======================================================================


def test_structured_evidence_ids_preserved():
    """Structured parser preserves evidence_ids from JSON."""
    p = StructuredBeliefParser()
    resp = _json_response(position="support", evidence_ids=["e1", "e2", "e3"])
    b = p.parse(resp)
    assert b.evidence_ids == ["e1", "e2", "e3"]


# ======================================================================
# 4. Reasoning trace is preserved
# ======================================================================


def test_structured_reasoning_trace_preserved():
    """Structured parser preserves reasoning_trace from JSON."""
    p = StructuredBeliefParser()
    resp = _json_response(
        position="support",
        confidence=0.7,
        reasoning_trace="Evidence shows clear pattern.",
    )
    b = p.parse(resp)
    assert b.reasoning_trace == "Evidence shows clear pattern."


# ======================================================================
# 5. Invalid JSON falls back correctly
# ======================================================================


def test_structured_invalid_json_falls_back():
    """StructuredBeliefParser falls back to heuristic on non-JSON input."""
    p = StructuredBeliefParser()
    b = p.parse("I approve.")
    # Falls back to heuristic: "approve" -> support
    assert b.position == "support"
    assert b.confidence == 1.0


def test_structured_empty_string_falls_back():
    """StructuredBeliefParser falls back on empty string."""
    p = StructuredBeliefParser()
    b = p.parse("")
    assert b.position == "neutral"  # heuristic fallback


# ======================================================================
# 6. Invalid confidence falls back correctly
# ======================================================================


def test_structured_invalid_confidence_falls_back():
    """StructuredBeliefParser falls back when confidence is out of range."""
    p = StructuredBeliefParser()
    resp = json.dumps({
        "position": "support",
        "confidence": 1.5,
        "evidence_ids": [],
        "reasoning_trace": "",
    })
    b = p.parse(resp)
    # BeliefState validation rejects confidence > 1.0, parser falls back
    assert b.position == "support"  # heuristic matches "support" in the text
    assert b.confidence == 1.0


# ======================================================================
# 7. Missing fields fall back correctly
# ======================================================================


def test_structured_missing_position_falls_back():
    """StructuredBeliefParser falls back when position key is missing."""
    p = StructuredBeliefParser()
    resp = json.dumps({"confidence": 0.5})
    b = p.parse(resp)
    assert b.position == "neutral"  # heuristic fallback


def test_structured_missing_confidence_falls_back():
    """StructuredBeliefParser falls back when confidence key is missing."""
    p = StructuredBeliefParser()
    resp = json.dumps({"position": "support"})
    b = p.parse(resp)
    # "support" in the JSON text triggers heuristic fallback -> support
    assert b.position == "support"
    assert b.confidence == 1.0


def test_structured_non_dict_json_falls_back():
    """StructuredBeliefParser falls back when JSON is not a dict."""
    p = StructuredBeliefParser()
    b = p.parse('[1, 2, 3]')
    assert b.position == "neutral"


def test_structured_array_value_falls_back():
    """StructuredBeliefParser falls back when a field has wrong type."""
    p = StructuredBeliefParser()
    resp = json.dumps({
        "position": "support",
        "confidence": 0.8,
        "evidence_ids": "not_a_list",
        "reasoning_trace": "",
    })
    b = p.parse(resp)
    assert b.position == "support"  # heuristic fallback on JSON text


# ======================================================================
# 8. Parsed belief reaches Agent.current_belief
# ======================================================================


def test_structured_belief_reaches_agent_current_belief():
    """StructuredBeliefParser result updates Agent.current_belief."""
    agents = [_agent("a1")]
    s = _society(agents, rounds=1)
    resp = _json_response(position="reject", confidence=0.6, reasoning_trace="Strong evidence.")
    be = RecordingBackend(responses=[resp])
    parser = StructuredBeliefParser()
    Orchestrator(
        society=s, task=_task(), backend=be, belief_parser=parser,
    ).run()
    assert agents[0].current_belief is not None
    assert agents[0].current_belief.position == "reject"
    assert agents[0].current_belief.confidence == 0.6
    assert agents[0].current_belief.reasoning_trace == "Strong evidence."


# ======================================================================
# 9. Parsed belief appears in Agent.belief_history
# ======================================================================


def test_structured_belief_appears_in_belief_history():
    """StructuredBeliefParser result is appended to Agent.belief_history."""
    agents = [_agent("a1")]
    s = _society(agents, rounds=2)
    resp = _json_response(position="support", confidence=0.9)
    be = RecordingBackend(responses=[resp, resp])
    parser = StructuredBeliefParser()
    Orchestrator(
        society=s, task=_task(), backend=be, belief_parser=parser,
    ).run()
    assert len(agents[0].belief_history) == 2
    for bh in agents[0].belief_history:
        assert bh.position == "support"
        assert bh.confidence == 0.9


# ======================================================================
# 10. Parsed belief appears correctly in RunTrace
# ======================================================================


def test_structured_belief_in_run_trace():
    """StructuredBeliefParser belief is recorded in RunTrace.agent_traces."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, rounds=1)
    resp_a1 = _json_response(position="support", confidence=0.8)
    resp_a2 = _json_response(position="reject", confidence=0.95, evidence_ids=["e1"])
    be = RecordingBackend(responses=[resp_a1, resp_a2])
    parser = StructuredBeliefParser()
    result = Orchestrator(
        society=s, task=_task(), backend=be, belief_parser=parser,
    ).run()
    assert result.trace is not None
    beliefs = {at.agent_id: at.belief for at in result.trace.agent_traces}
    assert beliefs["a1"].position == "support"
    assert beliefs["a1"].confidence == 0.8
    assert beliefs["a2"].position == "reject"
    assert beliefs["a2"].confidence == 0.95
    assert beliefs["a2"].evidence_ids == ["e1"]


def test_structured_belief_final_decision_in_run_trace():
    """final_decision reflects the last structured-parsed belief position."""
    agents = [_agent("a1")]
    s = _society(agents, rounds=2)
    r1 = _json_response(position="support")
    r2 = _json_response(position="reject")
    be = RecordingBackend(responses=[r1, r2])
    parser = StructuredBeliefParser()
    result = Orchestrator(
        society=s, task=_task(), backend=be, belief_parser=parser,
    ).run()
    assert result.trace is not None
    assert result.trace.final_decision == "reject"


# ======================================================================
# 11. Interventions still work with structured parser
# ======================================================================


def test_intervention_with_structured_parser():
    """MessageInjectionIntervention works with StructuredBeliefParser."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, rounds=2)
    resp = _json_response(position="support", confidence=0.75)
    be = RecordingBackend(responses=[resp, resp, resp, resp])
    intervention = MessageInjectionIntervention(
        target_id="a1", injected_content="INJECTED", round=1,
    )
    parser = StructuredBeliefParser()
    result = Orchestrator(
        society=s, task=_task(), backend=be,
        belief_parser=parser, intervention=intervention,
    ).run()
    assert result.trace is not None
    assert result.trace.intervention is not None
    # Beliefs still parsed correctly through structured parser
    assert result.trace.agent_traces[0].belief.position == "support"
    assert result.trace.agent_traces[0].belief.confidence == 0.75


# ======================================================================
# 12. Counterfactual branches still work with structured parser
# ======================================================================


def test_counterfactual_with_structured_parser():
    """CounterfactualExperiment works with StructuredBeliefParser."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, rounds=2)
    resp = _json_response(position="support", confidence=0.88, reasoning_trace="Analysis complete.")
    be = RecordingBackend(responses=[resp] * 10)
    intervention = MessageInjectionIntervention(
        target_id="a1", injected_content="BRANCH", round=1,
    )
    parser = StructuredBeliefParser()
    exp = CounterfactualExperiment(
        society=s, task=_task(), backend=be,
        base_run_id="cf-parse", belief_parser=parser,
    )
    comparison = exp.run_counterfactual(intervention=intervention)
    # Both branches should have structured beliefs
    for trace in (comparison.baseline_trace, comparison.intervention_trace):
        for at in trace.agent_traces:
            assert at.belief.position == "support"
            assert at.belief.confidence == 0.88
            assert at.belief.reasoning_trace == "Analysis complete."


def test_counterfactual_convenience_fn_with_structured_parser():
    """run_counterfactual_experiment passes structured parser through."""
    agents = [_agent("a1")]
    s = _society(agents, rounds=1)
    resp = _json_response(position="reject", confidence=0.6)
    be = RecordingBackend(responses=[resp, resp])
    intervention = MessageInjectionIntervention(
        target_id="a1", injected_content="X", round=1,
    )
    parser = StructuredBeliefParser()
    comparison = run_counterfactual_experiment(
        society=s, task=_task(), backend=be,
        intervention=intervention, belief_parser=parser,
        base_run_id="cf-struct",
    )
    for trace in (comparison.baseline_trace, comparison.intervention_trace):
        assert trace.agent_traces[0].belief.position == "reject"
        assert trace.agent_traces[0].belief.confidence == 0.6


# ======================================================================
# 13. parser_version config selection
# ======================================================================


def test_structured_parser_is_an_instance_of_belief_parser():
    """StructuredBeliefParser satisfies BeliefParser ABC."""
    p = StructuredBeliefParser()
    assert isinstance(p, BeliefParser)


def test_heuristic_parser_is_an_instance_of_belief_parser():
    """HeuristicBeliefParser satisfies BeliefParser ABC."""
    p = HeuristicBeliefParser()
    assert isinstance(p, BeliefParser)


def test_structured_parser_strict_mode_raises():
    """StructuredBeliefParser in strict mode raises on invalid input."""
    p = StructuredBeliefParser(strict=True)
    try:
        p.parse("not json at all")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_structured_parser_strict_mode_with_valid_json():
    """StructuredBeliefParser in strict mode works on valid JSON."""
    p = StructuredBeliefParser(strict=True)
    resp = _json_response(position="support", confidence=0.5)
    b = p.parse(resp)
    assert b.position == "support"
    assert b.confidence == 0.5


def test_structured_parser_json_array_falls_back():
    """StructuredBeliefParser handles JSON arrays as invalid structure (fallback to heuristic)."""
    p = StructuredBeliefParser()
    # JSON array is not a dict -> falls back to heuristic substring match
    b = p.parse('["support", 0.8]')
    assert b.position == "support"  # heuristic sees "support" in the raw text
    assert b.confidence == 1.0


def test_heuristic_belief_confidence_always_one():
    """Heuristic parser always produces confidence=1.0."""
    p = HeuristicBeliefParser()
    for text in ["I approve.", "I oppose.", "Something else."]:
        b = p.parse(text)
        assert b.confidence == 1.0


def test_multiple_agents_structured_parsing():
    """Multiple agents each receive their own structured-parsed belief."""
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, rounds=1)
    responses = [
        _json_response(position="support", confidence=0.7),
        _json_response(position="reject", confidence=0.9),
        _json_response(position="neutral", confidence=0.5, reasoning_trace="Undecided."),
    ]
    be = RecordingBackend(responses=responses)
    parser = StructuredBeliefParser()
    result = Orchestrator(
        society=s, task=_task(), backend=be, belief_parser=parser,
    ).run()
    beliefs = {at.agent_id: at.belief for at in result.trace.agent_traces}
    assert beliefs["a1"].position == "support"
    assert beliefs["a2"].position == "reject"
    assert beliefs["a3"].position == "neutral"
    assert beliefs["a3"].reasoning_trace == "Undecided."
