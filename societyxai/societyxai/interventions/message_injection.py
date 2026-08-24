from __future__ import annotations

from typing import Any

from societyxai.interventions.base import BaseIntervention
from societyxai.traces.schema import InterventionTrace


class MessageInjectionIntervention(BaseIntervention):
    """Injects a designated message into a target agent's conversation context.

    Targets a specific agent by *target_id* and optionally restricts injection
    to a specific round and/or turn index.
    """

    def __init__(
        self,
        target_id: str,
        injected_content: str,
        round: int = 1,
        turn_index: int | None = None,
        role: str = "user",
    ):
        super().__init__(intervention_type="message_injection", target_id=target_id)
        self.injected_content = injected_content
        self.round = round
        self.turn_index = turn_index
        self.role = role
        self.applied: bool = False

    def should_apply(self, agent_id: str, round_num: int, turn_index: int) -> bool:
        """Determine if the intervention targets this agent and turn."""
        if agent_id != self.target_id:
            return False
        if round_num != self.round:
            return False
        if self.turn_index is not None and turn_index != self.turn_index:
            return False
        return True

    def apply_to_messages(
        self,
        agent_id: str,
        messages: list[dict[str, Any]],
        round_num: int,
        turn_index: int,
    ) -> list[dict[str, Any]]:
        """Append the injected message to the messages list for the target agent."""
        if not self.should_apply(agent_id, round_num, turn_index):
            return messages

        self.applied = True
        new_messages = list(messages)
        new_messages.append({"role": self.role, "content": self.injected_content})
        return new_messages

    def to_trace(self, branch_id: str | None = None) -> InterventionTrace:
        """Create an InterventionTrace snapshot."""
        return InterventionTrace(
            intervention_type=self.intervention_type,
            target_id=self.target_id,
            branch_id=branch_id,
        )
