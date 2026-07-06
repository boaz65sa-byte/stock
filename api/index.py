"""FastAPI serverless API for Vercel.

Exposes the multi-agent analysis as JSON endpoints. Vercel's Python runtime
detects the top-level ``app`` (ASGI) object and serves it automatically.

Endpoints:
    GET /api/health
    GET /api/analyze?ticker=AAPL&period=1y
    GET /api/rank?tickers=AAPL,MSFT,BTC-USD&period=1y
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make the repository root importable so ``investment_agents`` resolves both
# locally (uvicorn api.index:app) and on Vercel (bundled via includeFiles).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import HTMLResponse, JSONResponse  # noqa: E402

from investment_agents.config import settings  # noqa: E402
from investment_agents.data import get_asset  # noqa: E402
from investment_agents.explain import explain_recommendation  # noqa: E402
from investment_agents.orchestrator import Committee  # noqa: E402

app = FastAPI(title="Investment Agents API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

_committee = Committee()


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    """Serve the frontend for local development.

    On Vercel this route is never reached because ``vercel.json`` routes all
    non-``/api`` paths to the static ``index.html`` directly.
    """
    index_path = Path(__file__).resolve().parent.parent / "index.html"
    try:
        return HTMLResponse(index_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return HTMLResponse("<h1>index.html not found</h1>", status_code=404)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "llm_enabled": settings.llm_enabled}


@app.get("/api/analyze")
def analyze(ticker: str = Query(..., min_length=1), period: str = Query("1y")) -> JSONResponse:
    ticker = ticker.strip().upper()
    settings.history_period = period
    try:
        asset = get_asset(ticker, period=period)
    except Exception as exc:  # network / bad symbol
        return JSONResponse(status_code=502, content={"error": f"fetch failed: {type(exc).__name__}"})

    if not asset.is_valid:
        return JSONResponse(status_code=404, content={"error": "no_data", "ticker": ticker})

    rec = _committee.analyze_asset(asset)
    info = explain_recommendation(rec)

    hist = asset.close.tail(180)
    return JSONResponse(
        content={
            "ticker": rec.ticker,
            "price": rec.price,
            "action": rec.action.value,
            "score_pct": rec.score_pct,
            "emoji": info["emoji"],
            "verdict": info["verdict"],
            "subtitle": info["subtitle"],
            "color": info["color"],
            "confidence_word": info["confidence_word"],
            "summary": info["summary"],
            "signals": info["signal_lines"],
            "history": {
                "dates": [d.strftime("%Y-%m-%d") for d in hist.index],
                "prices": [round(float(p), 2) for p in hist.values],
            },
        }
    )


@app.get("/api/rank")
def rank(tickers: str = Query(...), period: str = Query("1y")) -> JSONResponse:
    settings.history_period = period
    tks = [t.strip().upper() for t in tickers.split(",") if t.strip()][:8]
    if not tks:
        return JSONResponse(status_code=400, content={"error": "no_tickers"})

    recs = _committee.rank(tks)
    out = []
    for r in recs:
        info = explain_recommendation(r)
        out.append(
            {
                "ticker": r.ticker,
                "action": r.action.value,
                "score_pct": r.score_pct,
                "verdict": info["verdict"],
                "emoji": info["emoji"],
                "color": info["color"],
                "price": r.price,
            }
        )
    return JSONResponse(content={"results": out})
