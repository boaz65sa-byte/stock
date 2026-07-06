"""Resolve free-text asset names (Hebrew or English) into Yahoo Finance tickers.

This lets users type "טסלה" or "נאסד\"ק" instead of memorizing symbols.
Also detects well-known *private* companies (e.g. Anthropic) that are not
traded on any exchange, so we can show a clear message instead of "no data".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# name (lowercased) -> Yahoo Finance ticker.
# Hebrew has no letter case, so .lower() leaves Hebrew keys unchanged.
NAME_TO_TICKER: dict[str, str] = {
    # --- US stocks ---
    "אפל": "AAPL", "apple": "AAPL",
    "מיקרוסופט": "MSFT", "microsoft": "MSFT",
    "אנבידיה": "NVDA", "nvidia": "NVDA",
    "טסלה": "TSLA", "tesla": "TSLA",
    "אמזון": "AMZN", "amazon": "AMZN",
    "גוגל": "GOOGL", "google": "GOOGL", "alphabet": "GOOGL", "אלפאבית": "GOOGL",
    "מטא": "META", "meta": "META", "פייסבוק": "META", "facebook": "META",
    "נטפליקס": "NFLX", "netflix": "NFLX",
    "אינטל": "INTC", "intel": "INTC",
    "amd": "AMD", "איי.אם.די": "AMD",
    "ברודקום": "AVGO", "broadcom": "AVGO",
    "פלנטיר": "PLTR", "palantir": "PLTR",
    "קוקה קולה": "KO", "coca cola": "KO", "coca-cola": "KO", "קוקהקולה": "KO",
    "מקדונלדס": "MCD", "mcdonalds": "MCD", "mcdonald's": "MCD",
    "דיסני": "DIS", "disney": "DIS",
    "וולמארט": "WMT", "walmart": "WMT",
    "נייקי": "NKE", "nike": "NKE",
    "סטארבקס": "SBUX", "starbucks": "SBUX",
    "בואינג": "BA", "boeing": "BA",
    "פייפאל": "PYPL", "paypal": "PYPL",
    "אובר": "UBER", "uber": "UBER",
    "איירביאנבי": "ABNB", "airbnb": "ABNB",
    "ג'יי פי מורגן": "JPM", "jpmorgan": "JPM", "jp morgan": "JPM",
    "ויזה": "V", "visa": "V",
    "מאסטרקארד": "MA", "mastercard": "MA",
    # --- Israeli stocks (Tel Aviv, .TA) ---
    "טבע": "TEVA.TA", "teva": "TEVA.TA",
    "בנק הפועלים": "POLI.TA", "פועלים": "POLI.TA",
    "בנק לאומי": "LUMI.TA", "לאומי": "LUMI.TA",
    "נייס": "NICE.TA", "nice": "NICE.TA",
    "אלביט": "ESLT.TA", "elbit": "ESLT.TA", "אלביט מערכות": "ESLT.TA",
    # --- Crypto ---
    "ביטקוין": "BTC-USD", "bitcoin": "BTC-USD", "בטקוין": "BTC-USD", "btc": "BTC-USD",
    "אתריום": "ETH-USD", "ethereum": "ETH-USD", "את'ריום": "ETH-USD", "eth": "ETH-USD",
    "סולנה": "SOL-USD", "solana": "SOL-USD",
    "דוג'קוין": "DOGE-USD", "dogecoin": "DOGE-USD", "דוגקוין": "DOGE-USD",
    "קרדנו": "ADA-USD", "cardano": "ADA-USD",
    "ריפל": "XRP-USD", "ripple": "XRP-USD", "xrp": "XRP-USD",
    # --- Indices / ETFs ---
    "מדד s&p 500": "SPY", "s&p 500": "SPY", "sp500": "SPY", "אס אנד פי": "SPY",
    "אס אנד פי 500": "SPY", "מדד 500": "SPY", "ספי": "SPY",
    "נאסדק": "QQQ", "נאסד\"ק": "QQQ", "nasdaq": "QQQ", "קיו קיו קיו": "QQQ",
    "דאו": "DIA", "דאו ג'ונס": "DIA", "dow": "DIA", "dow jones": "DIA",
    "ראסל": "IWM", "ראסל 2000": "IWM", "russell": "IWM", "russell 2000": "IWM",
    "ת\"א 125": "^TA125.TA", "תא 125": "^TA125.TA", "מדד תל אביב": "^TA125.TA",
    # --- Commodities (futures) ---
    "זהב": "GC=F", "gold": "GC=F",
    "כסף": "SI=F", "silver": "SI=F",
    "נפט": "CL=F", "oil": "CL=F", "wti": "CL=F",
    "גז טבעי": "NG=F", "natural gas": "NG=F",
}

# Well-known private companies (not publicly traded) -> display name.
PRIVATE_COMPANIES: dict[str, str] = {
    "אנתרופיק": "Anthropic", "אנטרופיק": "Anthropic", "anthropic": "Anthropic",
    "openai": "OpenAI", "אופן איי איי": "OpenAI", "אופנאיי": "OpenAI", "או-פן איי איי": "OpenAI",
    "spacex": "SpaceX", "ספייסאקס": "SpaceX", "ספייס אקס": "SpaceX",
    "stripe": "Stripe", "סטרייפ": "Stripe",
    "bytedance": "ByteDance", "בייטדאנס": "ByteDance", "טיקטוק": "TikTok (ByteDance)", "tiktok": "TikTok (ByteDance)",
    "databricks": "Databricks", "דאטהבריקס": "Databricks",
    "revolut": "Revolut", "רבולוט": "Revolut",
    "xai": "xAI", "אקס איי איי": "xAI",
}


@dataclass
class Resolved:
    ticker: Optional[str]        # resolved Yahoo ticker, or None if not tradable
    query: str                   # the original user input
    private_name: Optional[str] = None  # display name if it's a known private company


def to_ticker(query: str) -> str:
    """Best-effort: turn a name/symbol into a ticker (returns input if unknown)."""
    q = (query or "").strip()
    if not q:
        return ""
    key = q.lower()
    if key in NAME_TO_TICKER:
        return NAME_TO_TICKER[key]
    return q.upper()


def resolve(query: str) -> Resolved:
    """Full resolution including private-company detection."""
    q = (query or "").strip()
    if not q:
        return Resolved(ticker=None, query=q)
    key = q.lower()
    if key in PRIVATE_COMPANIES:
        return Resolved(ticker=None, query=q, private_name=PRIVATE_COMPANIES[key])
    return Resolved(ticker=to_ticker(q), query=q)
