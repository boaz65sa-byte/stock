"""Profit projections and one-click broker export (Dash and similar).

Projections use historical returns weighted by allocation, adjusted for agent
scores and user profile. They are illustrative scenarios only — not guarantees.
"""

from __future__ import annotations

from typing import Iterable, Optional

from . import indicators as ta
from .config import Recommendation
from .data import get_asset

PROJECT_YEARS = {"short": 2, "medium": 4, "long": 7}
CASH_YIELD = 0.03  # assumed annual yield on uninvested cash
CRYPTO_SUFFIX = "-USD"

SCENARIO_HE = {
    "pessimistic": "זהיר (תרחיש גרוע)",
    "base": "צפוי (ממוצע היסטורי)",
    "optimistic": "אופטימי (תרחיש טוב)",
}


def _is_crypto(ticker: str) -> bool:
    return ticker.endswith(CRYPTO_SUFFIX) or ticker in ("BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD")


def _asset_annual_stats(ticker: str) -> tuple[float, float]:
    """Return (annualized_return, annualized_volatility) from ~2y history."""
    try:
        asset = get_asset(ticker, period="2y", with_info=False)
        if not asset.is_valid or len(asset.close) < 60:
            return 0.08, 0.22
        close = asset.close
        return ta.annualized_return(close), ta.annualized_volatility(close)
    except Exception:
        return 0.08, 0.22


def project_portfolio_returns(
    amount: float,
    invested: float,
    cash: float,
    allocations: list[dict],
    profile: dict,
    rec_by_ticker: Optional[dict[str, Recommendation]] = None,
) -> dict:
    """Estimate profit scenarios based on historical returns + profile."""
    rec_by_ticker = rec_by_ticker or {}
    horizon = profile.get("horizon", "medium")
    risk = profile.get("risk", "medium")
    years = PROJECT_YEARS.get(horizon, 4)

    port_return = 0.0
    port_vol = 0.0
    if amount > 0:
        for a in allocations:
            w = a["amount"] / amount
            ann_ret, vol = _asset_annual_stats(a["ticker"])
            rec = rec_by_ticker.get(a["ticker"])
            score_adj = 1.0 + (rec.score * 0.12 if rec else 0.0)
            port_return += w * ann_ret * score_adj
            port_vol += w * vol
        port_return += (cash / amount) * CASH_YIELD

    risk_bias = {"low": -0.02, "medium": 0.0, "high": 0.03}.get(risk, 0.0)
    base_rate = port_return + risk_bias

    scenarios_raw = {
        "pessimistic": max(base_rate - port_vol * 0.6, -0.35),
        "base": base_rate,
        "optimistic": min(base_rate + port_vol * 0.5, 0.55),
    }

    scenarios: dict[str, dict] = {}
    for key, rate in scenarios_raw.items():
        # Compound invested at rate; cash at CASH_YIELD.
        end_invested = invested * ((1 + rate) ** years) if invested > 0 else 0.0
        end_cash = cash * ((1 + CASH_YIELD) ** years) if cash > 0 else 0.0
        end_value = round(end_invested + end_cash, 2)
        profit = round(end_value - amount, 2)
        profit_pct = round(profit / amount * 100, 1) if amount > 0 else 0.0
        scenarios[key] = {
            "label_he": SCENARIO_HE[key],
            "annual_rate_pct": round(rate * 100, 1),
            "end_value": end_value,
            "profit": profit,
            "profit_pct": profit_pct,
        }

    horizon_he = {
        "short": "2 שנים",
        "medium": "4 שנים",
        "long": "7 שנים",
    }.get(horizon, f"{years} שנים")

    return {
        "years": years,
        "horizon_he": horizon_he,
        "invested": invested,
        "amount": amount,
        "weighted_annual_pct": round(base_rate * 100, 1),
        "scenarios": scenarios,
        "summary_he": (
            f"לפי תשואות היסטוריות, ציוני הסוכנים ופרופיל ({horizon_he}, סיכון {risk}): "
            f"תרחיש צפוי — רווח של כ-${scenarios['base']['profit']:,.0f} "
            f"({scenarios['base']['profit_pct']:+.1f}%) על ${amount:,.0f}."
        ),
        "disclaimer": "צפי מבוסס על עבר — לא הבטחה. שוק ההון יכול לרדת; חומר חינוכי בלבד.",
    }


def _share_qty(ticker: str, amount: float, price: Optional[float]) -> tuple[Optional[float], float]:
    """Return (quantity, leftover_usd). Crypto allows fractions."""
    if not price or price <= 0 or amount <= 0:
        return None, amount
    if _is_crypto(ticker):
        qty = round(amount / price, 6)
        leftover = round(amount - qty * price, 2)
        return qty, max(0.0, leftover)
    qty = int(amount // price)
    leftover = round(amount - qty * price, 2)
    return float(qty) if qty > 0 else 0.0, max(0.0, leftover)


def build_broker_export(
    allocations: list[dict],
    cash: float,
    amount: float,
    platform: str = "dash",
) -> dict:
    """Build copy-paste / CSV / JSON payloads for broker import (e.g. Dash)."""
    orders: list[dict] = []
    for a in allocations:
        ticker = a["ticker"]
        amt = a["amount"]
        price = a.get("price")
        qty, leftover = _share_qty(ticker, amt, price)
        orders.append(
            {
                "ticker": ticker,
                "name_he": a.get("name_he", ticker),
                "amount_usd": amt,
                "weight_pct": a.get("weight_pct", 0),
                "price": price,
                "shares": qty,
                "leftover_usd": leftover,
                "action": "BUY",
            }
        )

    # Plain text for Dash / generic broker paste.
    lines = ["# תיק להעברה — העתק והדבק ב-Dash (ייבוא / העתק מסחר)", f"# סה\"כ: ${amount:,.2f}", ""]
    for o in orders:
        if o["shares"] and o["shares"] > 0:
            sh = o["shares"]
            sh_str = f"{sh:.6f}".rstrip("0").rstrip(".") if _is_crypto(o["ticker"]) else str(int(sh))
            lines.append(f"{o['ticker']}\t{sh_str}\t${o['amount_usd']:,.2f}\t{o['name_he']}")
    if cash > 0:
        lines.append(f"CASH\t\t${cash:,.2f}\tמזומן בצד")
    clipboard_text = "\n".join(lines)

    csv_rows = ["Symbol,Shares,AmountUSD,WeightPct,Name"]
    for o in orders:
        sh = o["shares"] if o["shares"] is not None else ""
        csv_rows.append(
            f"{o['ticker']},{sh},{o['amount_usd']},{o['weight_pct']},\"{o['name_he']}\""
        )
    if cash > 0:
        csv_rows.append(f"CASH,,{cash},,\"מזומן\"")

    import json

    broker_json = json.dumps(
        {
            "platform": platform,
            "total_usd": amount,
            "cash_usd": cash,
            "orders": [
                {
                    "symbol": o["ticker"],
                    "side": "buy",
                    "quantity": o["shares"],
                    "amount_usd": o["amount_usd"],
                    "limit_price": o["price"],
                }
                for o in orders
                if o["shares"] and o["shares"] > 0
            ],
        },
        ensure_ascii=False,
        indent=2,
    )

    return {
        "platform": platform,
        "platform_he": "Dash",
        "orders": orders,
        "cash_usd": cash,
        "total_usd": amount,
        "clipboard_text": clipboard_text,
        "csv": "\n".join(csv_rows),
        "json": broker_json,
        "instructions_he": (
            "1. לחץ «העתק תיק ל-Dash» — הרשימה תועתק ללוח.\n"
            "2. פתח את Dash → ייבוא תיק / העתק מסחר / הדבק פקודות.\n"
            "3. אשר את הפקודות (כמות + סכום) — אין צורך להקליד ידנית כל נכס."
        ),
    }


def enrich_portfolio_result(
    result: dict,
    profile: dict,
    recs: Iterable[Recommendation],
) -> dict:
    """Attach projection + broker export to an advisor/portfolio result dict."""
    rec_by = {r.ticker: r for r in recs}
    allocs = result.get("allocations") or []
    amount = result.get("amount") or result.get("invested", 0) + result.get("cash", 0)
    invested = result.get("invested", 0)
    cash = result.get("cash", 0)

    if amount <= 0:
        amount = invested + cash

    if allocs and amount > 0:
        result["projection"] = project_portfolio_returns(
            amount, invested, cash, allocs, profile, rec_by
        )
        result["broker"] = build_broker_export(allocs, cash, amount)
        for a in allocs:
            for o in result["broker"]["orders"]:
                if o["ticker"] == a["ticker"]:
                    a["shares"] = o["shares"]
                    a["leftover_usd"] = o["leftover_usd"]
                    break
    return result
