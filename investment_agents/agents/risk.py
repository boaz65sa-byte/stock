"""Risk manager agent: penalizes high volatility and deep drawdowns.

This agent acts as a brake. It rarely says "buy" strongly; instead it warns
when an asset is dangerous, nudging the committee's score toward caution.
"""

from __future__ import annotations

from ..config import Signal
from ..data import AssetData
from .. import indicators as ta
from .base import BaseAgent


class RiskManagerAgent(BaseAgent):
    name = "Risk Manager"
    weight = 0.9

    def analyze(self, asset: AssetData) -> Signal:
        if not asset.is_valid:
            return self._neutral("Not enough history to assess risk.")

        close = asset.close
        reasons: list[str] = []
        votes: list[float] = []

        vol = ta.annualized_volatility(close)
        if vol > 0.6:
            votes.append(-0.7)
            reasons.append(f"Very high volatility {vol * 100:.0f}% (risky).")
        elif vol > 0.35:
            votes.append(-0.3)
            reasons.append(f"Elevated volatility {vol * 100:.0f}%.")
        else:
            votes.append(0.2)
            reasons.append(f"Moderate volatility {vol * 100:.0f}%.")

        mdd = ta.max_drawdown(close)
        if mdd < -0.5:
            votes.append(-0.6)
            reasons.append(f"Severe max drawdown {mdd * 100:.0f}%.")
        elif mdd < -0.3:
            votes.append(-0.2)
            reasons.append(f"Notable max drawdown {mdd * 100:.0f}%.")
        else:
            votes.append(0.1)
            reasons.append(f"Contained drawdown {mdd * 100:.0f}%.")

        sharpe = ta.sharpe_ratio(close)
        if sharpe > 1:
            votes.append(0.5)
            reasons.append(f"Good risk-adjusted return (Sharpe {sharpe:.2f}).")
        elif sharpe < 0:
            votes.append(-0.4)
            reasons.append(f"Negative risk-adjusted return (Sharpe {sharpe:.2f}).")
        else:
            reasons.append(f"Sharpe {sharpe:.2f}.")

        score = sum(votes) / len(votes)
        return Signal(agent=self.name, score=score, confidence=0.7, reasons=reasons)
