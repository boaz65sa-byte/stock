"""Sector trend scout: compares an asset's momentum to the broad market (SPY).

Helps the committee spot relative strength — assets outperforming the market
often belong to sectors that are "in favor" right now.
"""

from __future__ import annotations

from functools import lru_cache

import pandas as pd

from ..config import Signal
from ..data import AssetData, get_asset
from .base import BaseAgent

_BENCHMARK = "SPY"


@lru_cache(maxsize=1)
def _benchmark_close() -> pd.Series:
    asset = get_asset(_BENCHMARK, period="6mo", with_info=False)
    return asset.close


class SectorTrendAgent(BaseAgent):
    name = "Sector Trend Scout"
    weight = 0.85

    def analyze(self, asset: AssetData) -> Signal:
        if not asset.is_valid or len(asset.close) < 63:
            return self._neutral("Not enough history for relative-strength check.")

        try:
            bench = _benchmark_close()
        except Exception:
            return self._neutral("Could not load market benchmark (SPY).")

        # Align on common dates.
        common = asset.close.index.intersection(bench.index)
        if len(common) < 63:
            return self._neutral("Insufficient overlap with market benchmark.")

        close = asset.close.loc[common]
        spy = bench.loc[common]
        days = 63
        asset_ret = close.iloc[-1] / close.iloc[-days] - 1.0
        spy_ret = spy.iloc[-1] / spy.iloc[-days] - 1.0
        rel = asset_ret - spy_ret

        reasons: list[str] = []
        if rel > 0.10:
            score = min(1.0, rel / 0.20)
            reasons.append(
                f"Outperforming S&P 500 by {rel * 100:+.1f}% over 3M (strong relative strength)."
            )
        elif rel > 0.03:
            score = rel / 0.10
            reasons.append(f"Slightly beating the market by {rel * 100:+.1f}% over 3M.")
        elif rel < -0.10:
            score = max(-1.0, rel / 0.20)
            reasons.append(
                f"Underperforming S&P 500 by {abs(rel) * 100:.1f}% over 3M (weak relative strength)."
            )
        elif rel < -0.03:
            score = rel / 0.10
            reasons.append(f"Slightly lagging the market by {abs(rel) * 100:.1f}% over 3M.")
        else:
            score = 0.0
            reasons.append(f"In line with the market ({rel * 100:+.1f}% vs S&P 500 over 3M).")

        return Signal(agent=self.name, score=score, confidence=0.65, reasons=reasons)
