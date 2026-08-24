import pytest
from pydantic import ValidationError

from societyxai.tasks import EvidenceItem, Task


def test_valid_task_can_be_created() -> None:
    task = Task(
        task_id="task-001",
        question="What is the likely outcome?",
        ground_truth="The system converges on approval.",
        choices=["approval", "rejection"],
        difficulty="medium",
        evidence=[
            EvidenceItem(
                evidence_id="e1",
                content="Evidence summary one.",
                source="source-a",
            )
        ],
        reference_solution="Approval is the correct answer.",
        metadata={"domain": "politics", "task_type": "consensus"},
    )
    assert task.task_id == "task-001"
    assert task.choices == ["approval", "rejection"]
    assert task.evidence[0].evidence_id == "e1"


def test_empty_task_id_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Task(
            task_id="",
            question="What happened?",
            ground_truth="It was resolved.",
        )


def test_empty_question_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Task(
            task_id="task-002",
            question="",
            ground_truth="It was resolved.",
        )


def test_empty_ground_truth_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Task(
            task_id="task-003",
            question="What happened?",
            ground_truth="",
        )


def test_evidence_item_works() -> None:
    evidence = EvidenceItem(
        evidence_id="ev-1",
        content="The proposal had broad support.",
        source="source-1",
    )
    assert evidence.content == "The proposal had broad support."
    assert evidence.source == "source-1"


def test_task_can_contain_multiple_evidence_items() -> None:
    task = Task(
        task_id="task-004",
        question="Who is most likely to support the measure?",
        ground_truth="Agent 2 supports it.",
        evidence=[
            EvidenceItem(evidence_id="ev-1", content="Agent 1 is hesitant."),
            EvidenceItem(evidence_id="ev-2", content="Agent 2 expresses support."),
        ],
    )
    assert len(task.evidence) == 2
    assert task.evidence[1].evidence_id == "ev-2"


def test_optional_difficulty_works() -> None:
    task = Task(
        task_id="task-005",
        question="Is the result stable?",
        ground_truth="Yes.",
    )
    assert task.difficulty is None


def test_optional_reference_solution_works() -> None:
    task = Task(
        task_id="task-006",
        question="Choose the correct decision.",
        ground_truth="Decision A.",
        reference_solution="Decision A is the expected answer.",
    )
    assert task.reference_solution == "Decision A is the expected answer."


def test_pydantic_serialization_works() -> None:
    task = Task(
        task_id="task-007",
        question="Which party should win?",
        ground_truth="Party B.",
        evidence=[EvidenceItem(evidence_id="ev-1", content="Party B has more support.")],
        metadata={"domain": "elections", "task_type": "ranking"},
    )
    payload = task.model_dump()
    assert payload["task_id"] == "task-007"
    assert payload["ground_truth"] == "Party B."
    assert payload["evidence"][0]["evidence_id"] == "ev-1"
