"""Structured JSON belief parser with heuristic fallback."""
from __future__ import annotations

import json
from typing import Any

from societyxai.parsers.base import BeliefParser
from societyxai.parsers.heuristic import HeuristicBeliefParser
from societyxai.traces.schema import BeliefState
from societyxai.utils.positions import normalize_position


class StructuredBeliefParser(BeliefParser):
    """Parse model output as structured JSON, falling back to the heuristic parser.

    Expected JSON shape::

        {
            "position": "support",
            "confidence": 0.85,
            "evidence_ids": ["e1"],
            "reasoning_trace": "..."
        }

    If the output is not valid JSON, contains unexpected fields, or fails
    ``BeliefState`` validation, the heuristic parser is invoked instead of
    raising an error.
    """

    def __init__(self, *, strict: bool = False) -> None:
        self._strict = strict
        self._fallback = HeuristicBeliefParser()

    def parse(self, response: str) -> BeliefState:
        parsed = self._try_parse_json(response)
        if parsed is not None:
            mapped = normalize_position(parsed.position)
            if mapped in {"support", "reject", "neutral"}:
                parsed.position = mapped
            return parsed
        if self._strict:
            raise ValueError(
                "StructuredBeliefParser received unparseable response "
                "and is configured in strict mode"
            )
        return self._fallback.parse(response)

    # ------------------------------------------------------------------

    @staticmethod
    def _try_parse_json(response: str) -> BeliefState | None:
        """Attempt to extract a ``BeliefState`` from JSON in *response*.

        Returns ``None`` if parsing or validation fails.
        """
        raw: Any = None
        try:
            raw = json.loads(response)
        except (json.JSONDecodeError, TypeError):
            return None

        if not isinstance(raw, dict):
            return None

        try:
            position: str = raw["position"]
            confidence: float = raw["confidence"]
            evidence_ids: list[str] = raw.get("evidence_ids", [])
            reasoning_trace: str = raw.get("reasoning_trace", "")
        except (KeyError, TypeError):
            return None

        if not isinstance(position, str) or not position:
            return None
        if not isinstance(confidence, (int, float)):
            return None
        if not isinstance(evidence_ids, list):
            return None
        if not isinstance(reasoning_trace, str):
            return None

        try:
            return BeliefState(
                position=position,
                confidence=float(confidence),
                evidence_ids=evidence_ids,
                reasoning_trace=reasoning_trace,
            )
        except Exception:
            return None
