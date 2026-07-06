# 📈 מערכת סוכני השקעות (Investment Agents)

מערכת רב‑סוכנים (multi‑agent) בפייתון שבודקת את שוק ההשקעות ומפיקה המלצות
"כדאי / לא כדאי" לכל נכס. ועדה של סוכנים מנתחת כל נכס מזוויות שונות
(טכני, מומנטום, ערך פונדמנטלי, וניהול סיכונים), ואופציונלית גם סוכן AI,
וכל הסוכנים "מצביעים" יחד לכדי ציון והמלצה אחת.

> ⚠️ **הבהרה חשובה:** הכלי נועד למחקר וללמידה בלבד ואינו מהווה ייעוץ השקעות.
> כל החלטת השקעה היא באחריותך המלאה.

---

## מה יש במערכת

- **נתונים חינמיים** דרך `yfinance` — אין צורך במפתח API כדי להתחיל.
- **שווקים נתמכים:** מניות ארה"ב (`AAPL`), מניות ישראל (`TEVA.TA`), קריפטו (`BTC-USD`), קרנות סל / ETF (`SPY`).
- **ועדת סוכנים:**
  - `Technical Analyst` — RSI, ממוצעים נעים (SMA50/200), MACD.
  - `Momentum Trader` — תשואות מגמה ל‑1/3/6 חודשים.
  - `Value Investor` — מכפיל רווח (P/E), PEG, רווחיות, צמיחה.
  - `Risk Manager` — תנודתיות, ירידה מקסימלית (drawdown), יחס שארפ.
  - `AI Analyst` (אופציונלי) — נדלק אוטומטית אם מוגדר `OPENAI_API_KEY`.
- **מסחר וירטואלי (Paper trading)** — תיק דמה שמבצע קניות/מכירות לפי ההמלצות.
- **בקטסטינג** — סימולציה היסטורית של אסטרטגיית חציית ממוצעים נעים.
- **שלושה ממשקים:** אתר ווב (FastAPI + HTML, מתאים לפריסה ב‑Vercel), שורת פקודה (CLI), ודשבורד מקומי (Streamlit).

---

## התקנה (מקומי)

```bash
python -m venv .venv
.venv\Scripts\activate            # Windows (PowerShell)

# בשביל האתר (FastAPI) + הליבה בלבד:
pip install -r requirements.txt

# בשביל הדשבורד המקומי (Streamlit) וה‑CLI הצבעוני:
pip install -r requirements-dashboard.txt
```

(אופציונלי) להפעלת סוכן ה‑AI: העתק את `.env.example` ל‑`.env` והכנס `OPENAI_API_KEY`.
בלי זה — המערכת עובדת במלואה עם הסוכנים האלגוריתמיים.

---

## אתר ווב (FastAPI) — הרצה מקומית ופריסה ל‑Vercel

הרצה מקומית של האתר:

```bash
uvicorn api.index:app --reload
# ואז פותחים בדפדפן:  http://127.0.0.1:8000  (העמוד ב-index.html)
```

**פריסה ל‑Vercel:**

1. היכנס ל‑[vercel.com](https://vercel.com) והתחבר עם חשבון GitHub.
2. לחץ **Add New → Project** ובחר את המאגר `stock`.
3. השאר את כל ההגדרות כברירת מחדל (ה‑`vercel.json` כבר מגדיר הכול) ולחץ **Deploy**.
4. תוך דקה תקבל כתובת ציבורית לאתר. 🎉

> חשוב: הדשבורד של **Streamlit לא רץ על Vercel** (הוא דורש שרת רציף). לכן
> גרסת הווב ל‑Vercel בנויה מ‑API של FastAPI (`api/index.py`) + עמוד סטטי
> (`index.html`). את Streamlit מריצים מקומית או ב‑Streamlit Community Cloud.

נקודות קצה של ה‑API:
- `GET /api/analyze?ticker=AAPL&period=1y`
- `GET /api/rank?tickers=AAPL,MSFT,BTC-USD`
- `GET /api/health`

---

## שימוש — שורת פקודה (CLI)

```bash
# 👶 מצב פשוט למתחילים — תשובה ברורה בעברית: כדאי / לא כדאי
python -m investment_agents.cli simple AAPL BTC-USD

# ניתוח מלא של נכס אחד או כמה
python -m investment_agents.cli analyze AAPL MSFT

# דירוג נכסים מהטוב לפחות טוב
python -m investment_agents.cli rank AAPL MSFT NVDA SPY BTC-USD --top 5

# בקטסט של אסטרטגיית חציית ממוצעים נעים
python -m investment_agents.cli backtest AAPL --fast 20 --slow 50

# צעד מסחר וירטואלי (שומר ל-portfolio.json)
python -m investment_agents.cli paper AAPL MSFT --budget 1000
```

## שימוש — דשבורד מקומי (Streamlit)

```bash
streamlit run app.py
```

הדשבורד נפתח ב**"מצב פשוט"** שמיועד גם למי שלא מבין כלום בהשקעות:
בוחרים נכס (יש כפתורים לנכסים פופולריים עם שמות בעברית), רואים **מד ויזואלי**
(מד מהירות מ‑100%- עד 100%+) עם תמונת מצב ברורה 🟢🟡🔴, הסבר בעברית פשוטה
*למה*, ואפשר **לקנות/למכור בלחיצת כפתור** בתיק דמה (כסף וירטואלי בלבד).
בנוסף יש לשוניות **השוואת נכסים**, **ניתוח מתקדם** ו**בקטסט**.

---

## איך מחושב הציון

כל סוכן מחזיר `Signal` עם:
- `score` בטווח `[-1, 1]` (חיובי = שורי/כדאי, שלילי = דובי/לא כדאי),
- `confidence` בטווח `[0, 1]` (כמה הסוכן בטוח),
- ורשימת נימוקים קצרים.

הוועדה (`Committee`) מחשבת **ממוצע משוקלל** שבו כל סוכן תורם לפי
`agent.weight × signal.confidence`. הציון הסופי מתורגם להמלצה:

| ציון | המלצה |
|------|-------|
| ≥ +50% | STRONG_BUY |
| +15%..+50% | BUY |
| -15%..+15% | HOLD |
| -50%..-15% | SELL |
| ≤ -50% | STRONG_SELL |

---

## מבנה הפרויקט

```
investment_agents/
  config.py         # טיפוסים משותפים (Signal, Recommendation) והגדרות
  data.py           # שכבת נתונים (yfinance) + מטמון
  indicators.py     # אינדיקטורים טכניים (RSI, MACD, SMA, שארפ, drawdown)
  orchestrator.py   # הוועדה שמאחדת את דעות הסוכנים
  portfolio.py      # תיק מסחר וירטואלי + בקטסטר
  cli.py            # ממשק שורת פקודה
  explain.py        # הסברים בעברית פשוטה (verdict + נימוקים)
  agents/           # הסוכנים
    base.py
    technical.py  momentum.py  value.py  risk.py  llm_analyst.py
api/
  index.py          # API של FastAPI (serverless, ל-Vercel)
index.html          # חזית הווב (עברית RTL, מד ויזואלי)
vercel.json         # הגדרות פריסה ל-Vercel
app.py              # דשבורד Streamlit (מקומי)
requirements.txt              # ליבה + API (מותקן ב-Vercel)
requirements-dashboard.txt    # תוספות ל-Streamlit/CLI מקומי
.env.example
```

---

## איך מרחיבים

- **סוכן חדש:** צור מחלקה שיורשת מ‑`BaseAgent`, ממש `analyze()` שמחזיר `Signal`,
  והוסף אותה ב‑`agents/__init__.py` בתוך `default_agents()`.
- **מסחר אמיתי:** החלף את `Portfolio` בממשק לברוקר (למשל Alpaca/Interactive Brokers).
  הארכיטקטורה כבר מפרידה בין קבלת ההחלטה (הוועדה) לביצוע (התיק).
