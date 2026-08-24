from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TopologyConfig(BaseModel):
    """Explicit topology description for a multi-agent discussion setup."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["ring", "star", "complete", "line", "custom"] = "ring"
    adjacency: list[list[int]] | None = None

    @field_validator("adjacency")
    @classmethod
    def validate_adjacency(cls, value: list[list[int]] | None) -> list[list[int]] | None:
        if value is None:
            return value
        if not all(isinstance(row, list) for row in value):
            raise ValueError("adjacency must be a list of integer lists")
        for row in value:
            if not all(isinstance(node, int) for node in row):
                raise ValueError("adjacency rows must contain integers only")
        return value


class SpeakerOrderConfig(BaseModel):
    """Deterministic speaker ordering for rounds."""

    model_config = ConfigDict(extra="forbid")

    order: list[str] = Field(default_factory=list)
    deterministic: bool = True

    @field_validator("order")
    @classmethod
    def validate_order(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("speaker_order order must not be empty")
        if len(set(value)) != len(value):
            raise ValueError("speaker_order contains duplicate agent identifiers")
        return value


class VisibilityConfig(BaseModel):
    """Controls which information is visible to agents during a round."""

    model_config = ConfigDict(extra="forbid")

    previous_messages: bool = True
    confidence: bool = False
    majority_position: bool = False


class InterventionConfig(BaseModel):
    """Minimal intervention specification for experimentation."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    injected_content: str | None = None
    round: int | None = None
    target_order: list[str] | None = None
    visible: bool | None = None


class InitialBeliefSpec(BaseModel):
    """Lightweight schema for specifying pre-round initial beliefs in YAML.

    This intentionally mirrors the runtime BeliefState fields without importing
    the runtime class to avoid import cycles.
    """

    model_config = ConfigDict(extra="forbid")

    position: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_ids: list[str] = Field(default_factory=list)
    reasoning_trace: str = ""


class ExperimentConfig(BaseModel):
    """Validated schema describing a complete SocietyXAI experiment run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    seed: int
    model_id: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    temperature: float = Field(ge=0)
    max_tokens: int = Field(gt=0)
    system_prompt: str = Field(min_length=1)
    system_prompt_hash: str | None = None
    number_of_agents: int = Field(gt=0)
    number_of_rounds: int = Field(gt=0)
    topology: TopologyConfig
    speaker_order: SpeakerOrderConfig
    visibility: VisibilityConfig
    intervention: InterventionConfig
    parser_version: str = Field(min_length=1)
    stopping_rule: str = Field(min_length=1)
    agent_models: dict[str, str] | None = None
    agent_roles: dict[str, str] | None = None
    agent_prompts: dict[str, str] | None = None
    architecture: str | None = None
    adjudicator_ids: list[str] | None = None
    initial_beliefs: dict[str, InitialBeliefSpec] | None = None

    @field_validator("seed")
    @classmethod
    def validate_seed(cls, value: int) -> int:
        return int(value)

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, value: float) -> float:
        if value < 0:
            raise ValueError("temperature must be non-negative")
        return float(value)

    @field_validator("speaker_order")
    @classmethod
    def validate_speaker_count(cls, value: SpeakerOrderConfig, info: object) -> SpeakerOrderConfig:
        data = info.data if hasattr(info, "data") else {}
        expected_agents = data.get("number_of_agents")
        if expected_agents is not None and len(value.order) != expected_agents:
            raise ValueError("speaker_order length must match number_of_agents")
        return value

    @field_validator("agent_models")
    @classmethod
    def validate_agent_models_keys(cls, value: dict[str, str] | None, info: object) -> dict[str, str] | None:
        if value is None:
            return value
        data = info.data if hasattr(info, "data") else {}
        speaker_order = data.get("speaker_order")
        if speaker_order is not None:
            known_ids = set(speaker_order.order) if hasattr(speaker_order, "order") else set()
            unknown = set(value.keys()) - known_ids
            if unknown:
                raise ValueError(
                    f"agent_models references unknown agent IDs: {sorted(unknown)}"
                )
        return value

    @field_validator("initial_beliefs")
    @classmethod
    def validate_initial_beliefs_keys(cls, value: dict[str, InitialBeliefSpec] | None, info: object) -> dict[str, InitialBeliefSpec] | None:
        """Ensure any initial_beliefs keys reference valid speaker_order agent IDs."""
        if value is None:
            return value
        data = info.data if hasattr(info, "data") else {}
        speaker_order = data.get("speaker_order")
        if speaker_order is not None:
            known_ids = set(speaker_order.order) if hasattr(speaker_order, "order") else set()
            unknown = set(value.keys()) - known_ids
            if unknown:
                raise ValueError(
                    f"initial_beliefs references unknown agent IDs: {sorted(unknown)}"
                )
        return value

    @field_validator("agent_roles")
    @classmethod
    def validate_agent_roles_keys(cls, value: dict[str, str] | None, info: object) -> dict[str, str] | None:
        if value is None:
            return value
        data = info.data if hasattr(info, "data") else {}
        speaker_order = data.get("speaker_order")
        if speaker_order is not None:
            known_ids = set(speaker_order.order) if hasattr(speaker_order, "order") else set()
            unknown = set(value.keys()) - known_ids
            if unknown:
                raise ValueError(
                    f"agent_roles references unknown agent IDs: {sorted(unknown)}"
                )
        return value

    @field_validator("adjudicator_ids")
    @classmethod
    def validate_adjudicator_ids(cls, value: list[str] | None, info: object) -> list[str] | None:
        if value is None:
            return value
        data = info.data if hasattr(info, "data") else {}
        speaker_order = data.get("speaker_order")
        if speaker_order is not None:
            known_ids = set(speaker_order.order) if hasattr(speaker_order, "order") else set()
            unknown = set(value) - known_ids
            if unknown:
                raise ValueError(
                    f"adjudicator_ids references unknown agent IDs: {sorted(unknown)}"
                )
        return value
