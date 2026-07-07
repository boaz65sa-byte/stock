"""Personal AI investment advisor — conversational layer in Hebrew.

Uses OpenAI when configured. Combines the user's profile, live portfolio,
and committee analysis into context so answers feel personal and actionable.
Educational only — not licensed investment advice.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from .config import settings
from .explain import explain_recommendation
from .orchestrator import Committee
from .tickers import resolve
from .watch import HoldingInput, watch_portfolio

ADVISOR_NAME = "אלי"

SYSTEM_PROMPT = f"""אתה {ADVISOR_NAME}, יועץ השקעות AI אישי — חם, מקצועי, וברור.

כללים:
- ענה תמיד בעברית פשוטה, כאילו אתה מדבר עם חבר שמתחיל להשקיע.
- תן המלצות מעשיות: מה לעשות, כמה (באחוזים או כללים), למה, ומתי לבדוק שוב.
- השתמש בנתוני ההקשר (פרופיל, תיק, ציוני סוכנים) כשהם קיימים — אל תמציא מספרים.
- אם חסר מידע — שאל שאלה אחת קצרה, או הצע מה המשתמש יכול למלא.
- היה כנה על סיכונים. אל תבטיח תשואות.
- בסוף עצה ספציפית (קנייה/מכירה) — משפט אחד: "זה חינוכי, לא ייעוץ השקעות רשמי."
- 3–8 משפטים לרוב. אפשר bullet קצר אם יש כמה פעולות.
- אל תשתמש באנגלית מיותרת. סימבולים של מניות (AAPL) מותרים."""

NO_KEY_REPLY = (
    f"שלום! אני {ADVISOR_NAME}, יועץ ה-AI האישי שלך — אבל כרגע אני לא מחובר למוח (OpenAI).\n\n"
    "כדי להפעיל אותי:\n"
    "1. צור מפתח API ב-platform.openai.com\n"
    "2. הוסף `OPENAI_API_KEY` ב-Vercel (Settings → Environment Variables) או בקובץ `.env` מקומי\n"
    "3. פרוס מחדש / הפעל מחדש את השרת\n\n"
    "בינתיים אפשר להשתמש ב«תיק חכם», «סריקת שוק» ו«תיק חי» — הם עובדים גם בלי AI."
)


def _profile_text(profile: Optional[dict]) -> str:
    if not profile:
        return ""
    goal = {"growth": "צמיחה", "balanced": "מאוזן", "preserve": "שימור הון"}.get(
        profile.get("goal"), profile.get("goal", "")
    )
    risk = {"low": "נמוך", "medium": "בינוני", "high": "גבוה"}.get(
        profile.get("risk"), profile.get("risk", "")
    )
    horizon = {"short": "עד שנתיים", "medium": "2-5 שנים", "long": "5+ שנים"}.get(
        profile.get("horizon"), profile.get("horizon", "")
    )
    crypto = "כולל קריפטו" if profile.get("include_crypto") else "ללא קריפטו"
    return f"פרופיל משתמש: מטרה={goal}, סיכון={risk}, טווח={horizon}, {crypto}."


def _portfolio_text(committee: Committee, portfolio: Optional[dict]) -> str:
    if not portfolio or not portfolio.get("holdings"):
        return ""
    holdings = [
        HoldingInput(
            ticker=h["ticker"],
            shares=float(h["shares"]),
            entry_price=float(h["entry_price"]),
        )
        for h in portfolio["holdings"]
        if h.get("ticker") and h.get("shares") and h.get("entry_price")
    ]
    if not holdings:
        return ""
    snap = watch_portfolio(committee, holdings, cash=float(portfolio.get("cash") or 0))
    lines = [
        f"תיק המשתמש (עדכון): שווי ${snap['total_value']:,.0f}, "
        f"רווח/הפסד {snap['total_pnl_pct']:+.1f}% (${snap['total_pnl_usd']:+,.0f}), "
        f"מזומן ${snap['cash']:,.0f}.",
        f"סיכום Guardian: {snap['guardian']['headline']}",
    ]
    for p in snap["positions"][:12]:
        lines.append(
            f"  • {p['name_he']} ({p['ticker']}): {p['shares']} יח', "
            f"P&L {p['pnl_pct']:+.1f}%, היום {p['day_change_pct'] or 0:+.1f}%, "
            f"סוכנים={p['verdict']}, פעולה={p['advice']['label_he']}"
        )
    return "\n".join(lines)


def _tickers_in_message(message: str) -> list[str]:
    """Find tickers / Hebrew names mentioned in the user message."""
    found: list[str] = []
    # Words and comma-separated tokens.
    tokens = re.split(r"[\s,;]+", message.strip())
    for tok in tokens:
        if len(tok) < 2:
            continue
        r = resolve(tok)
        if r.ticker and r.ticker not in found:
            found.append(r.ticker)
    return found[:3]


def _extra_ticker_analysis(committee: Committee, message: str) -> str:
    tickers = _tickers_in_message(message)
    if not tickers:
        return ""
    lines = ["ניתוח סוכנים לנכסים שהוזכרו:"]
    for t in tickers:
        try:
            rec = committee.analyze(t, with_info=False)
            info = explain_recommendation(rec)
            price = f"${rec.price:.2f}" if rec.price else "N/A"
            lines.append(
                f"  • {t}: {info['verdict']}, ציון {rec.score_pct:+d}%, מחיר {price}. "
                f"{info['summary']}"
            )
        except Exception:
            lines.append(f"  • {t}: לא ניתן לנתח כרגע.")
    return "\n".join(lines)


def build_context(
    committee: Committee,
    message: str,
    profile: Optional[dict] = None,
    portfolio: Optional[dict] = None,
) -> str:
    parts = [_profile_text(profile), _portfolio_text(committee, portfolio)]
    parts.append(_extra_ticker_analysis(committee, message))
    return "\n".join(p for p in parts if p)


def chat(
    committee: Committee,
    message: str,
    history: list[dict],
    profile: Optional[dict] = None,
    portfolio: Optional[dict] = None,
) -> dict:
    """Send a message to the personal AI advisor and return the reply."""
    if not settings.llm_enabled:
        return {
            "reply": NO_KEY_REPLY,
            "advisor_name": ADVISOR_NAME,
            "enabled": False,
        }

    context = build_context(committee, message, profile, portfolio)
    user_block = message
    if context:
        user_block = f"[הקשר נוכחי]\n{context}\n\n[שאלת המשתמש]\n{message}"

    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for h in history[-10:]:
        role = h.get("role", "user")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": h.get("content", "")[:2000]})
    messages.append({"role": "user", "content": user_block[:4000]})

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        resp = client.chat.completions.create(
            model=settings.openai_model,
            messages=messages,
            temperature=0.55,
            max_tokens=700,
        )
        reply = (resp.choices[0].message.content or "").strip()
        if not reply:
            reply = "לא הצלחתי לנסח תשובה — נסה לנסח שוב או לשאול בצורה אחרת."
        return {
            "reply": reply,
            "advisor_name": ADVISOR_NAME,
            "enabled": True,
            "context_used": bool(context),
        }
    except Exception as exc:
        return {
            "reply": f"שגיאה בחיבור ל-AI ({type(exc).__name__}). בדוק את מפתח ה-API ונסה שוב.",
            "advisor_name": ADVISOR_NAME,
            "enabled": True,
            "error": type(exc).__name__,
        }
