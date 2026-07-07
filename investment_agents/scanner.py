"""Market scanner: the agent battery sweeps the universe and surfaces guidance.

Coordinates the committee over a broad ticker list, aggregates results by
sector, and produces plain-Hebrew "where and what to invest" guidance.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from .advice import action_plan
from .config import Recommendation
from .explain import AGENT_DESC_HE, AGENT_ROLE_HE, explain_recommendation
from .orchestrator import Committee
from .universe import SECTOR_NAMES, get_universe, name_of, sector_of


def agent_roster(committee: Committee | None = None) -> list[dict]:
    """Return metadata about every agent in the battery."""
    c = committee or Committee()
    out: list[dict] = []
    for agent in c.agents:
        out.append(
            {
                "name": agent.name,
                "role_he": AGENT_ROLE_HE.get(agent.name, agent.name),
                "desc_he": AGENT_DESC_HE.get(agent.name, ""),
                "weight": agent.weight,
            }
        )
    return out


def _sector_rankings(recs: Iterable[Recommendation]) -> list[dict]:
    """Average committee score per sector, best sector first."""
    buckets: dict[str, list[float]] = defaultdict(list)
    for rec in recs:
        sec = sector_of(rec.ticker)
        if sec:
            buckets[sec].append(rec.score)
    ranked = sorted(
        (
            {"sector": sec, "avg_score_pct": int(round(sum(scores) / len(scores) * 100))}
            for sec, scores in buckets.items()
            if scores
        ),
        key=lambda x: x["avg_score_pct"],
        reverse=True,
    )
    return ranked


def _build_guidance(
    opportunities: list[dict],
    sector_ranking: list[dict],
    sector_filter: str | None,
    buy_count: int,
) -> list[str]:
    """Plain-Hebrew bullets telling the user where and what to look at."""
    lines: list[str] = []

    if sector_filter:
        lines.append(f"סרקת את מגזר {sector_filter}.")
    else:
        lines.append("סרקת את כל השוק — מניות, מדדים, סחורות וקריפטו.")

    if buy_count == 0:
        lines.append("כרגע אין איתות קנייה חזק — עדיף להמתין או להחזיק מזומן.")
        return lines

    lines.append(f"נמצאו {buy_count} נכסים עם איתות חיובי מהסוכנים.")

    if sector_ranking:
        hot = sector_ranking[0]
        lines.append(
            f"המגזר החזק ביותר כרגע: {hot['sector']} "
            f"(ממוצע ציון {hot['avg_score_pct']:+d}%)."
        )
        if len(sector_ranking) > 1:
            cold = sector_ranking[-1]
            lines.append(
                f"המגזר החלש ביותר: {cold['sector']} "
                f"(ממוצע ציון {cold['avg_score_pct']:+d}%) — עדיף זהירות שם."
            )

    top3 = [o for o in opportunities if o["score_pct"] > 0][:3]
    if top3:
        names = ", ".join(f"{o['name_he']} ({o['ticker']})" for o in top3)
        lines.append(f"3 ההזדמנויות המובילות: {names}.")

    best = opportunities[0] if opportunities else None
    if best and best["score_pct"] > 15:
        lines.append(
            f"המלצה מיידית: לבחון כניסה ל-{best['name_he']} — {best['headline']}."
        )
    elif best:
        lines.append(
            f"הכיוון הכללי חיובי אך לא חזק — אפשר לעקוב אחרי {best['name_he']} ולהמתין לאיתות ברור יותר."
        )

    lines.append("לחץ על נכס ברשימה לניתוח מלא של כל הסוכנים.")
    return lines


def scan_market(
    committee: Committee,
    sector: str | None = None,
    top: int = 12,
) -> dict:
    """Run the full market scan and return structured results + guidance."""
    sec = sector if sector in SECTOR_NAMES else None
    universe = get_universe(sec)
    recs = committee.rank(universe, with_info=False, max_workers=16)

    opportunities: list[dict] = []
    for rec in recs:
        info = explain_recommendation(rec)
        plan = action_plan(rec)
        opportunities.append(
            {
                "ticker": rec.ticker,
                "name_he": name_of(rec.ticker),
                "sector": sector_of(rec.ticker),
                "price": rec.price,
                "action": rec.action.value,
                "score_pct": rec.score_pct,
                "emoji": info["emoji"],
                "verdict": info["verdict"],
                "color": info["color"],
                "confidence_word": info["confidence_word"],
                "headline": plan["headline"],
                "risk_level": plan["risk_level"],
            }
        )

    buys = [o for o in opportunities if o["score_pct"] > 0]
    sector_ranking = _sector_rankings(recs)
    guidance = _build_guidance(opportunities, sector_ranking, sec, len(buys))

    return {
        "scanned": len(recs),
        "universe_size": len(universe),
        "sector": sec or "כל השוק",
        "top": opportunities[:top],
        "buy_count": len(buys),
        "sector_ranking": sector_ranking,
        "guidance": guidance,
        "agents": agent_roster(committee),
        "note": "הסוכנים סרקו את השוק ודירגו את הנכסים מהחזק לחלש. "
        "התוצאות הן ניתוח ממוחשב וחומר חינוכי — לא ייעוץ השקעות.",
    }
