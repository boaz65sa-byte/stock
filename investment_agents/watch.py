"""Live portfolio guardian — tracks holdings, P&L, and agent-driven actions."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from .config import Action, Recommendation
from .data import get_asset
from .explain import explain_recommendation
from .orchestrator import Committee
from .tickers import resolve
from .universe import name_of


@dataclass
class HoldingInput:
    ticker: str
    shares: float
    entry_price: float


URGENCY_HE = {"high": "דחוף", "medium": "שים לב", "low": "רגוע"}
ACTION_HE = {
    "exit": "🚪 לצאת / למכור",
    "reduce": "📉 לצמצם",
    "hold": "✋ להחזיק",
    "add": "📈 להוסיף",
    "watch": "👀 לעקוב",
}


def _day_change_pct(history) -> Optional[float]:
    if history is None or len(history) < 2:
        return None
    prev, last = float(history.iloc[-2]), float(history.iloc[-1])
    if prev <= 0:
        return None
    return round((last / prev - 1) * 100, 2)


def _position_advice(
    rec: Recommendation,
    pnl_pct: float,
    day_pct: Optional[float],
) -> dict:
    """Map committee verdict + P&L into a concrete action for this holding."""
    action = rec.action
    urgency = "low"
    code = "hold"
    reasons: list[str] = []

    if action in (Action.STRONG_SELL, Action.SELL):
        code = "exit"
        urgency = "high"
        if pnl_pct >= 10:
            reasons.append(f"הסוכנים שליליים ויש רווח של {pnl_pct:+.1f}% — שקול לממש.")
        elif pnl_pct <= -10:
            reasons.append(f"הסוכנים שליליים והפסד של {pnl_pct:+.1f}% — שקול לצמצם/לצאת.")
        else:
            reasons.append("רוב הסוכנים שליליים — עדיף לא להוסיף; שקול יציאה.")
    elif action == Action.HOLD:
        code = "watch" if pnl_pct <= -12 else "hold"
        urgency = "medium" if pnl_pct <= -15 else "low"
        if pnl_pct <= -15:
            reasons.append(f"ירידה של {pnl_pct:+.1f}% מהכניסה — עקוב; אם ממשיך לרדת, שקול צמצום.")
        elif pnl_pct >= 25:
            reasons.append(f"רווח של {pnl_pct:+.1f}% — אפשר לקחת חלק מהרווח (trim).")
            code = "reduce"
            urgency = "medium"
        else:
            reasons.append("אין כיוון ברור — החזק ובדוק שוב בעוד כמה ימים.")
    elif action == Action.BUY:
        code = "add" if pnl_pct <= 5 else "hold"
        urgency = "low"
        reasons.append("הסוכנים חיוביים — אפשר להוסיף בהדרגה (DCA), לא בבת אחת.")
    else:  # STRONG_BUY
        code = "add"
        urgency = "medium" if pnl_pct < 0 else "low"
        reasons.append("איתות חזק — אם יש מזומן, אפשר לשקול הוספה מדורגת.")

    if day_pct is not None and day_pct <= -4:
        reasons.append(f"ירידה חדה היום ({day_pct:+.1f}%) — אל תקבל החלטות בפanic.")
        if urgency == "low":
            urgency = "medium"

    return {
        "code": code,
        "label_he": ACTION_HE[code],
        "urgency": urgency,
        "urgency_he": URGENCY_HE[urgency],
        "reasons": reasons,
    }


def _guardian_summary(positions: list[dict], total_pnl_pct: float) -> dict:
    """Portfolio-level message from the guardian agent."""
    exits = [p for p in positions if p["advice"]["code"] == "exit"]
    reduces = [p for p in positions if p["advice"]["code"] == "reduce"]
    adds = [p for p in positions if p["advice"]["code"] == "add"]
    urgent = [p for p in positions if p["advice"]["urgency"] == "high"]

    bullets: list[str] = []
    headline = "התיק יציב — אין פעולה דחופה."
    mood = "calm"

    if urgent:
        mood = "alert"
        names = ", ".join(p["name_he"] for p in urgent[:3])
        headline = f"⚠️ פעולה נדרשת ב-{len(urgent)} נכסים: {names}"
        for p in urgent:
            bullets.append(f"{p['name_he']} ({p['ticker']}): {p['advice']['label_he']} — {p['advice']['reasons'][0]}")

    if exits and not urgent:
        mood = "caution"
        headline = f"שקול יציאה מ-{len(exits)} נכסים לפי הסוכנים."
        for p in exits[:3]:
            bullets.append(f"{p['name_he']}: {p['advice']['reasons'][0]}")

    if adds and mood == "calm":
        mood = "positive"
        headline = f"יש {len(adds)} נכסים עם איתות להוספה — אם יש מזומן."
        for p in adds[:2]:
            bullets.append(f"{p['name_he']}: {p['advice']['reasons'][0]}")

    if reduces:
        for p in reduces[:2]:
            bullets.append(f"{p['name_he']}: {p['advice']['reasons'][0]}")

    if total_pnl_pct >= 15:
        bullets.insert(0, f"התיק ברווח כולל של {total_pnl_pct:+.1f}% — שקול לפזר/לקחת חלק מהרווחים.")
    elif total_pnl_pct <= -10:
        bullets.insert(0, f"התיק בירידה של {total_pnl_pct:+.1f}% — אל תמכור בהיסטריה; בדוק נכס-נכס.")

    bullets.append("אני עוקב ואעדכן בכל ריענון. חומר חינוכי — לא ייעוץ אישי.")
    return {"headline": headline, "mood": mood, "bullets": bullets}


def _analyze_holding(committee: Committee, h: HoldingInput) -> Optional[dict]:
    if h.shares <= 0 or h.entry_price <= 0:
        return None
    r = resolve(h.ticker)
    ticker = r.ticker or h.ticker.strip().upper()
    if not ticker:
        return None
    try:
        asset = get_asset(ticker, period="6mo", with_info=False)
        if not asset.is_valid:
            return None
        rec = committee.analyze_asset(asset)
        current = rec.price or float(asset.close.iloc[-1])
    except Exception:
        return None

    cost = h.shares * h.entry_price
    value = h.shares * current
    pnl = value - cost
    pnl_pct = (current / h.entry_price - 1) * 100 if h.entry_price > 0 else 0.0
    day_pct = _day_change_pct(asset.close)

    info = explain_recommendation(rec)
    advice = _position_advice(rec, pnl_pct, day_pct)

    return {
        "ticker": ticker,
        "name_he": name_of(ticker) if name_of(ticker) != ticker else ticker,
        "shares": h.shares,
        "entry_price": round(h.entry_price, 4),
        "current_price": round(current, 4),
        "cost_basis": round(cost, 2),
        "market_value": round(value, 2),
        "pnl_usd": round(pnl, 2),
        "pnl_pct": round(pnl_pct, 2),
        "day_change_pct": day_pct,
        "score_pct": rec.score_pct,
        "action": rec.action.value,
        "verdict": info["verdict"],
        "emoji": info["emoji"],
        "color": info["color"],
        "advice": advice,
        "_cost": cost,
        "_value": value,
    }


def watch_portfolio(
    committee: Committee,
    holdings: list[HoldingInput],
    cash: float = 0.0,
) -> dict:
    """Analyze a live portfolio and return P&L + guardian guidance."""
    positions: list[dict] = []

    workers = min(8, max(1, len(holdings)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        for row in ex.map(lambda h: _analyze_holding(committee, h), holdings):
            if row is not None:
                positions.append(row)

    total_cost = cash + sum(p.pop("_cost") for p in positions)
    total_value = cash + sum(p.pop("_value") for p in positions)
    total_pnl = round(total_value - total_cost, 2)
    total_pnl_pct = round((total_value / total_cost - 1) * 100, 2) if total_cost > 0 else 0.0
    invested_value = total_value - cash
    invested_cost = total_cost - cash

    guardian = _guardian_summary(positions, total_pnl_pct)

    return {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cash": round(cash, 2),
        "total_cost": round(total_cost, 2),
        "total_value": round(total_value, 2),
        "total_pnl_usd": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "invested_pnl_usd": round(invested_value - invested_cost, 2) if invested_cost > 0 else 0,
        "positions": sorted(positions, key=lambda p: abs(p["pnl_usd"]), reverse=True),
        "guardian": guardian,
        "note": "עדכון חי מבוסס מחירים אחרונים וניתוח הסוכנים. לא ייעוץ השקעות.",
    }
