from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from societyxai.traces.schema import InterventionTrace

if TYPE_CHECKING:
    from societyxai.core.society import Society


class BaseIntervention(ABC):
    """Abstract base interface for SocietyXAI interventions."""

    def __init__(self, intervention_type: str, target_id: str):
        self.intervention_type = intervention_type
        self.target_id = target_id

    def prepare_society(self, society: Society) -> Society:
        """Return the branch-specific society state before replay starts."""
        return society

    def filter_visible_messages(
        self,
        agent_id: str,
        visible_messages: list[dict[str, Any]],
        all_messages: list[dict[str, Any]],
        round_num: int,
        turn_index: int,
    ) -> list[dict[str, Any]]:
        """Optionally filter the messages visible to a branch agent turn."""
        return visible_messages

    @abstractmethod
    def should_apply(self, agent_id: str, round_num: int, turn_index: int) -> bool:
        """Check whether this intervention should trigger for the given turn."""
        raise NotImplementedError

    @abstractmethod
    def apply_to_messages(
        self,
        agent_id: str,
        messages: list[dict[str, Any]],
        round_num: int,
        turn_index: int,
    ) -> list[dict[str, Any]]:
        """Transform or inject content into the agent's context messages."""
        raise NotImplementedError

    @abstractmethod
    def to_trace(self, branch_id: str | None = None) -> InterventionTrace:
        """Construct an InterventionTrace representing this intervention."""
        raise NotImplementedError
