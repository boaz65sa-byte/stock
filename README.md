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
- **שני ממשקים:** שורת פקודה (CLI) ודשבורד ווב יפה (Streamlit).

---

## התקנה

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows (PowerShell)
pip install -r requirements.txt
```

(אופציונלי) להפעלת סוכן ה‑AI: העתק את `.env.example` ל‑`.env` והכנס `OPENAI_API_KEY`.
בלי זה — המערכת עובדת במלואה עם הסוכנים האלגוריתמיים.

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

## שימוש — דשבורד ווב

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
  agents/           # הסוכנים
    base.py
    technical.py  momentum.py  value.py  risk.py  llm_analyst.py
app.py              # דשבורד Streamlit
requirements.txt
.env.example
```

---

## איך מרחיבים

- **סוכן חדש:** צור מחלקה שיורשת מ‑`BaseAgent`, ממש `analyze()` שמחזיר `Signal`,
  והוסף אותה ב‑`agents/__init__.py` בתוך `default_agents()`.
- **מסחר אמיתי:** החלף את `Portfolio` בממשק לברוקר (למשל Alpaca/Interactive Brokers).
  הארכיטקטורה כבר מפרידה בין קבלת ההחלטה (הוועדה) לביצוע (התיק).
