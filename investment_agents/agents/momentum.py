"""Momentum agent: recent trailing returns across several horizons."""

from __future__ import annotations

from ..config import Signal
from ..data import AssetData
from .base import BaseAgent


class MomentumAgent(BaseAgent):
    name = "Momentum Trader"
    weight = 1.0

    # (lookback in trading days, weight)
    HORIZONS = [(21, 0.3), (63, 0.4), (126, 0.3)]

    def analyze(self, asset: AssetData) -> Signal:
        if not asset.is_valid:
            return self._neutral("Not enough price history for momentum.")

        close = asset.close
        reasons: list[str] = []
        weighted = 0.0
        total_w = 0.0

        for days, w in self.HORIZONS:
            if len(close) <= days:
                continue
            ret = close.iloc[-1] / close.iloc[-days] - 1.0
            # Squash return into [-1, 1]; ~+25% over the window ~= full bullish.
            squashed = max(-1.0, min(1.0, ret / 0.25))
            weighted += squashed * w
            total_w += w
            label = {21: "1M", 63: "3M", 126: "6M"}.get(days, f"{days}d")
            reasons.append(f"{label} return {ret * 100:+.1f}%.")

        if total_w == 0:
            return self._neutral("Not enough history for momentum horizons.")

        score = weighted / total_w
        confidence = min(1.0, 0.5 + 0.1 * len([1 for d, _ in self.HORIZONS if len(close) > d]))
        return Signal(agent=self.name, score=score, confidence=confidence, reasons=reasons)
