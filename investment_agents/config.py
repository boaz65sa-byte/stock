"""Central configuration and shared data types for the system."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # dotenv is optional
    pass


class Action(str, Enum):
    """A discrete trading decision."""

    STRONG_BUY = "STRONG_BUY"
    BUY = "BUY"
    HOLD = "HOLD"
    SELL = "SELL"
    STRONG_SELL = "STRONG_SELL"


# Map an aggregate score in [-1, 1] to a human action.
def score_to_action(score: float) -> Action:
    if score >= 0.5:
        return Action.STRONG_BUY
    if score >= 0.15:
        return Action.BUY
    if score <= -0.5:
        return Action.STRONG_SELL
    if score <= -0.15:
        return Action.SELL
    return Action.HOLD


@dataclass
class Signal:
    """A single agent's opinion about an asset.

    score: value in [-1, 1]. +1 = maximally bullish, -1 = maximally bearish.
    confidence: value in [0, 1]. How sure the agent is.
    reasons: short human-readable bullet points explaining the score.
    """

    agent: str
    score: float
    confidence: float
    reasons: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.score = max(-1.0, min(1.0, float(self.score)))
        self.confidence = max(0.0, min(1.0, float(self.confidence)))


@dataclass
class Recommendation:
    """The committee's combined verdict for a single ticker."""

    ticker: str
    action: Action
    score: float
    confidence: float
    price: Optional[float]
    signals: list[Signal] = field(default_factory=list)

    @property
    def score_pct(self) -> int:
        return int(round(self.score * 100))


@dataclass
class Settings:
    """Runtime settings, mostly read from environment variables."""

    openai_api_key: Optional[str] = os.getenv("OPENAI_API_KEY") or None
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Google Gemini (AI Studio) — preferred when set; works with Gemini subscription API keys.
    gemini_api_key: Optional[str] = (
        os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or None
    )
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # How much recent history each analysis pulls (yfinance period string).
    history_period: str = "1y"
    history_interval: str = "1d"

    @property
    def llm_enabled(self) -> bool:
        return bool(self.openai_api_key or self.gemini_api_key)

    @property
    def llm_provider(self) -> str:
        if self.gemini_api_key:
            return "gemini"
        if self.openai_api_key:
            return "openai"
        return "none"


settings = Settings()
