"""A curated market universe for the scanner agents.

Instead of asking the user which tickers to check, the scanner sweeps a broad,
liquid, sector-tagged universe and lets the committee surface the best
opportunities ("where and what to invest"). Kept US-large-cap heavy for data
reliability via yfinance, with a few Israeli names and ETFs.
"""

from __future__ import annotations

# Sector (Hebrew) -> list of (ticker, Hebrew display name).
SECTORS: dict[str, list[tuple[str, str]]] = {
    "טכנולוגיה": [
        ("AAPL", "אפל"), ("MSFT", "מיקרוסופט"), ("NVDA", "אנבידיה"),
        ("GOOGL", "גוגל (Alphabet)"), ("META", "מטא (פייסבוק)"),
        ("AVGO", "ברודקום"), ("AMD", "AMD"), ("INTC", "אינטל"),
        ("ORCL", "אורקל"), ("CRM", "סיילספורס"), ("ADBE", "אדובי"),
        ("CSCO", "סיסקו"), ("QCOM", "קוואלקום"), ("PLTR", "פלנטיר"),
    ],
    "צריכה ומסחר": [
        ("AMZN", "אמזון"), ("TSLA", "טסלה"), ("HD", "הום דיפו"),
        ("MCD", "מקדונלד'ס"), ("NKE", "נייקי"), ("SBUX", "סטארבקס"),
        ("WMT", "וולמארט"), ("COST", "קוסטקו"), ("DIS", "דיסני"),
        ("KO", "קוקה קולה"), ("PEP", "פפסיקו"), ("PG", "פרוקטר אנד גמבל"),
    ],
    "פיננסים": [
        ("JPM", "ג'יי.פי מורגן"), ("BAC", "בנק אוף אמריקה"),
        ("V", "ויזה"), ("MA", "מאסטרקארד"), ("WFC", "וולס פארגו"),
        ("GS", "גולדמן זאקס"), ("MS", "מורגן סטנלי"), ("BRK-B", "ברקשייר האת'אווי"),
        ("PYPL", "פייפאל"),
    ],
    "בריאות ותרופות": [
        ("LLY", "אלי לילי"), ("JNJ", "ג'ונסון אנד ג'ונסון"),
        ("UNH", "יונייטד הלת'"), ("PFE", "פייזר"), ("MRK", "מרק"),
        ("ABBV", "אבבי"), ("TMO", "תרמו פישר"),
    ],
    "תעשייה ואנרגיה": [
        ("BA", "בואינג"), ("CAT", "קטרפילר"), ("GE", "ג'נרל אלקטריק"),
        ("XOM", "אקסון מוביל"), ("CVX", "שברון"), ("UPS", "UPS"),
    ],
    "תקשורת ובידור": [
        ("NFLX", "נטפליקס"), ("T", "AT&T"), ("VZ", "וריזון"),
        ("UBER", "אובר"), ("ABNB", "איירביאנבי"),
    ],
    "מניות ישראליות": [
        ("TEVA", "טבע (בארה\"ב)"), ("NICE", "נייס (בארה\"ב)"),
        ("MNDY", "מאנדיי"), ("GLBE", "גלובל-אי"), ("CYBR", "סייברארק"),
        ("WIX", "וויקס"),
    ],
    "מדדים וסחורות": [
        ("SPY", "מדד S&P 500"), ("QQQ", "מדד נאסד\"ק 100"),
        ("DIA", "מדד דאו ג'ונס"), ("IWM", "ראסל 2000"),
        ("GC=F", "זהב"), ("SI=F", "כסף"), ("CL=F", "נפט"),
    ],
    "קריפטו": [
        ("BTC-USD", "ביטקוין"), ("ETH-USD", "אתריום"),
        ("SOL-USD", "סולנה"), ("XRP-USD", "ריפל"),
    ],
}

# ticker -> Hebrew display name (flattened, for quick lookup).
TICKER_NAME_HE: dict[str, str] = {
    t: name for members in SECTORS.values() for (t, name) in members
}

# ticker -> sector (Hebrew).
TICKER_SECTOR_HE: dict[str, str] = {
    t: sector for sector, members in SECTORS.items() for (t, _name) in members
}

SECTOR_NAMES: list[str] = list(SECTORS.keys())


def get_universe(sector: str | None = None) -> list[str]:
    """Return the tickers to scan. ``sector=None`` scans everything."""
    if sector and sector in SECTORS:
        return [t for (t, _n) in SECTORS[sector]]
    # De-duplicate while preserving order across sectors.
    seen: set[str] = set()
    out: list[str] = []
    for members in SECTORS.values():
        for (t, _n) in members:
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


def name_of(ticker: str) -> str:
    return TICKER_NAME_HE.get(ticker, ticker)


def sector_of(ticker: str) -> str:
    return TICKER_SECTOR_HE.get(ticker, "")
