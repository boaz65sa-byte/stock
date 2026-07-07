"""Personal AI investment advisor — conversational layer in Hebrew.

Uses OpenAI when configured. Combines the user's profile, live portfolio,
and committee analysis into context so answers feel personal and actionable.
Educational only — not licensed investment advice.
"""

from __future__ import annotations

import json
import re
from typing import Optional

from .agents.llm_analyst import LLMAnalystAgent
from .config import settings
from .explain import explain_recommendation
from .llm_provider import chat_completion, model_name, provider_name
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
    f"שלום! אני {ADVISOR_NAME}, יועץ ה-AI האישי שלך — אבל כרגע אני לא מחובר למוח (AI).\n\n"
    "יש לך מנוי Gemini? מעולה:\n"
    "1. היכנס ל-aistudio.google.com/apikey וצור מפתח API\n"
    "2. הוסף ב-Vercel (Settings → Environment Variables):\n"
    "   • `GEMINI_API_KEY` = המפתח שלך\n"
    "   • (אופציונלי) `GEMINI_MODEL` = gemini-2.0-flash\n"
    "3. Redeploy\n\n"
    "או עם OpenAI: `OPENAI_API_KEY` מ-platform.openai.com\n\n"
    "בינתיים: «תיק חכם», «סריקת שוק» ו«תיק חי» עובדים גם בלי AI."
)


def _context_committee(committee: Committee) -> Committee:
    """Use algorithmic agents only when building chat context (saves LLM quota)."""
    agents = [a for a in committee.agents if not isinstance(a, LLMAnalystAgent)]
    if len(agents) == len(committee.agents):
        return committee
    return Committee(agents=agents)


def _llm_error_reply(exc: Exception) -> str:
    name = type(exc).__name__
    if name == "RateLimitError" or "rate limit" in str(exc).lower() or "quota" in str(exc).lower():
        provider = "Gemini" if provider_name() == "gemini" else "OpenAI"
        return (
            f"הגעת למגבלת בקשות של {provider} (RateLimit) — לא בעיה במפתח.\n\n"
            "מה לעשות:\n"
            "• המתן דקה-שתיים ונסה שוב\n"
            "• אל תשלח הרבה הודעות ברצף\n"
            "• ב-Gemini: בדוק מכסה ב-aistudio.google.com/apikey\n"
            "• אופציונלי: `GEMINI_MODEL=gemini-2.0-flash-lite` ב-Vercel (מכסה גבוהה יותר)\n\n"
            "«תיק חי» ו«סריקת שוק» עובדים בלי צ'אט AI."
        )
    if "auth" in name.lower() or "api key" in str(exc).lower() or "401" in str(exc):
        return (
            "מפתח ה-API לא תקין או פג תוקף.\n"
            "בדוק `GEMINI_API_KEY` (או `OPENAI_API_KEY`) ב-Vercel → Redeploy."
        )
    return f"שגיאה בחיבור ל-AI ({name}). נסה שוב בעוד רגע."


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
    snap = watch_portfolio(_context_committee(committee), holdings, cash=float(portfolio.get("cash") or 0))
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
    ctx = _context_committee(committee)
    lines = ["ניתוח סוכנים לנכסים שהוזכרו:"]
    for t in tickers:
        try:
            rec = ctx.analyze(t, with_info=False)
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

    messages: list[dict] = []
    for h in history[-10:]:
        role = h.get("role", "user")
        if role in ("user", "assistant"):
            messages.append({"role": role, "content": h.get("content", "")[:2000]})
    messages.append({"role": "user", "content": user_block[:4000]})

    try:
        reply = chat_completion(SYSTEM_PROMPT, messages, temperature=0.55, max_tokens=700)
        if not reply:
            reply = "לא הצלחתי לנסח תשובה — נסה לנסח שוב או לשאול בצורה אחרת."
        return {
            "reply": reply,
            "advisor_name": ADVISOR_NAME,
            "enabled": True,
            "provider": provider_name(),
            "model": model_name(),
            "context_used": bool(context),
        }
    except Exception as exc:
        return {
            "reply": _llm_error_reply(exc),
            "advisor_name": ADVISOR_NAME,
            "enabled": True,
            "provider": provider_name(),
            "error": type(exc).__name__,
        }
