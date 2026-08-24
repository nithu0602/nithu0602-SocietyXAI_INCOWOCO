from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from societyxai.traces.schema import BeliefState


class SocialStyle(BaseModel):
    """Simple structured metadata for an agent's communication tendencies."""

    model_config = ConfigDict(extra="forbid")

    assertiveness: float = Field(ge=0.0, le=1.0)
    verbosity: float = Field(ge=0.0, le=1.0)
    confidence_style: float = Field(ge=0.0, le=1.0)


class Agent(BaseModel):
    """Operational state container for a SocietyXAI agent."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str = Field(min_length=1)
    role: str = Field(min_length=1)
    model_id: str = Field(min_length=1)
    system_prompt: str = Field(min_length=1)
    capability_score: float | None = Field(default=None, ge=0.0, le=1.0)
    social_style: SocialStyle = Field(default_factory=lambda: SocialStyle(
        assertiveness=0.5,
        verbosity=0.5,
        confidence_style=0.5,
    ))
    current_belief: BeliefState | None = None
    belief_history: list[BeliefState] = Field(default_factory=list)
    received_message_ids: list[str] = Field(default_factory=list)

    @field_validator("belief_history")
    @classmethod
    def validate_belief_history(cls, value: list[BeliefState]) -> list[BeliefState]:
        return value

    @field_validator("received_message_ids")
    @classmethod
    def validate_received_message_ids(cls, value: list[str]) -> list[str]:
        return value
