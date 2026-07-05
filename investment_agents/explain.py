"""Turn technical recommendations into plain Hebrew a beginner can understand.

The goal: someone who knows nothing about investing should read the output
and immediately understand "should I buy this or not, and why".
"""

from __future__ import annotations

from .config import Action, Recommendation, Signal

# Big, human verdict for each action.
VERDICT_HE: dict[Action, str] = {
    Action.STRONG_BUY: "כדאי מאוד לקנות",
    Action.BUY: "נראה כדאי לקנות",
    Action.HOLD: "עדיף להמתין",
    Action.SELL: "עדיף לא לקנות / למכור חלק",
    Action.STRONG_SELL: "לא כדאי — עדיף למכור",
}

# One-line explanation of what the verdict means.
VERDICT_SUB_HE: dict[Action, str] = {
    Action.STRONG_BUY: "רוב הסימנים חיוביים וחזקים.",
    Action.BUY: "יותר סימנים חיוביים משליליים.",
    Action.HOLD: "הסימנים מעורבים — אין כיוון ברור כרגע.",
    Action.SELL: "יש יותר סימני אזהרה מסימנים חיוביים.",
    Action.STRONG_SELL: "רוב הסימנים שליליים.",
}

# Emoji "traffic light" per action.
EMOJI_HE: dict[Action, str] = {
    Action.STRONG_BUY: "🟢",
    Action.BUY: "🟢",
    Action.HOLD: "🟡",
    Action.SELL: "🔴",
    Action.STRONG_SELL: "🔴",
}

COLOR_HE: dict[Action, str] = {
    Action.STRONG_BUY: "#0a8f3c",
    Action.BUY: "#2ecc71",
    Action.HOLD: "#f1c40f",
    Action.SELL: "#e67e22",
    Action.STRONG_SELL: "#c0392b",
}

# Map the internal agent names to a friendly Hebrew role + what it checks.
AGENT_ROLE_HE: dict[str, str] = {
    "Technical Analyst": "מגמת הגרף",
    "Momentum Trader": "העלייה/ירידה לאחרונה",
    "Value Investor": "כמה החברה שווה מול הרווח שלה",
    "Risk Manager": "רמת הסיכון",
    "AI Analyst": "דעת הבינה המלאכותית",
}


def _mood(score: float) -> tuple[str, str]:
    """Return (emoji, hebrew word) describing a single signal's direction."""
    if score >= 0.15:
        return "👍", "חיובי"
    if score <= -0.15:
        return "👎", "שלילי"
    return "😐", "ניטרלי"


def confidence_word_he(confidence: float) -> str:
    if confidence >= 0.75:
        return "ביטחון גבוה"
    if confidence >= 0.45:
        return "ביטחון בינוני"
    return "ביטחון נמוך"


def simple_signal_lines(signals: list[Signal]) -> list[dict]:
    """Beginner-friendly, per-agent summary items."""
    lines: list[dict] = []
    for s in signals:
        emoji, mood = _mood(s.score)
        role = AGENT_ROLE_HE.get(s.agent, s.agent)
        lines.append(
            {
                "emoji": emoji,
                "role": role,
                "mood": mood,
                "score": s.score,
                "detail": s.reasons[0] if s.reasons else "",
            }
        )
    return lines


def explain_recommendation(rec: Recommendation) -> dict:
    """Produce a full plain-Hebrew explanation package for the UI/CLI."""
    action = rec.action
    positives = sum(1 for s in rec.signals if s.score >= 0.15)
    negatives = sum(1 for s in rec.signals if s.score <= -0.15)

    summary = (
        f"מתוך {len(rec.signals)} הבודקים: "
        f"{positives} רואים סימן חיובי, {negatives} רואים סימן שלילי."
    )

    return {
        "emoji": EMOJI_HE.get(action, "🟡"),
        "verdict": VERDICT_HE.get(action, "עדיף להמתין"),
        "subtitle": VERDICT_SUB_HE.get(action, ""),
        "color": COLOR_HE.get(action, "#f1c40f"),
        "score_pct": rec.score_pct,
        "confidence_word": confidence_word_he(rec.confidence),
        "summary": summary,
        "signal_lines": simple_signal_lines(rec.signals),
    }
