"""Optional LLM-based analyst.

Only used when OPENAI_API_KEY is set. It receives a compact summary of the
recent price action and fundamentals and returns a structured opinion. If the
API call fails for any reason, it degrades gracefully to a neutral signal.
"""

from __future__ import annotations

import json

from ..config import Signal, settings
from ..data import AssetData
from .. import indicators as ta
from ..llm_provider import json_completion
from .base import BaseAgent


SYSTEM_PROMPT = (
    "You are a cautious equity/crypto analyst on an investment committee. "
    "Given quantitative facts about ONE asset, respond ONLY with a compact JSON "
    'object: {"score": <float -1..1>, "confidence": <float 0..1>, '
    '"reasons": [<3 short strings>]}. '
    "score>0 means bullish, <0 bearish. Do not add any text outside the JSON."
)


class LLMAnalystAgent(BaseAgent):
    name = "AI Analyst"
    weight = 1.1

    def _summary(self, asset: AssetData) -> str:
        close = asset.close
        info = asset.info or {}
        facts = {
            "ticker": asset.ticker,
            "name": info.get("shortName") or info.get("longName"),
            "sector": info.get("sector"),
            "last_price": round(float(close.iloc[-1]), 2),
            "rsi14": round(float(ta.rsi(close).iloc[-1]), 1),
            "return_1m_pct": round(float(close.iloc[-1] / close.iloc[-21] - 1) * 100, 1)
            if len(close) > 21
            else None,
            "return_6m_pct": round(float(close.iloc[-1] / close.iloc[-126] - 1) * 100, 1)
            if len(close) > 126
            else None,
            "annual_vol_pct": round(ta.annualized_volatility(close) * 100, 1),
            "max_drawdown_pct": round(ta.max_drawdown(close) * 100, 1),
            "trailing_pe": info.get("trailingPE"),
            "revenue_growth": info.get("revenueGrowth"),
        }
        return json.dumps(facts)

    def analyze(self, asset: AssetData) -> Signal:
        if not asset.is_valid:
            return self._neutral("Not enough data for AI analysis.")
        if not settings.llm_enabled:
            return self._neutral("AI analyst disabled (no GEMINI_API_KEY / OPENAI_API_KEY).")

        try:
            raw = json_completion(SYSTEM_PROMPT, self._summary(asset), temperature=0.2)
            data = json.loads(raw)
            return Signal(
                agent=self.name,
                score=float(data.get("score", 0.0)),
                confidence=float(data.get("confidence", 0.5)),
                reasons=[str(r) for r in data.get("reasons", [])][:3],
            )
        except Exception as exc:  # network / parsing / auth issues
            return self._neutral(f"AI analyst unavailable ({type(exc).__name__}).")
