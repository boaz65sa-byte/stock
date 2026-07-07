"""Turn a Recommendation into a concrete, plain-Hebrew action plan.

This is the "what should I actually do, and how" layer. It is intentionally
general and educational — position-size figures are common rules of thumb,
NOT personal financial advice.
"""

from __future__ import annotations

from typing import Iterable

from .broker import enrich_portfolio_result
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


# ---------------------------------------------------------------------------
# Profile-driven ("smart") portfolio builder
# ---------------------------------------------------------------------------

# Candidate assets grouped by class.
UNIVERSE_CLASSES: dict[str, list[str]] = {
    "broad": ["SPY", "QQQ"],                              # broad market ETFs
    "growth": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META"],  # large-cap growth
    "sectors": ["XLK", "XLV", "XLF", "XLE"],             # tech/health/finance/energy
    "bonds": ["TLT"],                                     # long-term treasuries
    "diversifier": ["GC=F"],                             # gold
    "israel": ["EIS"],                                   # iShares MSCI Israel ETF
    "crypto": ["BTC-USD", "ETH-USD"],                    # crypto
}

# Short, human-friendly Hebrew names for each candidate ticker.
TICKER_HE: dict[str, str] = {
    "SPY": "מדד S&P 500 (500 החברות הגדולות בארה\"ב)",
    "QQQ": "מדד נאסד\"ק 100 (חברות טכנולוגיה מובילות)",
    "AAPL": "אפל", "MSFT": "מיקרוסופט", "NVDA": "אנבידיה",
    "GOOGL": "גוגל (Alphabet)", "AMZN": "אמזון", "META": "מטא (פייסבוק)",
    "XLK": "מגזר הטכנולוגיה (ETF)", "XLV": "מגזר הבריאות (ETF)",
    "XLF": "מגזר הפיננסים (ETF)", "XLE": "מגזר האנרגיה (ETF)",
    "TLT": "אג\"ח ממשלת ארה\"ב ארוכות (הגנה)",
    "GC=F": "זהב", "EIS": "מדד ישראל (iShares Israel ETF)",
    "BTC-USD": "ביטקוין", "ETH-USD": "אתריום",
}

# Class -> Hebrew role, so the user understands *why* each asset is there.
CLASS_HE: dict[str, str] = {
    "broad": "עוגן התיק — מדד רחב ומפוזר",
    "growth": "מנוע צמיחה — מניה מובילה",
    "sectors": "פיזור מגזרי — חשיפה לענף שלם",
    "bonds": "כרית ביטחון — אג\"ח ממשלתי",
    "diversifier": "הגנה מפני אינפלציה/משברים — זהב",
    "israel": "חשיפה מקומית — שוק ישראל",
    "crypto": "רכיב ספקולטיבי — קריפטו (סיכון גבוה)",
}

# Class -> short label + plain explanation for beginners ("what is this?").
CLASS_LABEL_HE: dict[str, str] = {
    "broad": "מדדים רחבים",
    "growth": "מניות צמיחה",
    "sectors": "מגזרים",
    "bonds": "אג\"ח ממשלתי",
    "diversifier": "זהב",
    "israel": "ישראל",
    "crypto": "קריפטו",
}
CLASS_INFO_HE: dict[str, str] = {
    "broad": "קרן שעוקבת אחרי מדד שלם (עשרות עד מאות חברות בבת אחת). הדרך הפשוטה והמפוזרת ביותר להשקיע בשוק — כשהכלכלה עולה, גם המדד עולה.",
    "growth": "מניה של חברה בודדת גדולה וצומחת (כמו אפל או אנבידיה). פוטנציאל רווח גבוה, אבל תנודתית יותר ממדד כי הכל תלוי בחברה אחת.",
    "sectors": "קרן שמשקיעה בענף שלם — למשל טכנולוגיה (XLK), בריאות (XLV), פיננסים (XLF) או אנרגיה (XLE). מאפשר להמר על תחום מסוים בלי לבחור מניה בודדת.",
    "bonds": "הלוואה לממשלת ארה\"ב שמחזירה ריבית קבועה. יציב יחסית ונוטה לעלות דווקא כשמניות יורדות — לכן משמש ככרית ביטחון בתיק.",
    "diversifier": "זהב — נכס מחסה קלאסי ששומר על ערך בזמן משברים ואינפלציה, וזז לרוב אחרת ממניות.",
    "israel": "קרן שעוקבת אחרי המניות המובילות בישראל. נותנת חשיפה לשוק המקומי לצד השוק האמריקאי.",
    "crypto": "מטבע דיגיטלי (ביטקוין/אתריום). סיכוי גבוה לרווח אך תנודתיות קיצונית — לכן מוגבל לחלק קטן מהתיק בלבד.",
}

# Base split across classes for the invested portion, by goal.
# Each goal must sum to ~1.0 across its classes.
GOAL_CLASS_ALLOC: dict[str, dict[str, float]] = {
    "growth":   {"broad": 0.22, "growth": 0.40, "sectors": 0.18, "bonds": 0.00,
                 "diversifier": 0.05, "israel": 0.05, "crypto": 0.10},
    "balanced": {"broad": 0.32, "growth": 0.20, "sectors": 0.16, "bonds": 0.08,
                 "diversifier": 0.09, "israel": 0.05, "crypto": 0.10},
    "preserve": {"broad": 0.40, "growth": 0.08, "sectors": 0.10, "bonds": 0.22,
                 "diversifier": 0.15, "israel": 0.05, "crypto": 0.00},
}

CASH_BY_HORIZON = {"short": 0.40, "medium": 0.15, "long": 0.05}
RISK_CASH_ADJ = {"low": 0.15, "medium": 0.0, "high": -0.05}
ASSET_CAP = {"low": 0.15, "medium": 0.25, "high": 0.35}
CRYPTO_CAP = {"low": 0.0, "medium": 0.10, "high": 0.25}

HORIZON_HE = {"short": "טווח קצר (עד שנתיים)", "medium": "טווח בינוני (2-5 שנים)", "long": "טווח ארוך (5+ שנים)"}
GOAL_HE = {"growth": "צמיחה", "balanced": "מאוזן", "preserve": "שימור הון"}
RISK_WORD_HE = {"low": "נמוך", "medium": "בינוני", "high": "גבוה"}


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def advisor_universe(goal: str, risk: str, include_crypto: bool) -> tuple[list[str], dict, dict]:
    """Return (tickers, class_of_ticker, base_weight_of_ticker) for a profile."""
    goal = goal if goal in GOAL_CLASS_ALLOC else "balanced"
    alloc = dict(GOAL_CLASS_ALLOC[goal])
    if not include_crypto or risk == "low":
        c = alloc.get("crypto", 0.0)
        alloc["crypto"] = 0.0
        alloc["broad"] += c * 0.6
        alloc["diversifier"] += c * 0.4

    tickers: list[str] = []
    class_of: dict[str, str] = {}
    base_of: dict[str, float] = {}
    for cls, share in alloc.items():
        if share <= 0:
            continue
        members = UNIVERSE_CLASSES[cls]
        per = share / len(members)
        for t in members:
            tickers.append(t)
            class_of[t] = cls
            base_of[t] = per
    return tickers, class_of, base_of


def build_advisor(profile: dict, recs: Iterable[Recommendation], amount: float) -> dict:
    """Build a personalized portfolio from a profile + committee scores.

    profile keys: horizon (short/medium/long), risk (low/medium/high),
    goal (growth/balanced/preserve), include_crypto (bool).
    """
    horizon = profile.get("horizon", "medium")
    risk = profile.get("risk", "medium")
    goal = profile.get("goal", "balanced")
    include_crypto = bool(profile.get("include_crypto", False))

    cash_frac = _clamp(CASH_BY_HORIZON.get(horizon, 0.15) + RISK_CASH_ADJ.get(risk, 0.0), 0.0, 0.7)
    invested_frac = 1.0 - cash_frac

    _, class_of, base_of = advisor_universe(goal, risk, include_crypto)

    # Adjust base weights by the committee's current view.
    adj: dict[str, float] = {}
    rec_by_ticker: dict[str, Recommendation] = {}
    for r in recs:
        rec_by_ticker[r.ticker] = r
        base = base_of.get(r.ticker, 0.0)
        if base <= 0:
            continue
        if r.score <= -0.5:
            factor = 0.0  # avoid strong-sell assets entirely
        else:
            factor = max(0.2, min(2.0, 1.0 + r.score)) * max(0.3, r.confidence)
        adj[r.ticker] = base * factor

    total = sum(adj.values())
    reasoning = _advisor_reasoning(horizon, risk, goal, include_crypto, cash_frac)

    if total <= 0 or amount <= 0:
        return {
            "amount": amount, "invested": 0.0, "cash": round(max(amount, 0.0), 2),
            "allocations": [], "reasoning": reasoning,
            "note": "לפי הפרופיל והניתוח הנוכחי עדיף להחזיק מזומן ולהמתין.",
        }

    # Normalize to the invested fraction, then apply caps (excess -> cash).
    target = {t: adj[t] / total * invested_frac for t in adj}
    asset_cap = ASSET_CAP.get(risk, 0.25)
    for t in list(target):
        target[t] = min(target[t], asset_cap)

    crypto_ts = [t for t in target if class_of.get(t) == "crypto"]
    csum = sum(target[t] for t in crypto_ts)
    crypto_cap = CRYPTO_CAP.get(risk, 0.1)
    if csum > crypto_cap and csum > 0:
        scale = crypto_cap / csum
        for t in crypto_ts:
            target[t] *= scale

    allocations = []
    invested = 0.0
    for t, frac in target.items():
        amt = round(amount * frac, 2)
        if amt <= 0:
            continue
        invested += amt
        r = rec_by_ticker[t]
        cls = class_of.get(t, "")
        allocations.append(
            {
                "ticker": t, "weight_pct": round(frac * 100, 1), "amount": amt,
                "score_pct": r.score_pct, "action": r.action.value, "price": r.price,
                "cls": cls,
                "name_he": TICKER_HE.get(t, t),
                "role_he": CLASS_HE.get(cls, ""),
                "why": _alloc_why(r, cls),
            }
        )
    allocations.sort(key=lambda a: a["amount"], reverse=True)
    cash = round(amount - invested, 2)

    # Beginner glossary: explain only the classes that actually appear.
    glossary = []
    seen: set[str] = set()
    for a in allocations:
        cls = a["cls"]
        if cls and cls not in seen:
            seen.add(cls)
            glossary.append({
                "cls": cls,
                "label": CLASS_LABEL_HE.get(cls, cls),
                "info": CLASS_INFO_HE.get(cls, ""),
            })

    result = {
        "amount": amount, "invested": round(invested, 2), "cash": cash,
        "allocations": allocations, "reasoning": reasoning, "glossary": glossary,
        "note": "החלוקה נבנתה מהפרופיל שלך יחד עם הציונים העדכניים של הסוכנים. חומר חינוכי בלבד.",
    }
    return enrich_portfolio_result(result, profile, recs)


def _alloc_why(rec: Recommendation, cls: str) -> str:
    """One short line explaining why this asset earned its slot."""
    role = CLASS_HE.get(cls, "רכיב בתיק")
    if rec.score >= 0.35:
        view = "הסוכנים חיוביים עליו כרגע"
    elif rec.score >= 0.1:
        view = "הסוכנים חיוביים במידה מתונה"
    elif rec.score >= -0.1:
        view = "הסוכנים נייטרליים — נכלל בעיקר לפיזור"
    else:
        view = "הסוכנים פושרים — משקל מוקטן, נכלל לפיזור"
    return f"{role}. {view}."


def _advisor_reasoning(horizon, risk, goal, include_crypto, cash_frac) -> list[str]:
    out = [
        f"מטרה: {GOAL_HE.get(goal, goal)} · {HORIZON_HE.get(horizon, horizon)} · סיכון {RISK_WORD_HE.get(risk, risk)}.",
        f"רכיב מזומן מתוכנן: כ-{round(cash_frac * 100)}% "
        + ("(טווח קצר — שומרים יותר נזילות)." if horizon == "short"
           else "(טווח ארוך — כמעט הכל מושקע)." if horizon == "long" else "."),
    ]
    if goal == "growth":
        out.append("הטיה למניות צמיחה ולמגזרי טכנולוגיה להאצת תשואה פוטנציאלית.")
    elif goal == "preserve":
        out.append("דגש על מדדים רחבים, אג\"ח ממשלתי וזהב לשמירה על יציבות.")
    else:
        out.append("איזון בין מדדים רחבים, מניות צמיחה, מגזרים, אג\"ח וזהב.")
    out.append("התיק מפוזר על פני כמה סוגי נכסים (מדדים, מניות, מגזרים, אג\"ח, זהב, ישראל) כדי לא לשים את כל הביצים בסל אחד.")
    if risk == "low":
        out.append("סיכון נמוך: הגבלנו כל נכס ל-15% ולא כללנו קריפטו.")
    elif risk == "high":
        out.append("סיכון גבוה: אפשרנו חשיפה גדולה יותר לנכס בודד וקריפטו עד 25%.")
    else:
        out.append("סיכון בינוני: תקרה של 25% לנכס וקריפטו עד 10%.")
    if include_crypto and risk != "low":
        out.append("כללת קריפטו בתיק (מוגבל לפי רמת הסיכון).")
    elif include_crypto and risk == "low":
        out.append("ביקשת קריפטו, אך ברמת סיכון נמוכה השמטנו אותו מטעמי בטיחות.")
    out.append("הנכסים החלשים לפי הניתוח קיבלו משקל נמוך יותר (או הושמטו).")
    return out


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
            "amount": round(max(amount, 0.0), 2),
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
    return enrich_portfolio_result(
        {
            "amount": amount,
            "invested": round(invested, 2),
            "cash": cash,
            "allocations": allocations,
            "excluded": excluded,
            "note": note,
        },
        {"horizon": "medium", "risk": "medium", "goal": "balanced"},
        recs,
    )
