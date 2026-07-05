"""Base class every agent inherits from."""

from __future__ import annotations

from abc import ABC, abstractmethod

from ..config import Signal
from ..data import AssetData


class BaseAgent(ABC):
    """An agent looks at one asset and returns a Signal.

    Attributes:
        name: human-readable name shown in reports.
        weight: relative influence in the committee vote (default 1.0).
    """

    name: str = "BaseAgent"
    weight: float = 1.0

    @abstractmethod
    def analyze(self, asset: AssetData) -> Signal:
        """Return this agent's opinion about the asset."""
        raise NotImplementedError

    def _neutral(self, reason: str) -> Signal:
        """Helper for when the agent cannot form an opinion."""
        return Signal(agent=self.name, score=0.0, confidence=0.0, reasons=[reason])
