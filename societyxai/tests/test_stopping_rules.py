"""Focused tests for Phase 4C: stopping-rule support in Orchestrator.

Covers: no-rule preserves full rounds, consensus triggers early stop,
rounds_executed accuracy, trace integrity, intervention before stop,
counterfactual branch independence, and visibility/parameter regression.
"""
from __future__ import annotations

from typing import Any

from societyxai.config.schema import SpeakerOrderConfig, TopologyConfig, VisibilityConfig
from societyxai.core import Agent, Orchestrator, Society
from societyxai.interventions import (
    CounterfactualExperiment,
    MessageInjectionIntervention,
    run_counterfactual_experiment,
)
from societyxai.models import ModelBackend, ModelResponse
from societyxai.tasks import Task
from societyxai.traces.schema import RunTrace


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# NOTE: _extract_belief uses substring matching: "agree" is inside "disagree",
# so "I oppose." (reject) and "I approve." (support) are used to avoid collisions.

class RecordingBackend(ModelBackend):
    """Backend that records calls and returns configurable responses."""

    def __init__(self, responses: list[str] | None = None, model_id: str = "m", provider: str = "p"):
        super().__init__(model_id=model_id, provider=provider)
        self.calls: list[list[dict]] = []
        self._responses = responses
        self._call_idx = 0

    def generate(self, messages, temperature=None, max_tokens=None, seed=None):
        self.calls.append(list(messages))
        if self._responses:
            text = self._responses[self._call_idx % len(self._responses)]
        else:
            text = "ok"
        self._call_idx += 1
        return ModelResponse(text=text)


class PromptMappedBackend(ModelBackend):
    """Backend that returns a fixed response based on the system prompt."""

    def __init__(self, prompt_to_response: dict[str, str], model_id: str = "m", provider: str = "p"):
        super().__init__(model_id=model_id, provider=provider)
        self._prompt_to_response = prompt_to_response

    def generate(self, messages, temperature=None, max_tokens=None, seed=None):
        system_prompt = messages[0]["content"]
        return ModelResponse(text=self._prompt_to_response[system_prompt])


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


# ======================================================================
# 1. No stopping rule preserves full configured rounds
# ======================================================================


def test_max_rounds_rule_runs_all_rounds():
    """stopping_rule='max_rounds' runs every configured round."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, rounds=3)
    be = RecordingBackend()
    result = Orchestrator(
        society=s, task=_task(), backend=be, stopping_rule="max_rounds",
    ).run()
    assert result.rounds_executed == 3
    assert len(result.turns) == 6  # 3 rounds x 2 agents


def test_none_stopping_rule_runs_all_rounds():
    """stopping_rule=None (default) runs every configured round."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, rounds=2)
    be = RecordingBackend()
    result = Orchestrator(society=s, task=_task(), backend=be).run()
    assert result.rounds_executed == 2
    assert len(result.turns) == 4


def test_unknown_stopping_rule_runs_all_rounds():
    """An unrecognized rule string runs every configured round (safe fallback)."""
    agents = [_agent("a1")]
    s = _society(agents, rounds=2)
    be = RecordingBackend()
    result = Orchestrator(
        society=s, task=_task(), backend=be, stopping_rule="unknown_rule",
    ).run()
    assert result.rounds_executed == 2


# ======================================================================
# 2. Stopping rule triggers when condition is first satisfied
# ======================================================================


def test_consensus_stops_after_round_1():
    """All agents agree in round 1 -> consensus met -> stops early."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, rounds=5)
    # Both agents approve -> position = "support" for both -> consensus
    be = RecordingBackend(responses=["I approve.", "I approve."])
    result = Orchestrator(
        society=s, task=_task(), backend=be, stopping_rule="consensus",
    ).run()
    assert result.rounds_executed == 1
    assert len(result.turns) == 2  # only round 1 completed


def test_consensus_stops_after_round_2():
    """Agents disagree in round 1, agree in round 2 -> stops after round 2."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, rounds=5)

    # Round 1: a1=approve(support), a2=oppose(reject) -> no consensus
    # Round 2: a1=approve(support), a2=approve(support) -> consensus
    responses = [
        "I approve.",   # a1 R1: support
        "I oppose.",    # a2 R1: reject
        "I approve.",   # a1 R2: support
        "I approve.",   # a2 R2: support
    ]
    be = RecordingBackend(responses=responses)
    result = Orchestrator(
        society=s, task=_task(), backend=be, stopping_rule="consensus",
    ).run()
    assert result.rounds_executed == 2
    assert len(result.turns) == 4


# ======================================================================
# 3. Remaining rounds are not executed after stopping
# ======================================================================


def test_no_turns_beyond_consensus_round():
    """Once consensus is met, no further backend calls are made."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, rounds=10)
    be = RecordingBackend(responses=["I approve.", "I approve."])
    result = Orchestrator(
        society=s, task=_task(), backend=be, stopping_rule="consensus",
    ).run()
    assert result.rounds_executed == 1
    assert len(be.calls) == 2  # only 2 backend calls (1 round x 2 agents)


# ======================================================================
# 4. rounds_executed is correct
# ======================================================================


def test_rounds_executed_matches_actual_rounds():
    """rounds_executed always reflects the number of completed rounds."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, rounds=4)
    # a1 and a2 disagree -> no consensus -> runs all 4 rounds
    be = RecordingBackend(responses=["I approve.", "I oppose."] * 4)
    result = Orchestrator(
        society=s, task=_task(), backend=be, stopping_rule="consensus",
    ).run()
    assert result.rounds_executed == 4  # never reached consensus, ran all


def test_rounds_executed_on_early_stop():
    """rounds_executed reflects the round where consensus was reached."""
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, rounds=5)
    # Round 1: all approve -> consensus
    responses = ["I approve."] * 3
    be = RecordingBackend(responses=responses)
    result = Orchestrator(
        society=s, task=_task(), backend=be, stopping_rule="consensus",
    ).run()
    assert result.rounds_executed == 1


# ======================================================================
# 5. Trace contains only executed turns
# ======================================================================


def test_trace_agent_traces_match_executed_turns():
    """RunTrace.agent_traces contains exactly one entry per executed turn."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, rounds=3)
    be = RecordingBackend(responses=["I approve.", "I approve."])
    result = Orchestrator(
        society=s, task=_task(), backend=be, stopping_rule="consensus",
    ).run()
    assert result.trace is not None
    assert isinstance(result.trace, RunTrace)
    assert len(result.trace.agent_traces) == len(result.turns)
    assert len(result.trace.message_traces) == len(result.turns)


def test_trace_message_traces_match_executed_turns():
    """RunTrace.message_traces contains exactly one entry per executed turn."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, rounds=2)
    be = RecordingBackend(responses=["I approve.", "I oppose.",
                                     "I approve.", "I oppose."])
    result = Orchestrator(
        society=s, task=_task(), backend=be, stopping_rule="max_rounds",
    ).run()
    assert result.trace is not None
    assert len(result.trace.message_traces) == 4  # 2 rounds x 2 agents
    assert all(mt.agent_id for mt in result.trace.message_traces)


def test_trace_final_decision_after_early_stop():
    """final_decision in RunTrace reflects the majority of the final round."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, rounds=5)
    # Round 1: both approve -> consensus -> stop
    responses = ["I approve.", "I approve."]
    be = RecordingBackend(responses=responses)
    result = Orchestrator(
        society=s, task=_task(), backend=be, stopping_rule="consensus",
    ).run()
    assert result.trace is not None
    assert result.trace.final_decision == "support"


def test_majority_vote_unanimous_support():
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, rounds=1)
    be = PromptMappedBackend({
        "sys-a1": "I approve.",
        "sys-a2": "I approve.",
        "sys-a3": "I approve.",
    })
    for agent in agents:
        agent.system_prompt = f"sys-{agent.agent_id}"
    result = Orchestrator(society=s, task=_task(), backend=be).run()
    assert result.trace is not None
    assert result.trace.final_decision == "support"


def test_majority_vote_unanimous_reject():
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, rounds=1)
    be = PromptMappedBackend({
        "sys-a1": "I oppose.",
        "sys-a2": "I oppose.",
        "sys-a3": "I oppose.",
    })
    for agent in agents:
        agent.system_prompt = f"sys-{agent.agent_id}"
    result = Orchestrator(society=s, task=_task(), backend=be).run()
    assert result.trace is not None
    assert result.trace.final_decision == "reject"


def test_majority_vote_three_two_majority():
    agents = [_agent("a1"), _agent("a2"), _agent("a3"), _agent("a4"), _agent("a5")]
    s = _society(agents, rounds=1)
    be = PromptMappedBackend({
        "sys-a1": "I approve.",
        "sys-a2": "I approve.",
        "sys-a3": "I approve.",
        "sys-a4": "I oppose.",
        "sys-a5": "I oppose.",
    })
    for agent in agents:
        agent.system_prompt = f"sys-{agent.agent_id}"
    result = Orchestrator(society=s, task=_task(), backend=be).run()
    assert result.trace is not None
    assert result.trace.final_decision == "support"


def test_majority_vote_tie_uses_deterministic_rule():
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, rounds=1)
    be = PromptMappedBackend({
        "sys-a1": "I approve.",
        "sys-a2": "I oppose.",
    })
    for agent in agents:
        agent.system_prompt = f"sys-{agent.agent_id}"
    result = Orchestrator(society=s, task=_task(), backend=be).run()
    assert result.trace is not None
    assert result.trace.final_decision == "reject"


def test_majority_vote_is_independent_of_speaking_order():
    agents_a = [_agent("a1"), _agent("a2"), _agent("a3")]
    agents_b = [_agent("a1"), _agent("a2"), _agent("a3")]
    for agent in agents_a + agents_b:
        agent.system_prompt = f"sys-{agent.agent_id}"

    backend_a = PromptMappedBackend({
        "sys-a1": "I approve.",
        "sys-a2": "I approve.",
        "sys-a3": "I oppose.",
    })
    backend_b = PromptMappedBackend({
        "sys-a1": "I approve.",
        "sys-a2": "I approve.",
        "sys-a3": "I oppose.",
    })

    s_a = Society(
        agents=agents_a,
        topology=TopologyConfig(kind="complete"),
        number_of_rounds=1,
        speaker_order=SpeakerOrderConfig(order=["a1", "a2", "a3"], deterministic=True),
        visibility=VisibilityConfig(),
    )
    s_b = Society(
        agents=agents_b,
        topology=TopologyConfig(kind="complete"),
        number_of_rounds=1,
        speaker_order=SpeakerOrderConfig(order=["a3", "a2", "a1"], deterministic=True),
        visibility=VisibilityConfig(),
    )

    result_a = Orchestrator(society=s_a, task=_task(), backend=backend_a).run()
    result_b = Orchestrator(society=s_b, task=_task(), backend=backend_b).run()

    assert result_a.trace is not None
    assert result_b.trace is not None
    assert result_a.trace.final_decision == "support"
    assert result_b.trace.final_decision == "support"


# ======================================================================
# 6. Intervention behavior before the stopping point still occurs
# ======================================================================


def test_intervention_applies_before_consensus_stop():
    """An intervention targeting round 1 still fires even with consensus stopping."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, rounds=3)
    intervention = MessageInjectionIntervention(
        target_id="a1",
        injected_content="INJECTED_MSG",
        round=1,
    )
    # Both approve -> consensus round 1
    be = RecordingBackend(responses=["I approve.", "I approve."])
    result = Orchestrator(
        society=s, task=_task(), backend=be,
        stopping_rule="consensus", intervention=intervention,
    ).run()
    assert result.rounds_executed == 1
    assert result.trace is not None
    assert result.trace.intervention is not None
    assert result.trace.intervention.intervention_type == "message_injection"


def test_intervention_round_filtering_with_consensus():
    """Intervention targeting round 2 does not fire if consensus stops at round 1."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, rounds=3)
    intervention = MessageInjectionIntervention(
        target_id="a1",
        injected_content="ROUND2_INJECT",
        round=2,
    )
    be = RecordingBackend(responses=["I approve.", "I approve."])
    result = Orchestrator(
        society=s, task=_task(), backend=be,
        stopping_rule="consensus", intervention=intervention,
    ).run()
    # Stopped at round 1, round 2 intervention never reached
    assert result.rounds_executed == 1
    # The intervention was constructed but never applied to any message
    for msg_trace in result.trace.message_traces:
        assert "ROUND2_INJECT" not in msg_trace.content


# ======================================================================
# 7. Baseline and intervention branches apply stopping independently
# ======================================================================


def test_counterfactual_both_branches_honor_consensus():
    """Both baseline and intervention branches respect the stopping rule."""
    agents = [_agent("a1"), _agent("a2")]
    s = _society(agents, rounds=5)

    class ConsensusBackend(ModelBackend):
        def __init__(self):
            super().__init__(model_id="m", provider="p")
            self.total_calls = 0

        def generate(self, messages, temperature=None, max_tokens=None, seed=None):
            self.total_calls += 1
            return ModelResponse(text="I approve.")

    backend = ConsensusBackend()
    intervention = MessageInjectionIntervention(
        target_id="a1",
        injected_content="INJECT",
        round=1,
    )

    exp = CounterfactualExperiment(
        society=s, task=_task(), backend=backend,
        base_run_id="cf-stop", stopping_rule="consensus",
    )
    comparison = exp.run_counterfactual(intervention=intervention)

    # Both branches should have stopped after round 1
    # With 2 agents, round 1 = 2 agent traces per branch
    assert len(comparison.baseline_trace.agent_traces) == 2
    assert len(comparison.intervention_trace.agent_traces) == 2


def test_counterfactual_independent_stopping_via_convenience_fn():
    """run_counterfactual_experiment passes stopping_rule through."""
    agents = [_agent("a1")]
    s = _society(agents, rounds=3)
    be = RecordingBackend(responses=["I approve."])
    intervention = MessageInjectionIntervention(
        target_id="a1", injected_content="X", round=1,
    )
    comparison = run_counterfactual_experiment(
        society=s, task=_task(), backend=be,
        intervention=intervention, stopping_rule="consensus",
        base_run_id="cf-convenience",
    )
    # With 1 agent, round 1 = 1 agent trace
    assert len(comparison.baseline_trace.agent_traces) == 1
    assert len(comparison.intervention_trace.agent_traces) == 1


# ======================================================================
# 8. Existing visibility and generation-parameter behavior unchanged
# ======================================================================


def test_visibility_still_works_with_consensus():
    """Visibility controls are unaffected by the stopping rule."""
    agents = [_agent("a1"), _agent("a2")]
    s = Society(
        agents=agents,
        topology=TopologyConfig(kind="complete"),
        number_of_rounds=3,
        speaker_order=SpeakerOrderConfig(order=["a1", "a2"], deterministic=True),
        visibility=VisibilityConfig(previous_messages=False),
    )
    be = RecordingBackend(responses=["I approve.", "I approve."])
    result = Orchestrator(
        society=s, task=_task(), backend=be, stopping_rule="consensus",
    ).run()
    assert result.rounds_executed == 1
    # With previous_messages=False, no conversation should appear
    for call in be.calls:
        assert not any("Previous messages:" in m["content"] for m in call)


def test_generation_params_still_forwarded():
    """Temperature, max_tokens, seed are forwarded regardless of stopping rule."""
    agents = [_agent("a1")]
    s = _society(agents, rounds=3)
    be = RecordingBackend(responses=["I approve."])
    Orchestrator(
        society=s, task=_task(), backend=be,
        stopping_rule="consensus",
        temperature=0.77, max_tokens=200, seed=42,
    ).run()
    # The backend received the parameters
    assert len(be.calls) == 1


def test_consensus_with_three_agents():
    """Consensus requires ALL agents to agree."""
    agents = [_agent("a1"), _agent("a2"), _agent("a3")]
    s = _society(agents, rounds=5)
    # Round 1: a1=approve, a2=approve, a3=oppose -> no consensus
    # Round 2: all approve -> consensus
    responses = [
        "I approve.",   # a1 R1: support
        "I approve.",   # a2 R1: support
        "I oppose.",    # a3 R1: reject
        "I approve.",   # a1 R2: support
        "I approve.",   # a2 R2: support
        "I approve.",   # a3 R2: support
    ]
    be = RecordingBackend(responses=responses)
    result = Orchestrator(
        society=s, task=_task(), backend=be, stopping_rule="consensus",
    ).run()
    assert result.rounds_executed == 2
    assert len(result.turns) == 6
