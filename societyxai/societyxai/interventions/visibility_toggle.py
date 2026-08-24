from __future__ import annotations

from typing import Any

from societyxai.core.society import Society
from societyxai.interventions.base import BaseIntervention
from societyxai.traces.schema import InterventionTrace


class VisibilityToggleIntervention(BaseIntervention):
    """Toggle a single visibility flag for the counterfactual branch."""

    def __init__(self, visibility_field: str, visible: bool):
        if visibility_field not in {"confidence", "majority_position"}:
            raise ValueError("visibility_field must be 'confidence' or 'majority_position'")
        super().__init__(intervention_type=f"{visibility_field}_visibility", target_id=visibility_field)
        self.visibility_field = visibility_field
        self.visible = visible

    def prepare_society(self, society: Society) -> Society:
        branch_society = society.model_copy(deep=True)
        setattr(branch_society.visibility, self.visibility_field, self.visible)
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


class ConfidenceVisibilityIntervention(VisibilityToggleIntervention):
    def __init__(self, visible: bool):
        super().__init__("confidence", visible)


class MajorityVisibilityIntervention(VisibilityToggleIntervention):
    def __init__(self, visible: bool):
        super().__init__("majority_position", visible)
