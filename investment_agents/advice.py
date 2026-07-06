"""Turn a Recommendation into a concrete, plain-Hebrew action plan.

This is the "what should I actually do, and how" layer. It is intentionally
general and educational — position-size figures are common rules of thumb,
NOT personal financial advice.
"""

from __future__ import annotations

from typing import Iterable

from .config import Action, Recommendation


def _risk_level(rec: Recommendation) -> str:
    """Derive a coarse risk level from the Risk Manager's signal."""
    risk_score = 0.0
    for s in rec.signals:
        if s.agent == "Risk Manager":
            risk_score = s.score
            break
    # Risk Manager: positive score => safer, negative => riskier.
    if risk_score <= -0.3:
        return "high"
    if risk_score <= 0.05:
        return "medium"
    return "low"


RISK_HE = {"high": "סיכון גבוה", "medium": "סיכון בינוני", "low": "סיכון נמוך יחסית"}

# Suggested max share of a portfolio for a *single* asset, by risk level.
# General rule-of-thumb ranges only.
ALLOC_HE = {
    "high": "עד כ-5% מהתיק",
    "medium": "עד כ-10% מהתיק",
    "low": "עד כ-15% מהתיק",
}


def action_plan(rec: Recommendation) -> dict:
    """Build a structured, actionable plan for a single asset."""
    risk = _risk_level(rec)
    alloc = ALLOC_HE[risk]
    steps: list[str] = []

    if rec.action in (Action.STRONG_BUY, Action.BUY):
        headline = "הכיוון חיובי — אפשר לשקול כניסה"
        emoji = "🟢"
        steps = [
            f"היקף מוצע: {alloc} (בגלל {RISK_HE[risk]}). אל תרכז יותר מדי בנכס אחד.",
            "השקע בהדרגה (קצת כל חודש) במקום סכום גדול בבת אחת — כך פחות תלוי בתזמון.",
            "קבע מראש נקודת יציאה: אם הנכס יורד ~15-20% מתחת למחיר הקנייה, שקול לצאת.",
            "מתאים להשקעה לטווח בינוני-ארוך (שנה ומעלה), לא לספקולציה קצרה.",
        ]
        if rec.action == Action.STRONG_BUY:
            steps.insert(0, "רוב הבודקים חיוביים ובביטחון גבוה — האיתות חזק יחסית.")
    elif rec.action == Action.HOLD:
        headline = "אין כיוון ברור — עדיף להמתין ולעקוב"
        emoji = "🟡"
        steps = [
            "אם אתה כבר מחזיק: אפשר להמשיך להחזיק ולבחון שוב בעוד כמה שבועות.",
            "אם אינך מחזיק: חכה לאיתות ברור יותר לפני כניסה.",
            "הוסף את הנכס לרשימת מעקב ובדוק אותו שוב בהמשך.",
        ]
    else:  # SELL / STRONG_SELL
        headline = "רוב הסימנים שליליים — עדיף זהירות"
        emoji = "🔴"
        steps = [
            "אם אתה מחזיק: שקול לצמצם חשיפה או לצאת בהדרגה.",
            "אם אינך מחזיק: עדיף להימנע מכניסה חדשה כרגע.",
            "אפשר לשוב ולבחון את הנכס כשהמגמה תשתפר.",
        ]

    return {
        "emoji": emoji,
        "headline": headline,
        "risk_level": RISK_HE[risk],
        "steps": steps,
        # Reminders shown for every recommendation.
        "reminders": [
            "השקע רק כסף שאתה לא צריך בטווח הקרוב (קודם קרן חירום).",
            "פזר בין כמה נכסים/תחומים כדי להקטין סיכון.",
            "זה ניתוח ממוחשב וחומר חינוכי — לא ייעוץ השקעות אישי.",
        ],
    }


def suggest_allocation(recs: Iterable[Recommendation], amount: float) -> dict:
    """Split ``amount`` across assets, weighted by their positive score.

    Only assets the committee is positive on receive money; the weight is
    proportional to ``score * confidence``. Anything not allocated stays in
    cash. This is a simple, transparent rule of thumb — not personal advice.
    """
    recs = list(recs)
    weights = [max(r.score, 0.0) * max(r.confidence, 0.0) for r in recs]
    total_w = sum(weights)

    if total_w <= 0 or amount <= 0:
        return {
            "invested": 0.0,
            "cash": round(max(amount, 0.0), 2),
            "allocations": [],
            "excluded": [r.ticker for r in recs],
            "note": "אף נכס אינו חיובי מספיק כרגע — עדיף להמתין ולהחזיק מזומן.",
        }

    allocations = []
    excluded = []
    invested = 0.0
    for r, w in zip(recs, weights):
        if w <= 0:
            excluded.append(r.ticker)
            continue
        pct = w / total_w
        amt = round(amount * pct, 2)
        invested += amt
        allocations.append(
            {
                "ticker": r.ticker,
                "weight_pct": round(pct * 100, 1),
                "amount": amt,
                "score_pct": r.score_pct,
                "action": r.action.value,
                "price": r.price,
            }
        )

    allocations.sort(key=lambda a: a["amount"], reverse=True)
    cash = round(amount - invested, 2)
    note = (
        "החלוקה משוקללת לפי חוזק האיתות (ציון × ביטחון). "
        "פזר, השקע בהדרגה, וזכור: חומר חינוכי בלבד."
    )
    return {
        "invested": round(invested, 2),
        "cash": cash,
        "allocations": allocations,
        "excluded": excluded,
        "note": note,
    }
