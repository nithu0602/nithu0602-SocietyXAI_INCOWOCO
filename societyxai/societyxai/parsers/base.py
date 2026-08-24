"""Abstract base for belief parsers."""
from __future__ import annotations

from abc import ABC, abstractmethod

from societyxai.traces.schema import BeliefState


class BeliefParser(ABC):
    """Protocol for converting a raw model response string into a BeliefState."""

    @abstractmethod
    def parse(self, response: str) -> BeliefState:
        """Return a BeliefState derived from *response*."""
