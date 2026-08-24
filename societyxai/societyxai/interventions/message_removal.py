from __future__ import annotations

import re
from typing import Any

from societyxai.interventions.base import BaseIntervention
from societyxai.traces.schema import InterventionTrace


class MessageRemovalIntervention(BaseIntervention):
    """Remove a specific message from the counterfactual branch context."""

    _MESSAGE_ID_RE = re.compile(r"^r(?P<round>\d+)_t(?P<turn>\d+)_(?P<agent>.+)$")

    def __init__(self, target_id: str):
        super().__init__(intervention_type="message_removal", target_id=target_id)
        match = self._MESSAGE_ID_RE.match(target_id)
        if match is None:
            raise ValueError(
                "message removal target_id must use the orchestrator message_id format "
                "r<round>_t<turn>_<agent_id>"
            )
        self.target_round = int(match.group("round"))
        self.target_turn_index = int(match.group("turn"))
        self.target_agent_id = match.group("agent")

    def should_apply(self, agent_id: str, round_num: int, turn_index: int) -> bool:
        return (
            agent_id == self.target_agent_id
            and round_num == self.target_round
            and turn_index == self.target_turn_index
        )

    def apply_to_messages(
        self,
        agent_id: str,
        messages: list[dict[str, Any]],
        round_num: int,
        turn_index: int,
    ) -> list[dict[str, Any]]:
        return messages

    def filter_visible_messages(
        self,
        agent_id: str,
        visible_messages: list[dict[str, Any]],
        all_messages: list[dict[str, Any]],
        round_num: int,
        turn_index: int,
    ) -> list[dict[str, Any]]:
        return [msg for msg in visible_messages if msg["message_id"] != self.target_id]

    def to_trace(self, branch_id: str | None = None) -> InterventionTrace:
        return InterventionTrace(
            intervention_type=self.intervention_type,
            target_id=self.target_id,
            branch_id=branch_id,
        )
