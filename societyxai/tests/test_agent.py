import pytest
from pydantic import ValidationError

from societyxai.core import Agent, SocialStyle
from societyxai.traces.schema import BeliefState


def test_valid_agent_can_be_created() -> None:
    agent = Agent(
        agent_id="agent_1",
        role="speaker",
        model_id="model-a",
        system_prompt="You are a helpful assistant.",
        capability_score=0.8,
        social_style={
            "assertiveness": 0.7,
            "verbosity": 0.6,
            "confidence_style": 0.8,
        },
        current_belief=BeliefState(
            position="agree",
            confidence=0.75,
            evidence_ids=["e1"],
            reasoning_trace="The evidence is persuasive.",
        ),
    )
    assert agent.agent_id == "agent_1"
    assert agent.current_belief is not None


def test_agent_id_is_required() -> None:
    with pytest.raises(ValidationError):
        Agent(
            role="speaker",
            model_id="model-a",
            system_prompt="You are a helpful assistant.",
        )


def test_role_is_required() -> None:
    with pytest.raises(ValidationError):
        Agent(
            agent_id="agent_1",
            model_id="model-a",
            system_prompt="You are a helpful assistant.",
        )


def test_model_id_is_required() -> None:
    with pytest.raises(ValidationError):
        Agent(
            agent_id="agent_1",
            role="speaker",
            system_prompt="You are a helpful assistant.",
        )


def test_system_prompt_is_required() -> None:
    with pytest.raises(ValidationError):
        Agent(
            agent_id="agent_1",
            role="speaker",
            model_id="model-a",
            system_prompt="",
        )


def test_capability_score_accepts_valid_values() -> None:
    agent = Agent(
        agent_id="agent_2",
        role="critic",
        model_id="model-b",
        system_prompt="Evaluate carefully.",
        capability_score=0.55,
    )
    assert agent.capability_score == 0.55


def test_capability_score_outside_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Agent(
            agent_id="agent_3",
            role="critic",
            model_id="model-b",
            system_prompt="Evaluate carefully.",
            capability_score=1.5,
        )


def test_social_style_values_are_validated() -> None:
    social = SocialStyle(assertiveness=0.9, verbosity=0.2, confidence_style=0.8)
    assert social.assertiveness == 0.9

    with pytest.raises(ValidationError):
        SocialStyle(assertiveness=1.2, verbosity=0.2, confidence_style=0.8)


def test_current_belief_can_be_a_belief_state() -> None:
    belief = BeliefState(
        position="support",
        confidence=0.65,
        evidence_ids=["e1", "e2"],
        reasoning_trace="Current argument is plausible.",
    )
    agent = Agent(
        agent_id="agent_4",
        role="analyst",
        model_id="model-c",
        system_prompt="Analyze the evidence.",
        current_belief=belief,
    )
    assert agent.current_belief == belief


def test_current_belief_defaults_to_none() -> None:
    agent = Agent(
        agent_id="agent_5",
        role="analyst",
        model_id="model-c",
        system_prompt="Analyze the evidence.",
    )
    assert agent.current_belief is None


def test_belief_history_defaults_to_empty_list() -> None:
    agent = Agent(
        agent_id="agent_6",
        role="analyst",
        model_id="model-c",
        system_prompt="Analyze the evidence.",
    )
    assert agent.belief_history == []


def test_received_message_ids_defaults_to_empty_list() -> None:
    agent = Agent(
        agent_id="agent_7",
        role="speaker",
        model_id="model-d",
        system_prompt="Speak clearly.",
    )
    assert agent.received_message_ids == []


def test_agents_do_not_share_mutable_default_lists() -> None:
    agent_1 = Agent(
        agent_id="agent_8",
        role="speaker",
        model_id="model-x",
        system_prompt="Speak clearly.",
    )
    agent_2 = Agent(
        agent_id="agent_9",
        role="speaker",
        model_id="model-y",
        system_prompt="Speak clearly.",
    )

    agent_1.received_message_ids.append("m-1")
    agent_1.belief_history.append(
        BeliefState(
            position="neutral",
            confidence=0.5,
            evidence_ids=[],
            reasoning_trace="Pending.",
        )
    )

    assert agent_2.received_message_ids == []
    assert agent_2.belief_history == []
