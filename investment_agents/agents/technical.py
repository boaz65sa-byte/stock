"""Technical analysis agent: RSI, moving-average cross, MACD, Bollinger."""

from __future__ import annotations

from ..config import Signal
from ..data import AssetData
from .. import indicators as ta
from .base import BaseAgent


class TechnicalAgent(BaseAgent):
    name = "Technical Analyst"
    weight = 1.2

    def analyze(self, asset: AssetData) -> Signal:
        if not asset.is_valid:
            return self._neutral("Not enough price history for technical analysis.")

        close = asset.close
        reasons: list[str] = []
        votes: list[float] = []

        # --- RSI: oversold is bullish, overbought is bearish ---
        rsi = ta.rsi(close).iloc[-1]
        if rsi < 30:
            votes.append(0.8)
            reasons.append(f"RSI {rsi:.0f} < 30 (oversold, bullish).")
        elif rsi > 70:
            votes.append(-0.8)
            reasons.append(f"RSI {rsi:.0f} > 70 (overbought, bearish).")
        else:
            # Lean slightly based on distance from 50.
            votes.append((50 - rsi) / 50)
            reasons.append(f"RSI {rsi:.0f} (neutral zone).")

        # --- Moving-average trend: price vs SMA50 and SMA50 vs SMA200 ---
        sma50 = ta.sma(close, 50).iloc[-1]
        price = close.iloc[-1]
        if price > sma50:
            votes.append(0.5)
            reasons.append("Price above SMA50 (uptrend).")
        else:
            votes.append(-0.5)
            reasons.append("Price below SMA50 (downtrend).")

        if len(close) >= 200:
            sma200 = ta.sma(close, 200).iloc[-1]
            if sma50 > sma200:
                votes.append(0.6)
                reasons.append("Golden cross: SMA50 above SMA200 (bullish).")
            else:
                votes.append(-0.6)
                reasons.append("Death cross: SMA50 below SMA200 (bearish).")

        # --- MACD histogram sign ---
        macd_hist = ta.macd(close)["hist"].iloc[-1]
        if macd_hist > 0:
            votes.append(0.4)
            reasons.append("MACD histogram positive (momentum up).")
        else:
            votes.append(-0.4)
            reasons.append("MACD histogram negative (momentum down).")

        score = sum(votes) / len(votes)
        confidence = min(1.0, 0.4 + 0.15 * len(votes))
        return Signal(agent=self.name, score=score, confidence=confidence, reasons=reasons)
