"""Command-line interface for the investment agents system.

Examples:
    python -m investment_agents.cli analyze AAPL MSFT NVDA
    python -m investment_agents.cli rank AAPL MSFT BTC-USD SPY --top 5
    python -m investment_agents.cli backtest AAPL --fast 20 --slow 50
    python -m investment_agents.cli paper AAPL MSFT --budget 1000
"""

from __future__ import annotations

import argparse
import sys

# Windows terminals often default to a legacy code page (e.g. cp1255) that
# cannot encode Hebrew + emoji. Force UTF-8 so output never crashes.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .advice import action_plan
from .config import Action, Recommendation, settings
from .explain import explain_recommendation
from .orchestrator import Committee
from .portfolio import Portfolio, backtest_sma_cross, rebalance_with_committee
from .scanner import scan_market
from .universe import SECTOR_NAMES, get_universe

console = Console()

ACTION_STYLE = {
    Action.STRONG_BUY: "bold green",
    Action.BUY: "green",
    Action.HOLD: "yellow",
    Action.SELL: "red",
    Action.STRONG_SELL: "bold red",
}

DISCLAIMER = (
    "[dim]For research/education only. This is NOT financial advice. "
    "Trade at your own risk.[/dim]"
)


def _print_recommendation(rec: Recommendation, detailed: bool = True) -> None:
    style = ACTION_STYLE.get(rec.action, "white")
    price = f"{rec.price:.2f}" if rec.price is not None else "N/A"
    header = (
        f"[{style}]{rec.action.value}[/{style}]  "
        f"{rec.ticker}  price={price}  "
        f"score={rec.score_pct:+d}%  confidence={rec.confidence * 100:.0f}%"
    )
    if not detailed:
        console.print(header)
        return

    table = Table(show_header=True, header_style="bold cyan", expand=True)
    table.add_column("Agent", style="cyan", no_wrap=True)
    table.add_column("Score", justify="right")
    table.add_column("Conf.", justify="right")
    table.add_column("Reasons")
    for s in rec.signals:
        table.add_row(
            s.agent,
            f"{s.score * 100:+.0f}%",
            f"{s.confidence * 100:.0f}%",
            "\n".join(f"• {r}" for r in s.reasons) or "-",
        )
    console.print(Panel(table, title=header, border_style=style))


def cmd_analyze(args: argparse.Namespace) -> None:
    committee = Committee()
    for ticker in args.tickers:
        with console.status(f"Analyzing {ticker}..."):
            rec = committee.analyze(ticker)
        _print_recommendation(rec, detailed=not args.brief)


def cmd_simple(args: argparse.Namespace) -> None:
    """Beginner-friendly plain-Hebrew verdict, no jargon."""
    committee = Committee()
    for ticker in args.tickers:
        with console.status(f"בודק את {ticker}..."):
            rec = committee.analyze(ticker)
        info = explain_recommendation(rec)
        price = f"{rec.price:,.2f}" if rec.price is not None else "N/A"
        body = (
            f"[bold]{info['emoji']}  {info['verdict']}[/bold]  ({info['score_pct']:+d}%)\n"
            f"{info['subtitle']}\n"
            f"[dim]{info['confidence_word']} · מחיר: {price}[/dim]\n\n"
            f"{info['summary']}\n\n"
        )
        for line in info["signal_lines"]:
            body += f"{line['emoji']} {line['role']} — {line['mood']}\n"

        plan = action_plan(rec)
        body += f"\n[bold]🎯 מה לעשות: {plan['headline']}[/bold]  ([dim]{plan['risk_level']}[/dim])\n"
        for step in plan["steps"]:
            body += f"  ➤ {step}\n"

        console.print(Panel(body.rstrip(), title=ticker, border_style=info["color"]))


def cmd_rank(args: argparse.Namespace) -> None:
    committee = Committee()
    with console.status(f"Analyzing {len(args.tickers)} assets..."):
        recs = committee.rank(args.tickers)

    table = Table(title="Ranked recommendations (best first)", header_style="bold cyan")
    table.add_column("#", justify="right")
    table.add_column("Ticker")
    table.add_column("Action")
    table.add_column("Score", justify="right")
    table.add_column("Conf.", justify="right")
    table.add_column("Price", justify="right")
    for i, rec in enumerate(recs[: args.top], 1):
        style = ACTION_STYLE.get(rec.action, "white")
        price = f"{rec.price:.2f}" if rec.price is not None else "N/A"
        table.add_row(
            str(i),
            rec.ticker,
            f"[{style}]{rec.action.value}[/{style}]",
            f"{rec.score_pct:+d}%",
            f"{rec.confidence * 100:.0f}%",
            price,
        )
    console.print(table)


def cmd_backtest(args: argparse.Namespace) -> None:
    for ticker in args.tickers:
        with console.status(f"Backtesting {ticker}..."):
            res = backtest_sma_cross(ticker, args.fast, args.slow)
        console.print(
            Panel(
                f"Strategy return: [bold]{res.total_return * 100:+.1f}%[/bold]\n"
                f"Buy & hold:      {res.buy_hold_return * 100:+.1f}%\n"
                f"Trades:          {res.n_trades}",
                title=f"SMA {args.fast}/{args.slow} backtest — {ticker}",
                border_style="cyan",
            )
        )


def cmd_paper(args: argparse.Namespace) -> None:
    pf = Portfolio.load(args.file)
    log = rebalance_with_committee(pf, args.tickers, buy_budget_per_name=args.budget)
    pf.save(args.file)

    console.print(Panel("\n".join(log) or "No actions taken.", title="Paper trades", border_style="green"))
    # Value the portfolio at last prices we already fetched via the committee.
    from .data import get_asset

    prices = {t: (get_asset(t).last_price or 0.0) for t in list(pf.positions.keys())}
    equity = pf.market_value(prices)
    console.print(
        f"Cash: [bold]{pf.cash:,.2f}[/bold]  |  "
        f"Positions: {len(pf.positions)}  |  "
        f"Total equity: [bold]{equity:,.2f}[/bold]"
    )


def cmd_scan(args: argparse.Namespace) -> None:
    """Market scanner: sweep the universe and rank opportunities."""
    committee = Committee()
    sector = args.sector if args.sector in SECTOR_NAMES else None
    label = sector or "כל השוק"
    with console.status(f"📡 הסוכנים סורקים את {label}..."):
        result = scan_market(committee, sector=sector, top=args.top)

    console.print(
        Panel(
            "\n".join(f"• {g}" for g in result["guidance"]),
            title=f"📡 סריקת שוק — {result['sector']} ({result['scanned']} נכסים)",
            border_style="cyan",
        )
    )

    table = Table(title="הזדמנויות מובילות", header_style="bold cyan")
    table.add_column("#", justify="right")
    table.add_column("נכס")
    table.add_column("מגזר")
    table.add_column("ציון", justify="right")
    table.add_column("פעולה")
    for i, o in enumerate(result["top"], 1):
        table.add_row(
            str(i),
            f"{o['emoji']} {o['name_he']} ({o['ticker']})",
            o["sector"],
            f"{o['score_pct']:+d}%",
            o["verdict"],
        )
    console.print(table)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="investment_agents",
        description="Multi-agent investment analysis (research/education only).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    sc = sub.add_parser("scan", help="Scan the market with all agents")
    sc.add_argument("--sector", default="", help="Hebrew sector name (empty = all)")
    sc.add_argument("--top", type=int, default=12)
    sc.set_defaults(func=cmd_scan)

    s = sub.add_parser("simple", help="Beginner-friendly plain-Hebrew verdict")
    s.add_argument("tickers", nargs="+")
    s.set_defaults(func=cmd_simple)

    a = sub.add_parser("analyze", help="Full committee analysis for one or more tickers")
    a.add_argument("tickers", nargs="+")
    a.add_argument("--brief", action="store_true", help="One line per ticker")
    a.set_defaults(func=cmd_analyze)

    r = sub.add_parser("rank", help="Rank several assets best-to-worst")
    r.add_argument("tickers", nargs="+")
    r.add_argument("--top", type=int, default=20)
    r.set_defaults(func=cmd_rank)

    b = sub.add_parser("backtest", help="SMA-cross backtest on historical data")
    b.add_argument("tickers", nargs="+")
    b.add_argument("--fast", type=int, default=20)
    b.add_argument("--slow", type=int, default=50)
    b.set_defaults(func=cmd_backtest)

    pp = sub.add_parser("paper", help="Run one paper-trading rebalance step")
    pp.add_argument("tickers", nargs="+")
    pp.add_argument("--budget", type=float, default=1_000.0, help="Cash per BUY name")
    pp.add_argument("--file", default="portfolio.json")
    pp.set_defaults(func=cmd_paper)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    console.print(DISCLAIMER)
    if settings.llm_enabled:
        prov = settings.llm_provider
        console.print(f"[dim]AI advisor: ON ({prov})[/dim]")
    else:
        console.print("[dim]AI advisor: OFF (set GEMINI_API_KEY or OPENAI_API_KEY)[/dim]")

    args.func(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
