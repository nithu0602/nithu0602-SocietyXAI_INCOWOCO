"""Default keyword-based belief parser."""
from __future__ import annotations

from societyxai.parsers.base import BeliefParser
from societyxai.traces.schema import BeliefState


class HeuristicBeliefParser(BeliefParser):
    """Keyword-based belief extraction.

    Preserves the original ``Orchestrator._extract_belief`` behaviour:
    support/reject/neutral based on substring matching, confidence always 1.0,
    no evidence or reasoning captured.
    """

    def parse(self, response: str) -> BeliefState:
        lower = response.lower()
        if any(w in lower for w in ("support", "agree", "approve", "yes")):
            position = "support"
        elif any(w in lower for w in ("reject", "disagree", "oppose", "no")):
            position = "reject"
        else:
            position = "neutral"
        return BeliefState(position=position, confidence=1.0, evidence_ids=[])
