"""Opportunity scout: looks for actionable entry setups.

Focuses on classic "buy the dip" and breakout patterns that beginners
can understand: oversold bounce near support, or breaking recent highs.
"""

from __future__ import annotations

from ..config import Signal
from ..data import AssetData
from .. import indicators as ta
from .base import BaseAgent


class OpportunityAgent(BaseAgent):
    name = "Opportunity Scout"
    weight = 1.0

    def analyze(self, asset: AssetData) -> Signal:
        if not asset.is_valid or len(asset.close) < 50:
            return self._neutral("Not enough history for opportunity scan.")

        close = asset.close
        price = close.iloc[-1]
        reasons: list[str] = []
        votes: list[float] = []

        rsi = ta.rsi(close).iloc[-1]
        bb = ta.bollinger(close)
        lower = bb["lower"].iloc[-1]
        upper = bb["upper"].iloc[-1]
        mid = bb["mid"].iloc[-1]

        # Buy-the-dip: oversold + near lower Bollinger band.
        if rsi < 35 and price <= lower * 1.02:
            votes.append(0.75)
            reasons.append(
                f"Oversold bounce setup: RSI {rsi:.0f}, price near lower Bollinger band."
            )
        elif rsi < 40 and price < mid:
            votes.append(0.35)
            reasons.append(f"Mild dip opportunity: RSI {rsi:.0f}, price below mid-band.")

        # Breakout: new 20-day high with momentum.
        high20 = close.tail(21).iloc[:-1].max()
        if price >= high20 and rsi > 50:
            votes.append(0.6)
            reasons.append("Breakout: price at/near 20-day high with positive momentum.")
        elif price >= high20:
            votes.append(0.3)
            reasons.append("Near 20-day high — possible breakout forming.")

        # Overextended: price above upper band + overbought = caution.
        if rsi > 72 and price >= upper:
            votes.append(-0.5)
            reasons.append(f"Extended move: RSI {rsi:.0f}, price at upper Bollinger (risky entry).")

        if not votes:
            votes.append(0.0)
            reasons.append("No clear entry setup — wait for a better opportunity.")

        score = sum(votes) / len(votes)
        confidence = min(1.0, 0.45 + 0.15 * len(votes))
        return Signal(agent=self.name, score=score, confidence=confidence, reasons=reasons)
