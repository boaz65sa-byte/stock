"""Pure technical indicators implemented on top of pandas/numpy.

No external TA library is required, which keeps installation simple.
Each function takes a price Series (usually 'Close') and returns a Series.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, window: int) -> pd.Series:
    """Simple moving average."""
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    """Exponential moving average."""
    return series.ewm(span=span, adjust=False).mean()


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's smoothing)."""
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    out = 100 - (100 / (1 + rs))
    # When there are no losses at all, RSI is 100.
    out = out.where(avg_loss != 0, 100.0)
    return out


def macd(
    series: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """MACD line, signal line and histogram."""
    macd_line = ema(series, fast) - ema(series, slow)
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line
    return pd.DataFrame(
        {"macd": macd_line, "signal": signal_line, "hist": hist}
    )


def bollinger(series: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    """Bollinger bands."""
    mid = sma(series, window)
    std = series.rolling(window=window, min_periods=window).std()
    upper = mid + num_std * std
    lower = mid - num_std * std
    return pd.DataFrame({"mid": mid, "upper": upper, "lower": lower})


def annualized_return(series: pd.Series, periods_per_year: int = 252) -> float:
    """Annualized return based on daily closes."""
    returns = series.pct_change().dropna()
    if returns.empty:
        return 0.0
    mean_daily = returns.mean()
    return float((1 + mean_daily) ** periods_per_year - 1)


def annualized_volatility(series: pd.Series, periods_per_year: int = 252) -> float:
    """Annualized volatility (std of daily returns)."""
    returns = series.pct_change().dropna()
    if returns.empty:
        return 0.0
    return float(returns.std() * np.sqrt(periods_per_year))


def sharpe_ratio(series: pd.Series, risk_free: float = 0.0, periods_per_year: int = 252) -> float:
    """Rough Sharpe ratio from a price series."""
    vol = annualized_volatility(series, periods_per_year)
    if vol == 0:
        return 0.0
    return (annualized_return(series, periods_per_year) - risk_free) / vol


def max_drawdown(series: pd.Series) -> float:
    """Largest peak-to-trough decline as a negative fraction (e.g. -0.35)."""
    if series.empty:
        return 0.0
    cumulative_max = series.cummax()
    drawdown = series / cumulative_max - 1.0
    return float(drawdown.min())
