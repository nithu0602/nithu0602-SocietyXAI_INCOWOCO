from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from societyxai.config.schema import SpeakerOrderConfig, TopologyConfig, VisibilityConfig
from societyxai.core.agent import Agent


class Society(BaseModel):
    """Operational container for agents and communication configuration."""

    model_config = ConfigDict(extra="forbid")

    agents: list[Agent] = Field(default_factory=list)
    topology: TopologyConfig
    number_of_rounds: int = Field(gt=0)
    speaker_order: SpeakerOrderConfig
    visibility: VisibilityConfig

    @field_validator("agents")
    @classmethod
    def validate_agents(cls, value: list[Agent]) -> list[Agent]:
        if not value:
            raise ValueError("society must contain at least one agent")
        return value
