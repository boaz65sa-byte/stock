"""Simple paper-trading portfolio and a lightweight backtester."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from .config import Action
from .data import get_asset
from .orchestrator import Committee


@dataclass
class Position:
    ticker: str
    shares: float
    avg_price: float


@dataclass
class Trade:
    timestamp: str
    ticker: str
    side: str  # BUY / SELL
    shares: float
    price: float


@dataclass
class Portfolio:
    """A virtual cash + positions account. No real money involved."""

    cash: float = 10_000.0
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)

    def buy(self, ticker: str, price: float, amount_cash: float) -> None:
        amount_cash = min(amount_cash, self.cash)
        if amount_cash <= 0 or price <= 0:
            return
        shares = amount_cash / price
        self.cash -= amount_cash
        pos = self.positions.get(ticker)
        if pos:
            total = pos.shares + shares
            pos.avg_price = (pos.avg_price * pos.shares + price * shares) / total
            pos.shares = total
        else:
            self.positions[ticker] = Position(ticker, shares, price)
        self.trades.append(Trade(datetime.now().isoformat(), ticker, "BUY", shares, price))

    def sell(self, ticker: str, price: float, fraction: float = 1.0) -> None:
        pos = self.positions.get(ticker)
        if not pos or price <= 0:
            return
        shares = pos.shares * max(0.0, min(1.0, fraction))
        self.cash += shares * price
        pos.shares -= shares
        self.trades.append(Trade(datetime.now().isoformat(), ticker, "SELL", shares, price))
        if pos.shares <= 1e-9:
            del self.positions[ticker]

    def market_value(self, prices: dict[str, float]) -> float:
        equity = self.cash
        for t, pos in self.positions.items():
            equity += pos.shares * prices.get(t, pos.avg_price)
        return equity

    # --- persistence ---
    def save(self, path: str | Path = "portfolio.json") -> None:
        data = {
            "cash": self.cash,
            "positions": {t: asdict(p) for t, p in self.positions.items()},
            "trades": [asdict(x) for x in self.trades],
        }
        Path(path).write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path = "portfolio.json") -> "Portfolio":
        p = Path(path)
        if not p.exists():
            return cls()
        data = json.loads(p.read_text(encoding="utf-8"))
        pf = cls(cash=data.get("cash", 10_000.0))
        pf.positions = {
            t: Position(**v) for t, v in data.get("positions", {}).items()
        }
        pf.trades = [Trade(**x) for x in data.get("trades", [])]
        return pf


def rebalance_with_committee(
    portfolio: Portfolio,
    tickers: list[str],
    committee: Optional[Committee] = None,
    buy_budget_per_name: float = 1_000.0,
) -> list[str]:
    """Act on today's recommendations: buy STRONG_BUY/BUY, trim SELL/STRONG_SELL.

    Returns a list of human-readable action log lines.
    """
    committee = committee or Committee()
    log: list[str] = []
    recs = committee.rank(tickers)
    for rec in recs:
        if rec.price is None:
            continue
        if rec.action in (Action.STRONG_BUY, Action.BUY):
            budget = buy_budget_per_name * (2 if rec.action == Action.STRONG_BUY else 1)
            portfolio.buy(rec.ticker, rec.price, budget)
            log.append(f"BUY {rec.ticker} @ {rec.price:.2f} ({rec.action.value})")
        elif rec.action in (Action.SELL, Action.STRONG_SELL):
            frac = 1.0 if rec.action == Action.STRONG_SELL else 0.5
            if rec.ticker in portfolio.positions:
                portfolio.sell(rec.ticker, rec.price, frac)
                log.append(f"SELL {rec.ticker} @ {rec.price:.2f} ({rec.action.value})")
    return log


@dataclass
class BacktestResult:
    ticker: str
    equity_curve: pd.Series
    total_return: float
    buy_hold_return: float
    n_trades: int


def backtest_sma_cross(
    ticker: str,
    fast: int = 20,
    slow: int = 50,
    starting_cash: float = 10_000.0,
) -> BacktestResult:
    """A transparent, self-contained SMA-crossover backtest.

    Goes fully long when the fast SMA crosses above the slow SMA, fully to cash
    when it crosses below. This demonstrates the paper-trading machinery on
    historical data without look-ahead bias (signals use only past prices).
    """
    from . import indicators as ta

    asset = get_asset(ticker, period="5y", with_info=False)
    close = asset.close
    if len(close) < slow + 5:
        raise ValueError(f"Not enough history to backtest {ticker}.")

    sma_fast = ta.sma(close, fast)
    sma_slow = ta.sma(close, slow)
    # Position for tomorrow is decided by today's close (shift to avoid look-ahead).
    long_signal = (sma_fast > sma_slow).shift(1).fillna(False)

    cash = starting_cash
    shares = 0.0
    equity = []
    n_trades = 0
    for price, want_long in zip(close, long_signal):
        if want_long and shares == 0.0:
            shares = cash / price
            cash = 0.0
            n_trades += 1
        elif not want_long and shares > 0.0:
            cash = shares * price
            shares = 0.0
            n_trades += 1
        equity.append(cash + shares * price)

    curve = pd.Series(equity, index=close.index, name=ticker)
    total_return = curve.iloc[-1] / starting_cash - 1.0
    buy_hold = close.iloc[-1] / close.iloc[0] - 1.0
    return BacktestResult(ticker, curve, float(total_return), float(buy_hold), n_trades)
