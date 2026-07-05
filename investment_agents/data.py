"""Market data access layer.

Uses yfinance (free, no API key) to fetch historical prices and basic
fundamentals. Results are cached in-process to avoid hammering the API when
several agents ask for the same ticker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Optional

import pandas as pd

from .config import settings


@dataclass
class AssetData:
    """Everything the agents need to analyze a single asset."""

    ticker: str
    history: pd.DataFrame  # OHLCV, indexed by date
    info: dict[str, Any] = field(default_factory=dict)

    @property
    def last_price(self) -> Optional[float]:
        if self.history.empty:
            return None
        return float(self.history["Close"].iloc[-1])

    @property
    def close(self) -> pd.Series:
        return self.history["Close"].dropna()

    @property
    def is_valid(self) -> bool:
        return not self.history.empty and len(self.close) >= 30


def _normalize_ticker(ticker: str) -> str:
    return ticker.strip().upper()


@lru_cache(maxsize=256)
def _download(ticker: str, period: str, interval: str) -> pd.DataFrame:
    import yfinance as yf

    df = yf.download(
        ticker,
        period=period,
        interval=interval,
        auto_adjust=True,
        progress=False,
    )
    if isinstance(df.columns, pd.MultiIndex):
        # yfinance sometimes returns a column MultiIndex for single tickers.
        df.columns = df.columns.get_level_values(0)
    return df


@lru_cache(maxsize=256)
def _fetch_info(ticker: str) -> dict[str, Any]:
    import yfinance as yf

    try:
        return dict(yf.Ticker(ticker).info)
    except Exception:
        return {}


def get_asset(
    ticker: str,
    period: Optional[str] = None,
    interval: Optional[str] = None,
    with_info: bool = True,
) -> AssetData:
    """Fetch price history (and optionally fundamentals) for a ticker."""
    ticker = _normalize_ticker(ticker)
    period = period or settings.history_period
    interval = interval or settings.history_interval

    history = _download(ticker, period, interval)
    info = _fetch_info(ticker) if with_info else {}
    return AssetData(ticker=ticker, history=history, info=info)


def get_assets(
    tickers: list[str],
    period: Optional[str] = None,
    interval: Optional[str] = None,
    with_info: bool = True,
) -> list[AssetData]:
    return [get_asset(t, period, interval, with_info) for t in tickers]
