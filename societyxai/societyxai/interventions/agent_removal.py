from __future__ import annotations

from typing import Any

from societyxai.config.schema import TopologyConfig
from societyxai.core.society import Society
from societyxai.interventions.base import BaseIntervention
from societyxai.traces.schema import InterventionTrace


class AgentRemovalIntervention(BaseIntervention):
    """Remove a target agent from the counterfactual branch before replay."""

    def __init__(self, target_id: str):
        super().__init__(intervention_type="agent_removal", target_id=target_id)

    def prepare_society(self, society: Society) -> Society:
        """Return a deep-copied society with the target agent removed."""
        branch_society = society.model_copy(deep=True)
        agent_ids = [agent.agent_id for agent in branch_society.agents]
        if self.target_id not in agent_ids:
            raise ValueError(f"agent removal target not found in society: {self.target_id}")
        if len(agent_ids) <= 1:
            raise ValueError("agent removal requires at least one remaining agent")

        old_order = list(branch_society.speaker_order.order)
        branch_society.agents = [agent for agent in branch_society.agents if agent.agent_id != self.target_id]
        branch_society.speaker_order.order = [
            agent_id for agent_id in branch_society.speaker_order.order if agent_id != self.target_id
        ]

        topology = branch_society.topology
        if topology.adjacency is None:
            return branch_society

        remaining_order = branch_society.speaker_order.order
        old_index = {agent_id: index for index, agent_id in enumerate(old_order)}
        new_index = {agent_id: index for index, agent_id in enumerate(remaining_order)}

        if len(topology.adjacency) != len(old_order):
            raise ValueError("adjacency matrix does not match the society agent count")

        adjusted_adjacency: list[list[int]] = []
        for agent_id in remaining_order:
            row = topology.adjacency[old_index[agent_id]]
            adjusted_row = [
                new_index[old_order[column]]
                for column in row
                if 0 <= column < len(old_order) and old_order[column] != self.target_id
            ]
            adjusted_adjacency.append(adjusted_row)

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
