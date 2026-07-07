"""Agent implementations for the investment committee."""

from __future__ import annotations

from ..config import settings
from .base import BaseAgent
from .llm_analyst import LLMAnalystAgent
from .momentum import MomentumAgent
from .opportunity import OpportunityAgent
from .risk import RiskManagerAgent
from .sector_trend import SectorTrendAgent
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
        SectorTrendAgent(),
        OpportunityAgent(),
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
    "SectorTrendAgent",
    "OpportunityAgent",
    "LLMAnalystAgent",
    "default_agents",
]
