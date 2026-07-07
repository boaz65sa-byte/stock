"""Portfolio alert detection and Telegram push delivery."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Optional

from .config import settings


def alert_digest(alerts: list[dict]) -> str:
    """Stable fingerprint for a set of alerts (Telegram de-duplication)."""
    parts = sorted(f"{a['type']}:{a.get('ticker')}:{a['title_he']}" for a in alerts)
    return "|".join(parts)


def evaluate_alerts(
    current: dict,
    previous: Optional[dict],
    alert_settings: Optional[dict] = None,
) -> list[dict]:
    """Compare two portfolio snapshots and return human-readable alerts."""
    cfg = alert_settings or {}
    day_thr = float(cfg.get("day_pct", 3.0))
    pnl_thr = float(cfg.get("pnl_pct", 5.0))
    urgent_only = bool(cfg.get("urgent_only", False))

    alerts: list[dict] = []
    prev_positions = {}
    if previous and previous.get("positions"):
        prev_positions = {p["ticker"]: p for p in previous["positions"]}

    # Guardian-level alert.
    g = current.get("guardian") or {}
    mood = g.get("mood", "calm")
    if mood == "alert":
        alerts.append(
            _alert(
                "high",
                "guardian",
                None,
                "⚠️ פעולה דחופה בתיק",
                g.get("headline", "הסוכן ממליץ לפעול"),
            )
        )
    elif mood == "caution" and not urgent_only:
        alerts.append(
            _alert(
                "medium",
                "guardian",
                None,
                "שים לב — התיק",
                g.get("headline", ""),
            )
        )

    # Total P&L swing since last check.
    if previous is not None:
        prev_total = previous.get("total_pnl_pct", 0)
        cur_total = current.get("total_pnl_pct", 0)
        delta = cur_total - prev_total
        if abs(delta) >= pnl_thr:
            direction = "עלה" if delta > 0 else "ירד"
            alerts.append(
                _alert(
                    "medium" if abs(delta) < pnl_thr * 2 else "high",
                    "portfolio_pnl",
                    None,
                    f"התיק {direction} {abs(delta):.1f}%",
                    f"רווח/הפסד כולל: {cur_total:+.1f}% (לפני: {prev_total:+.1f}%)",
                )
            )

    for p in current.get("positions") or []:
        ticker = p["ticker"]
        advice = p.get("advice") or {}
        code = advice.get("code", "hold")
        urgency = advice.get("urgency", "low")

        # Exit / reduce signals.
        if code == "exit":
            alerts.append(
                _alert(
                    "high",
                    "exit",
                    ticker,
                    f"🚪 לשקול יציאה — {p.get('name_he', ticker)}",
                    f"{advice.get('reasons', [''])[0]} · P&L {p.get('pnl_pct', 0):+.1f}%",
                )
            )
        elif code == "reduce" and not urgent_only:
            alerts.append(
                _alert(
                    "medium",
                    "reduce",
                    ticker,
                    f"📉 לצמצם — {p.get('name_he', ticker)}",
                    f"רווח {p.get('pnl_pct', 0):+.1f}% · {advice.get('reasons', [''])[0]}",
                )
            )

        # Intraday move.
        day = p.get("day_change_pct")
        if day is not None and abs(day) >= day_thr:
            if day > 0:
                alerts.append(
                    _alert(
                        "medium",
                        "day_spike",
                        ticker,
                        f"📈 {p.get('name_he', ticker)} קפץ {day:+.1f}% היום",
                        f"מחיר ${p.get('current_price')} · P&L כולל {p.get('pnl_pct', 0):+.1f}%",
                    )
                )
            else:
                alerts.append(
                    _alert(
                        "high" if day <= -day_thr * 1.5 else "medium",
                        "day_drop",
                        ticker,
                        f"📉 {p.get('name_he', ticker)} ירד {day:.1f}% היום",
                        f"מחיר ${p.get('current_price')} · P&L כולל {p.get('pnl_pct', 0):+.1f}%",
                    )
                )

        # Advice turned worse since last check.
        prev = prev_positions.get(ticker)
        if prev:
            prev_code = (prev.get("advice") or {}).get("code", "hold")
            if prev_code not in ("exit", "reduce") and code in ("exit", "reduce"):
                alerts.append(
                    _alert(
                        "high",
                        "signal_change",
                        ticker,
                        f"🔔 שינוי איתות — {p.get('name_he', ticker)}",
                        f"הקודם: {prev_code} → עכשיו: {advice.get('label_he', code)}",
                    )
                )
            prev_score = prev.get("score_pct", 0)
            cur_score = p.get("score_pct", 0)
            if cur_score <= -15 and prev_score > -5:
                alerts.append(
                    _alert(
                        "medium",
                        "score_drop",
                        ticker,
                        f"👎 הסוכנים התהפכו שליליים — {p.get('name_he', ticker)}",
                        f"ציון {cur_score:+d}% (היה {prev_score:+d}%)",
                    )
                )

        if urgent_only and urgency != "high" and code not in ("exit",):
            continue

    # De-duplicate by title+ticker.
    seen: set[str] = set()
    unique: list[dict] = []
    for a in alerts:
        key = f"{a['type']}:{a.get('ticker')}:{a['title_he']}"
        if key not in seen:
            seen.add(key)
            unique.append(a)

    unique.sort(key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["level"]])
    return unique


def _alert(level: str, typ: str, ticker: Optional[str], title: str, body: str) -> dict:
    return {
        "level": level,
        "type": typ,
        "ticker": ticker,
        "title_he": title,
        "body_he": body,
        "telegram_line": f"{title}\n{body}",
    }


def telegram_configured() -> bool:
    return bool(settings.telegram_bot_token)


def send_telegram(chat_id: str, text: str) -> dict:
    """Send one message via Telegram Bot API."""
    token = settings.telegram_bot_token
    if not token:
        return {"ok": False, "error": "telegram_not_configured"}
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = json.dumps(
        {"chat_id": chat_id, "text": text[:4000], "parse_mode": "HTML"},
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            return {"ok": data.get("ok", False), "result": data}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode() if exc.fp else str(exc)
        return {"ok": False, "error": body[:300]}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}


def format_telegram_digest(alerts: list[dict], portfolio_summary: str) -> str:
    if not alerts:
        return ""
    lines = ["<b>📱 התראות תיק — Investment Agents</b>", portfolio_summary, ""]
    for a in alerts[:8]:
        icon = "🔴" if a["level"] == "high" else "🟡" if a["level"] == "medium" else "🟢"
        lines.append(f"{icon} <b>{a['title_he']}</b>")
        lines.append(a["body_he"])
        lines.append("")
    lines.append("<i>חינוכי בלבד — לא ייעוץ השקעות</i>")
    return "\n".join(lines)
