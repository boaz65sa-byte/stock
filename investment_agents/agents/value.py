"""Value agent: judges fundamentals (P/E, PEG, margins, growth).

Fundamentals come from yfinance's `.info`. For assets without fundamentals
(e.g. crypto), the agent stays neutral with low confidence.
"""

from __future__ import annotations

from ..config import Signal
from ..data import AssetData
from .base import BaseAgent


def _num(info: dict, key: str):
    v = info.get(key)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


class ValueAgent(BaseAgent):
    name = "Value Investor"
    weight = 1.0

    def analyze(self, asset: AssetData) -> Signal:
        info = asset.info or {}
        reasons: list[str] = []
        votes: list[float] = []

        pe = _num(info, "trailingPE") or _num(info, "forwardPE")
        peg = _num(info, "pegRatio")
        margins = _num(info, "profitMargins")
        rev_growth = _num(info, "revenueGrowth")

        if pe is not None:
            if pe <= 0:
                votes.append(-0.3)
                reasons.append(f"Negative earnings (P/E {pe:.1f}).")
            elif pe < 15:
                votes.append(0.6)
                reasons.append(f"Low P/E {pe:.1f} (cheap).")
            elif pe < 30:
                votes.append(0.1)
                reasons.append(f"Fair P/E {pe:.1f}.")
            else:
                votes.append(-0.4)
                reasons.append(f"High P/E {pe:.1f} (expensive).")

        if peg is not None and peg > 0:
            if peg < 1:
                votes.append(0.5)
                reasons.append(f"PEG {peg:.2f} < 1 (growth vs price attractive).")
            elif peg > 2:
                votes.append(-0.4)
                reasons.append(f"PEG {peg:.2f} > 2 (pricey vs growth).")

        if margins is not None:
            if margins > 0.15:
                votes.append(0.4)
                reasons.append(f"Healthy profit margin {margins * 100:.0f}%.")
            elif margins < 0:
                votes.append(-0.4)
                reasons.append("Company is unprofitable.")

        if rev_growth is not None:
            if rev_growth > 0.15:
                votes.append(0.4)
                reasons.append(f"Strong revenue growth {rev_growth * 100:.0f}%.")
            elif rev_growth < 0:
                votes.append(-0.3)
                reasons.append(f"Revenue shrinking {rev_growth * 100:.0f}%.")

        if not votes:
            return self._neutral("No fundamentals available (e.g. crypto/ETF).")

        score = sum(votes) / len(votes)
        confidence = min(0.9, 0.35 + 0.12 * len(votes))
        return Signal(agent=self.name, score=score, confidence=confidence, reasons=reasons)
