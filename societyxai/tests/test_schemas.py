from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from societyxai.traces import AgentTrace, BeliefState, InterventionTrace, MessageTrace, RunTrace


def test_valid_belief_state() -> None:
    belief = BeliefState(
        position="agree",
        confidence=0.78,
        evidence_ids=["e1", "e2"],
        reasoning_trace="The evidence supports the proposal.",
    )
    assert belief.position == "agree"
    assert belief.confidence == 0.78


def test_confidence_below_zero_is_rejected() -> None:
    with pytest.raises(ValidationError):
        BeliefState(
            position="reject",
            confidence=-0.01,
            evidence_ids=[],
            reasoning_trace="",
        )


def test_confidence_above_one_is_rejected() -> None:
    with pytest.raises(ValidationError):
        BeliefState(
            position="reject",
            confidence=1.01,
            evidence_ids=[],
            reasoning_trace="",
        )


def test_valid_agent_trace() -> None:
    agent = AgentTrace(
        agent_id="agent_0",
        role="moderator",
        capability_score=0.92,
        social_style="collaborative",
        round=1,
        turn_index=0,
        belief=BeliefState(
            position="neutral",
            confidence=0.5,
            evidence_ids=["e3"],
            reasoning_trace="We need more information.",
        ),
        received_message_ids=["m_1", "m_2"],
        cited_agent_ids=["agent_1"],
    )
    assert agent.role == "moderator"
    assert agent.round == 1


def test_negative_round_is_rejected() -> None:
    with pytest.raises(ValidationError):
        AgentTrace(
            agent_id="agent_0",
            role="speaker",
            round=-1,
            turn_index=0,
            belief=BeliefState(
                position="support",
                confidence=0.7,
                evidence_ids=[],
                reasoning_trace="Reasoning text",
            ),
            received_message_ids=[],
            cited_agent_ids=[],
        )


def test_valid_message_trace() -> None:
    message = MessageTrace(
        message_id="m_001",
        agent_id="agent_1",
        round=2,
        turn_index=1,
        content="I think the proposal is reasonable.",
        parent_message_ids=["m_000"],
        content_hash="abc123",
        intervention_status="none",
    )
    assert message.agent_id == "agent_1"
    assert message.content_hash == "abc123"


def test_valid_intervention_trace() -> None:
    intervention = InterventionTrace(
        intervention_type="message_injection",
        target_id="agent_2",
        branch_id="branch-a",
    )
    assert intervention.target_id == "agent_2"


def test_valid_complete_run_trace() -> None:
    run = RunTrace(
        run_id="run_001",
        task_id="task_001",
        seed=42,
        timestamp=datetime.now(timezone.utc),
        model_id="gpt-4o-mini",
        provider="openai",
        temperature=0.7,
        system_prompt_hash="hash-1",
        topology={"kind": "ring", "adjacency": [[1, 2], [2, 0], [0, 1]]},
        agent_traces=[
            AgentTrace(
                agent_id="agent_0",
                role="speaker",
                round=0,
                turn_index=0,
                belief=BeliefState(
                    position="support",
                    confidence=0.8,
                    evidence_ids=["e1"],
                    reasoning_trace="Support is justified.",
                ),
                received_message_ids=[],
                cited_agent_ids=[],
            )
        ],
        message_traces=[
            MessageTrace(
                message_id="m_0",
                agent_id="agent_0",
                round=0,
                turn_index=0,
                content="I support the idea.",
                parent_message_ids=[],
            )
        ],
        intervention=InterventionTrace(
            intervention_type="message_injection",
            target_id="agent_0",
            branch_id="b1",
        ),
        final_decision="support",
        correctness=True,
    )
    assert run.final_decision == "support"
    assert run.correctness is True


def test_optional_intervention_works() -> None:
    run = RunTrace(
        run_id="run_002",
        task_id="task_002",
        seed=7,
        timestamp=datetime.now(timezone.utc),
        model_id="gpt-4o-mini",
        provider="openai",
        temperature=0.9,
        topology={"kind": "complete"},
        agent_traces=[],
        message_traces=[],
    )
    assert run.intervention is None


def test_optional_final_decision_and_correctness_work() -> None:
    run = RunTrace(
        run_id="run_003",
        task_id="task_003",
        seed=11,
        timestamp=datetime.now(timezone.utc),
        model_id="gpt-4o-mini",
        provider="openai",
        temperature=0.2,
        topology={"kind": "line"},
        agent_traces=[],
        message_traces=[],
    )
    assert run.final_decision is None
    assert run.correctness is None


def test_pydantic_serialization_works() -> None:
    belief = BeliefState(
        position="agree",
        confidence=0.9,
        evidence_ids=["e1"],
        reasoning_trace="Solid reasoning.",
    )
    payload = belief.model_dump()
    assert payload["position"] == "agree"
    assert payload["confidence"] == 0.9
    assert payload["evidence_ids"] == ["e1"]
