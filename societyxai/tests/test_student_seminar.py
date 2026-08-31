from __future__ import annotations

from pathlib import Path

from societyxai.config.loader import ExperimentLoader
from societyxai.core import Agent, Orchestrator, Society
from societyxai.models import ModelBackend, ModelResponse
from societyxai.tasks import Task
from societyxai.traces.schema import BeliefState, RunTrace
from societyxai.config.schema import SpeakerOrderConfig, TopologyConfig, VisibilityConfig

from student_seminar.build import (
    build,
    build_experiment_dict,
    default_question_path,
    load_question,
    speaker_order,
    load_roster,
)
from student_seminar.monitor import first_correct_proposer, format_report, report

PACK = Path(__file__).resolve().parent.parent / "student_seminar"


def test_inbox_questions_have_required_fields() -> None:
    social = load_question(PACK / "questions" / "INBOX_SOCIAL.yaml")
    aptitude = load_question(PACK / "questions" / "INBOX_APTITUDE.yaml")
    assert social["ground_truth"] in {"support", "reject"}
    assert aptitude["ground_truth"] in {"support", "reject"}
    assert social["evidence"]
    assert aptitude["evidence"]
    assert default_question_path("social").name == "INBOX_SOCIAL.yaml"


def test_roster_orders_are_five_unique_students() -> None:
    roster = load_roster()
    for case in ("social", "aptitude"):
        for name in ("default", "reverse", "weak_first"):
            order = speaker_order(roster, case, name)
            assert len(order) == 5
            assert len(set(order)) == 5
            assert set(order) == set(roster["students"])
        assert speaker_order(roster, case, "default")[-1] == "asha"
        assert speaker_order(roster, case, "reverse") == list(
            reversed(speaker_order(roster, case, "default"))
        )
        assert speaker_order(roster, case, "weak_first")[:2] == ["noor", "rahul"]


def test_social_build_assigns_hats_and_seminar_architecture() -> None:
    experiment = build("social", "default")
    roles = {agent.agent_id: agent.role for agent in experiment.society.agents}
    assert experiment.config.architecture == "seminar"
    assert roles["asha"] == "moderator"
    assert roles["rahul"] == "advocate"
    assert roles["mei"] == "critic"
    assert roles["ilya"] == "fact_checker"
    assert roles["noor"] == "impact_analyst"
    assert experiment.config.adjudicator_ids == ["asha"]
    assert experiment.config.speaker_order.order[-1] == "asha"
    assert experiment.society.agents[0].capability_score is not None


def test_aptitude_build_assigns_hats() -> None:
    experiment = build("aptitude", "weak_first")
    roles = {agent.agent_id: agent.role for agent in experiment.society.agents}
    assert roles["rahul"] == "solver"
    assert roles["mei"] == "skeptic"
    assert roles["ilya"] == "alt_path"
    assert roles["noor"] == "formalizer"
    assert roles["asha"] == "closer"
    assert experiment.config.speaker_order.order[:2] == ["noor", "rahul"]


def test_fallback_rewrites_missing_labs_to_groq(monkeypatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    experiment_data, _task = build_experiment_dict("social", "default", fallback="groq")
    assert set(experiment_data["agent_providers"].values()) == {"groq"}
    assert "gpt-oss-20b" in experiment_data["agent_models"]["mei"]
    assert "gpt-oss-120b" in experiment_data["agent_models"]["asha"]


def test_generated_config_round_trips_loader() -> None:
    experiment_data, task_data = build_experiment_dict("aptitude", "reverse")
    loaded = ExperimentLoader.build(
        __import__("societyxai.config.schema", fromlist=["ExperimentConfig"]).ExperimentConfig(
            **experiment_data
        ),
        task_data,
    )
    assert loaded.config.speaker_order.order[0] == "asha"
    assert loaded.task.ground_truth == "support"


class _FixedBackend(ModelBackend):
    def __init__(self) -> None:
        super().__init__(model_id="fake", provider="fake")

    def generate(self, messages, temperature=None, max_tokens=None, seed=None):
        return ModelResponse(
            text='{"position":"support","confidence":0.7,"evidence_ids":["e1"],"reasoning_trace":"ok"}'
        )


def test_monitor_reports_first_correct_and_consensus() -> None:
    agents = [
        Agent(agent_id="rahul", role="solver", model_id="m", system_prompt="x"),
        Agent(agent_id="mei", role="skeptic", model_id="m", system_prompt="x"),
    ]
    society = Society(
        agents=agents,
        topology=TopologyConfig(kind="complete"),
        number_of_rounds=1,
        speaker_order=SpeakerOrderConfig(order=["rahul", "mei"]),
        visibility=VisibilityConfig(previous_messages=True),
    )
    result = Orchestrator(
        society=society,
        task=Task(task_id="t", question="Q?", ground_truth="support"),
        backend=_FixedBackend(),
    ).run()
    assert result.trace is not None
    payload = report(result.trace)
    assert payload["correct"] is True
    assert payload["first_correct_proposer"] == "rahul"
    assert payload["consensus_score"] == 1.0
    text = format_report(payload)
    assert "first correct proposer" in text


def test_first_correct_proposer_on_manual_trace() -> None:
    trace = RunTrace(
        run_id="r",
        task_id="t",
        seed=1,
        timestamp="2026-08-27T00:00:00Z",
        model_id="m",
        provider="p",
        temperature=0.0,
        topology=TopologyConfig(kind="complete"),
        ground_truth="support",
        agent_traces=[],
        final_decision="support",
        correctness=True,
    )
    from societyxai.traces.schema import AgentTrace

    trace.agent_traces = [
        AgentTrace(
            agent_id="mei",
            role="skeptic",
            model_id="g",
            provider="gemini",
            round=1,
            turn_index=1,
            belief=BeliefState(position="reject", confidence=0.4),
        ),
        AgentTrace(
            agent_id="rahul",
            role="solver",
            model_id="l",
            provider="openai",
            round=1,
            turn_index=2,
            belief=BeliefState(position="support", confidence=0.8),
        ),
    ]
    assert first_correct_proposer(trace) == "rahul"
