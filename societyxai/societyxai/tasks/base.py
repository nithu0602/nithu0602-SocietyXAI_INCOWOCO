from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceItem(BaseModel):
    """A single item of evidence supplied to a task."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1)
    content: str = Field(min_length=1)
    source: str | None = None


class Task(BaseModel):
    """Minimal research task abstraction for SocietyXAI."""

    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    ground_truth: str = Field(min_length=1)
    choices: list[str] | None = None
    difficulty: str | None = None
    evidence: list[EvidenceItem] = Field(default_factory=list)
    reference_solution: str | None = None
    metadata: dict[str, Any] | None = None
