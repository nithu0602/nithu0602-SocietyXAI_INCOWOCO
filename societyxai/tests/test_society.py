import pytest
from pydantic import ValidationError

from societyxai.config.schema import SpeakerOrderConfig, TopologyConfig, VisibilityConfig
from societyxai.core import Agent, Society


def _make_agent(agent_id: str, model_id: str = "model-a") -> Agent:
    return Agent(
        agent_id=agent_id,
        role="speaker",
        model_id=model_id,
        system_prompt="You are a helpful assistant.",
    )


def test_valid_society_can_be_created() -> None:
    society = Society(
        agents=[_make_agent("agent_1"), _make_agent("agent_2")],
        topology=TopologyConfig(kind="ring"),
        number_of_rounds=3,
        speaker_order=SpeakerOrderConfig(order=["agent_1", "agent_2"], deterministic=True),
        visibility=VisibilityConfig(previous_messages=True, confidence=True, majority_position=False),
    )
    assert len(society.agents) == 2
    assert society.number_of_rounds == 3


def test_society_requires_at_least_one_agent() -> None:
    with pytest.raises(ValidationError):
        Society(
            agents=[],
            topology=TopologyConfig(kind="ring"),
            number_of_rounds=3,
            speaker_order=SpeakerOrderConfig(order=["agent_1"], deterministic=True),
            visibility=VisibilityConfig(),
        )


def test_empty_agent_list_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Society(
            agents=[],
            topology=TopologyConfig(kind="ring"),
            number_of_rounds=2,
            speaker_order=SpeakerOrderConfig(order=["agent_1"], deterministic=True),
            visibility=VisibilityConfig(),
        )


def test_zero_rounds_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Society(
            agents=[_make_agent("agent_1")],
            topology=TopologyConfig(kind="ring"),
            number_of_rounds=0,
            speaker_order=SpeakerOrderConfig(order=["agent_1"], deterministic=True),
            visibility=VisibilityConfig(),
        )


def test_negative_rounds_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Society(
            agents=[_make_agent("agent_1")],
            topology=TopologyConfig(kind="ring"),
            number_of_rounds=-1,
            speaker_order=SpeakerOrderConfig(order=["agent_1"], deterministic=True),
            visibility=VisibilityConfig(),
        )


def test_multiple_agents_can_exist_in_one_society() -> None:
    agents = [_make_agent("agent_1"), _make_agent("agent_2"), _make_agent("agent_3")]
    society = Society(
        agents=agents,
        topology=TopologyConfig(kind="complete"),
        number_of_rounds=4,
        speaker_order=SpeakerOrderConfig(order=["agent_1", "agent_2", "agent_3"], deterministic=True),
        visibility=VisibilityConfig(previous_messages=True, confidence=False, majority_position=True),
    )
    assert len(society.agents) == 3


def test_existing_topology_configuration_can_be_used() -> None:
    topology = TopologyConfig(kind="line", adjacency=[[1], [0, 2], [1]])
    society = Society(
        agents=[_make_agent("agent_1"), _make_agent("agent_2"), _make_agent("agent_3")],
        topology=topology,
        number_of_rounds=2,
        speaker_order=SpeakerOrderConfig(order=["agent_1", "agent_2", "agent_3"], deterministic=True),
        visibility=VisibilityConfig(),
    )
    assert society.topology.kind == "line"


def test_existing_speaker_order_configuration_can_be_used() -> None:
    speaker_order = SpeakerOrderConfig(order=["agent_1", "agent_2"], deterministic=True)
    society = Society(
        agents=[_make_agent("agent_1"), _make_agent("agent_2")],
        topology=TopologyConfig(kind="star"),
        number_of_rounds=2,
        speaker_order=speaker_order,
        visibility=VisibilityConfig(),
    )
    assert society.speaker_order.order == ["agent_1", "agent_2"]


def test_existing_visibility_configuration_can_be_used() -> None:
    visibility = VisibilityConfig(previous_messages=True, confidence=True, majority_position=False)
    society = Society(
        agents=[_make_agent("agent_1")],
        topology=TopologyConfig(kind="ring"),
        number_of_rounds=1,
        speaker_order=SpeakerOrderConfig(order=["agent_1"], deterministic=True),
        visibility=visibility,
    )
    assert society.visibility.confidence is True


def test_societies_do_not_share_mutable_agent_lists() -> None:
    society_1 = Society(
        agents=[_make_agent("agent_1")],
        topology=TopologyConfig(kind="ring"),
        number_of_rounds=1,
        speaker_order=SpeakerOrderConfig(order=["agent_1"], deterministic=True),
        visibility=VisibilityConfig(),
    )
    society_2 = Society(
        agents=[_make_agent("agent_2")],
        topology=TopologyConfig(kind="ring"),
        number_of_rounds=1,
        speaker_order=SpeakerOrderConfig(order=["agent_2"], deterministic=True),
        visibility=VisibilityConfig(),
    )

    society_1.agents.append(_make_agent("agent_3"))
    assert len(society_2.agents) == 1
