from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from societyxai.config.schema import TopologyConfig, VisibilityConfig


class BeliefState(BaseModel):
    """Operational belief representation for an agent at a point in time."""

    model_config = ConfigDict(extra="forbid")

    position: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    reasoning_trace: str = ""


class AgentTrace(BaseModel):
    """State snapshot for a single agent during a round/turn."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    model_id: str | None = None
    provider: str | None = None
    capability_score: float | None = None
    social_style: str | None = None
    round: int = Field(ge=0)
    turn_index: int = Field(ge=0)
    belief: BeliefState
    received_message_ids: list[str] = Field(default_factory=list)
    cited_agent_ids: list[str] = Field(default_factory=list)
    exposed_majority_position: str | None = None


class MessageTrace(BaseModel):
    """A message emitted as part of the discussion."""

    model_config = ConfigDict(extra="forbid")

    message_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    model_id: str | None = None
    provider: str | None = None
    round: int = Field(ge=0)
    turn_index: int = Field(ge=0)
    content: str = Field(min_length=1)
    parent_message_ids: list[str] = Field(default_factory=list)
    content_hash: str | None = None
    intervention_status: str | None = None


class InterventionTrace(BaseModel):
    """Optional intervention metadata attached to an experiment run."""

    model_config = ConfigDict(extra="forbid")

    intervention_type: str | None = None
    target_id: str | None = None
    branch_id: str | None = None


class RunTrace(BaseModel):
    """Complete machine-readable trace for a SocietyXAI experiment run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    seed: int
    timestamp: datetime
    model_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    temperature: float = Field(ge=0.0)
    system_prompt_hash: str | None = None
    topology: TopologyConfig
    speaker_order: list[str] | None = None
    visibility: VisibilityConfig | None = None
    initial_beliefs: dict[str, BeliefState] | None = None
    ground_truth: str | None = None
    agent_traces: list[AgentTrace] = Field(default_factory=list)
    message_traces: list[MessageTrace] = Field(default_factory=list)
    intervention: InterventionTrace | None = None
    final_decision: str | None = None
    correctness: bool | None = None

    def save(self, directory: str | Path = "runs", filename: str | None = None) -> Path:
        """Serialize this RunTrace to JSON and write to disk."""
        from societyxai.traces.persistence import save_trace

        return save_trace(self, directory=directory, filename=filename)

    @classmethod
    def load(cls, path: str | Path) -> RunTrace:
        """Load and validate a RunTrace from a JSON file."""
        from societyxai.traces.persistence import load_trace

        return load_trace(path)


__all__ = [
    "BeliefState",
    "AgentTrace",
    "MessageTrace",
    "InterventionTrace",
    "RunTrace",
]
