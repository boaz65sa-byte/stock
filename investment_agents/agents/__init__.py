"""Agent implementations for the investment committee."""

from __future__ import annotations

from ..config import settings
from .base import BaseAgent
from .llm_analyst import LLMAnalystAgent
from .momentum import MomentumAgent
from .risk import RiskManagerAgent
from .technical import TechnicalAgent
from .value import ValueAgent


def default_agents() -> list[BaseAgent]:
    """Build the standard committee.

    Algorithmic agents always run. The LLM analyst is added only when an
    OpenAI key is configured.
    """
    agents: list[BaseAgent] = [
        TechnicalAgent(),
        MomentumAgent(),
        ValueAgent(),
        RiskManagerAgent(),
    ]
    if settings.llm_enabled:
        agents.append(LLMAnalystAgent())
    return agents


__all__ = [
    "BaseAgent",
    "TechnicalAgent",
    "MomentumAgent",
    "ValueAgent",
    "RiskManagerAgent",
    "LLMAnalystAgent",
    "default_agents",
]
