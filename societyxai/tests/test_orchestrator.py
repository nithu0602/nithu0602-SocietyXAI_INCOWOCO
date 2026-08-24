import pytest
from pydantic import ValidationError

from societyxai.config.schema import SpeakerOrderConfig, TopologyConfig, VisibilityConfig
from societyxai.core import Agent, Orchestrator, Society
from societyxai.models import ModelBackend, ModelResponse
from societyxai.tasks import Task


class FakeBackend(ModelBackend):
    def generate(self, messages, temperature=None, max_tokens=None, seed=None):
        return ModelResponse(text=f"response:{len(messages)}:{temperature}:{max_tokens}:{seed}")


def _make_agent(agent_id: str, model_id: str = "model-a") -> Agent:
    return Agent(
        agent_id=agent_id,
        role="speaker",
        model_id=model_id,
        system_prompt="You are a helpful assistant.",
    )


def test_valid_orchestrator_can_be_created() -> None:
    society = Society(
        agents=[_make_agent("a1"), _make_agent("a2")],
        topology=TopologyConfig(kind="ring"),
        number_of_rounds=2,
        speaker_order=SpeakerOrderConfig(order=["a1", "a2"], deterministic=True),
        visibility=VisibilityConfig(),
    )
    task = Task(
        task_id="task-1",
        question="What is the decision?",
        ground_truth="Decision A",
    )
    backend = FakeBackend("fake-model", "fake-provider")

    orchestrator = Orchestrator(society=society, task=task, backend=backend)
    assert orchestrator.task.task_id == "task-1"


def test_fake_backend_can_be_injected() -> None:
    society = Society(
        agents=[_make_agent("a1")],
        topology=TopologyConfig(kind="ring"),
        number_of_rounds=1,
        speaker_order=SpeakerOrderConfig(order=["a1"], deterministic=True),
        visibility=VisibilityConfig(),
    )
    task = Task(task_id="task-2", question="Question?", ground_truth="Answer")
    backend = FakeBackend("fake-model", "fake-provider")

    result = Orchestrator(society=society, task=task, backend=backend).run()
    assert result.task_id == "task-2"


def test_five_agents_three_rounds_produce_expected_turns() -> None:
    agents = [_make_agent(f"a{i}") for i in range(1, 6)]
    society = Society(
        agents=agents,
        topology=TopologyConfig(kind="ring"),
        number_of_rounds=3,
        speaker_order=SpeakerOrderConfig(order=["a1", "a2", "a3", "a4", "a5"], deterministic=True),
        visibility=VisibilityConfig(),
    )
    task = Task(task_id="task-3", question="Question?", ground_truth="Answer")
    backend = FakeBackend("fake-model", "fake-provider")

    result = Orchestrator(society=society, task=task, backend=backend).run()
    assert result.rounds_executed == 3
    assert len(result.turns) == 15


def test_round_numbers_are_correct() -> None:
    society = Society(
        agents=[_make_agent("a1"), _make_agent("a2")],
        topology=TopologyConfig(kind="ring"),
        number_of_rounds=2,
        speaker_order=SpeakerOrderConfig(order=["a1", "a2"], deterministic=True),
        visibility=VisibilityConfig(),
    )
    task = Task(task_id="task-4", question="Question?", ground_truth="Answer")
    backend = FakeBackend("fake-model", "fake-provider")

    result = Orchestrator(society=society, task=task, backend=backend).run()
    assert [turn.round for turn in result.turns] == [1, 1, 2, 2]


def test_turn_indices_are_deterministic() -> None:
    society = Society(
        agents=[_make_agent("a1"), _make_agent("a2")],
        topology=TopologyConfig(kind="ring"),
        number_of_rounds=2,
        speaker_order=SpeakerOrderConfig(order=["a1", "a2"], deterministic=True),
        visibility=VisibilityConfig(),
    )
    task = Task(task_id="task-5", question="Question?", ground_truth="Answer")
    backend = FakeBackend("fake-model", "fake-provider")

    result = Orchestrator(society=society, task=task, backend=backend).run()
    assert [turn.turn_index for turn in result.turns] == [1, 2, 1, 2]


def test_agent_order_follows_configured_speaker_order() -> None:
    society = Society(
        agents=[_make_agent("a1"), _make_agent("a2"), _make_agent("a3")],
        topology=TopologyConfig(kind="ring"),
        number_of_rounds=1,
        speaker_order=SpeakerOrderConfig(order=["a3", "a1", "a2"], deterministic=True),
        visibility=VisibilityConfig(),
    )
    task = Task(task_id="task-6", question="Question?", ground_truth="Answer")
    backend = FakeBackend("fake-model", "fake-provider")

    result = Orchestrator(society=society, task=task, backend=backend).run()
    assert [turn.agent_id for turn in result.turns] == ["a3", "a1", "a2"]


def test_task_is_passed_into_orchestration_process() -> None:
    society = Society(
        agents=[_make_agent("a1")],
        topology=TopologyConfig(kind="ring"),
        number_of_rounds=1,
        speaker_order=SpeakerOrderConfig(order=["a1"], deterministic=True),
        visibility=VisibilityConfig(),
    )
    task = Task(task_id="task-7", question="What now?", ground_truth="Answer")
    backend = FakeBackend("fake-model", "fake-provider")

    result = Orchestrator(society=society, task=task, backend=backend).run()
    assert result.task_id == task.task_id


def test_orchestrator_does_not_require_real_external_model() -> None:
    society = Society(
        agents=[_make_agent("a1")],
        topology=TopologyConfig(kind="ring"),
        number_of_rounds=1,
        speaker_order=SpeakerOrderConfig(order=["a1"], deterministic=True),
        visibility=VisibilityConfig(),
    )
    task = Task(task_id="task-8", question="Question?", ground_truth="Answer")
    backend = FakeBackend("fake-model", "fake-provider")

    result = Orchestrator(society=society, task=task, backend=backend).run()
    assert result.turns[0].provider == "fake-provider"


def test_invalid_or_empty_society_configuration_fails() -> None:
    with pytest.raises(ValueError):
        Orchestrator(
            society=None,
            task=Task(task_id="task-9", question="Question?", ground_truth="Answer"),
            backend=FakeBackend("fake-model", "fake-provider"),
        )

    with pytest.raises(ValidationError):
        Society(
            agents=[],
            topology=TopologyConfig(kind="ring"),
            number_of_rounds=1,
            speaker_order=SpeakerOrderConfig(order=["a1"], deterministic=True),
            visibility=VisibilityConfig(),
        )
