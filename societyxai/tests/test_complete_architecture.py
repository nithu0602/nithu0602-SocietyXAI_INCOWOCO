from pathlib import Path

from societyxai.config.loader import ExperimentLoader
from societyxai.config.schema import (
    ExperimentConfig,
    InterventionConfig,
    SpeakerOrderConfig,
    TopologyConfig,
    VisibilityConfig,
)
from societyxai.core import Agent, Orchestrator, Society
from societyxai.models import ModelBackend, ModelResponse
from societyxai.tasks import Task
from societyxai.utils.positions import normalize_position


class CountingBackend(ModelBackend):
    def __init__(self) -> None:
        super().__init__(model_id="fake", provider="fake")
        self.called: list[str] = []

    def generate(self, messages, temperature=None, max_tokens=None, seed=None):
        system = messages[0]["content"]
        self.called.append(system)
        return ModelResponse(text='{"position": "support", "confidence": 0.5, "evidence_ids": [], "reasoning_trace": "ok"}')


def test_normalize_approve_and_yes() -> None:
    assert normalize_position("approve") == "support"
    assert normalize_position("yes") == "support"
    assert normalize_position("reject") == "reject"


def test_complete_yaml_loads_without_network() -> None:
    path = Path(__file__).parent.parent / "configs" / "experiments" / "complete_healthcare_consultation.yaml"
    experiment = ExperimentLoader.load(path)
    assert experiment.config.topology.kind == "complete"
    assert experiment.config.architecture == "consultation"
    assert experiment.config.adjudicator_ids == ["treatment_planner"]
    roles = {agent.agent_id: agent.role for agent in experiment.society.agents}
    assert roles["gp"] == "general practitioner"
    assert experiment.backend.provider == "groq"


def test_adjudicator_skips_until_last_round() -> None:
    agents = [
        Agent(agent_id="a", role="specialist", model_id="m", system_prompt="You are a."),
        Agent(agent_id="j", role="judge", model_id="m", system_prompt="You are j."),
    ]
    society = Society(
        agents=agents,
        topology=TopologyConfig(kind="complete"),
        number_of_rounds=2,
        speaker_order=SpeakerOrderConfig(order=["a", "j"], deterministic=True),
        visibility=VisibilityConfig(previous_messages=True),
    )
    backend = CountingBackend()
    orch = Orchestrator(
        society=society,
        task=Task(task_id="t", question="Q?", ground_truth="support"),
        backend=backend,
        adjudicator_ids=["j"],
    )
    result = orch.run()
    speakers = [turn.agent_id for turn in result.turns]
    assert speakers == ["a", "a", "j"]
    assert result.rounds_executed == 2
