"""The committee: runs all agents on an asset and aggregates their signals."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from .agents import BaseAgent, default_agents
from .config import Recommendation, Signal, score_to_action
from .data import AssetData, get_asset


class Committee:
    """Coordinates a set of agents and produces a single recommendation.

    The aggregate score is a weighted average where each agent contributes
    proportionally to (agent.weight * signal.confidence).
    """

    def __init__(self, agents: Optional[list[BaseAgent]] = None) -> None:
        self.agents = agents if agents is not None else default_agents()

    def analyze_asset(self, asset: AssetData) -> Recommendation:
        signals: list[Signal] = []
        for agent in self.agents:
            try:
                signals.append(agent.analyze(asset))
            except Exception as exc:  # never let one agent crash the run
                signals.append(
                    Signal(
                        agent=getattr(agent, "name", "Agent"),
                        score=0.0,
                        confidence=0.0,
                        reasons=[f"Agent error: {type(exc).__name__}"],
                    )
                )

        total_weight = 0.0
        weighted_score = 0.0
        for agent, sig in zip(self.agents, signals):
            w = agent.weight * sig.confidence
            weighted_score += sig.score * w
            total_weight += w

        score = weighted_score / total_weight if total_weight > 0 else 0.0
        confidence = min(1.0, total_weight / (len(self.agents) or 1))

        return Recommendation(
            ticker=asset.ticker,
            action=score_to_action(score),
            score=score,
            confidence=confidence,
            price=asset.last_price,
            signals=signals,
        )

    def analyze(self, ticker: str, with_info: bool = True) -> Recommendation:
        return self.analyze_asset(get_asset(ticker, with_info=with_info))

    def rank(
        self,
        tickers: list[str],
        with_info: bool = True,
        max_workers: Optional[int] = None,
    ) -> list[Recommendation]:
        """Analyze many tickers and return them sorted best-first.

        Fetches run in parallel threads because the work is network-bound
        (yfinance I/O releases the GIL), which keeps large universes fast.
        Failed tickers are skipped so one bad symbol never breaks the batch.
        """
        recs: list[Recommendation] = []
        if not tickers:
            return recs

        def _safe(t: str) -> Optional[Recommendation]:
            try:
                return self.analyze(t, with_info=with_info)
            except Exception:
                return None

        cap = max_workers if max_workers else 8
        workers = min(cap, len(tickers))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            for rec in ex.map(_safe, tickers):
                if rec is not None:
                    recs.append(rec)

        recs.sort(key=lambda r: r.score * r.confidence, reverse=True)
        return recs
