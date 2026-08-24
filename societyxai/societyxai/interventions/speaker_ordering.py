from __future__ import annotations

from typing import Any

from societyxai.config.schema import TopologyConfig
from societyxai.core.society import Society
from societyxai.interventions.base import BaseIntervention
from societyxai.traces.schema import InterventionTrace


class SpeakerOrderingIntervention(BaseIntervention):
    """Apply a controlled speaker order permutation to the counterfactual branch."""

    def __init__(self, target_order: list[str]):
        if not target_order:
            raise ValueError("target_order must not be empty")
        super().__init__(intervention_type="speaker_ordering", target_id="speaker_order")
        self.target_order = list(target_order)

    def prepare_society(self, society: Society) -> Society:
        branch_society = society.model_copy(deep=True)
        current_order = list(branch_society.speaker_order.order)
        if len(self.target_order) != len(current_order):
            raise ValueError("speaker order permutation must contain the same agent IDs")
        if set(self.target_order) != set(current_order):
            raise ValueError("speaker order permutation must contain the same agent IDs")
        if len(set(self.target_order)) != len(self.target_order):
            raise ValueError("speaker order permutation must not contain duplicates")

        topology = branch_society.topology
        if topology.adjacency is None:
            branch_society.speaker_order.order = list(self.target_order)
            return branch_society

        old_index = {agent_id: index for index, agent_id in enumerate(current_order)}
        new_index = {agent_id: index for index, agent_id in enumerate(self.target_order)}
        if len(topology.adjacency) != len(current_order):
            raise ValueError("adjacency matrix does not match the society agent count")

        adjusted_adjacency: list[list[int]] = []
        for agent_id in self.target_order:
            row = topology.adjacency[old_index[agent_id]]
            adjusted_row = [new_index[current_order[column]] for column in row if 0 <= column < len(current_order)]
            adjusted_adjacency.append(adjusted_row)

        branch_society.speaker_order.order = list(self.target_order)
        branch_society.topology = TopologyConfig(kind=topology.kind, adjacency=adjusted_adjacency)
        return branch_society

    def should_apply(self, agent_id: str, round_num: int, turn_index: int) -> bool:
        return False

    def apply_to_messages(
        self,
        agent_id: str,
        messages: list[dict[str, Any]],
        round_num: int,
        turn_index: int,
    ) -> list[dict[str, Any]]:
        return messages

    def to_trace(self, branch_id: str | None = None) -> InterventionTrace:
        return InterventionTrace(
            intervention_type=self.intervention_type,
            target_id=self.target_id,
            branch_id=branch_id,
        )
