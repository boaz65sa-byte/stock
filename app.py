"""Streamlit dashboard for the investment agents system.

Run with:  streamlit run app.py

The default view ("מצב פשוט") is built for people who know nothing about
investing: pick an asset, see a clear visual verdict and a plain-Hebrew
explanation, and "buy"/"sell" in a virtual portfolio with one click.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from investment_agents import indicators as ta
from investment_agents.config import Action, settings
from investment_agents.data import get_asset
from investment_agents.explain import explain_recommendation
from investment_agents.orchestrator import Committee
from investment_agents.portfolio import Portfolio, backtest_sma_cross

st.set_page_config(page_title="מערכת סוכני השקעות", page_icon="📈", layout="wide")

PORTFOLIO_FILE = "portfolio.json"

# Popular assets with friendly Hebrew names so beginners don't need to know tickers.
POPULAR = {
    "🍎 אפל": "AAPL",
    "🪟 מיקרוסופט": "MSFT",
    "🎮 אנבידיה": "NVDA",
    "🚗 טסלה": "TSLA",
    "📦 אמזון": "AMZN",
    "🔎 גוגל": "GOOGL",
    "₿ ביטקוין": "BTC-USD",
    "Ξ אתריום": "ETH-USD",
    "📊 מדד S&P 500": "SPY",
    "💊 טבע (ישראל)": "TEVA.TA",
}

ACTION_COLOR = {
    Action.STRONG_BUY: "#0a8f3c",
    Action.BUY: "#2ecc71",
    Action.HOLD: "#f1c40f",
    Action.SELL: "#e67e22",
    Action.STRONG_SELL: "#c0392b",
}


# ---------------------------------------------------------------- helpers
@st.cache_resource
def _committee() -> Committee:
    return Committee()


@st.cache_data(show_spinner=False, ttl=900)
def _analyze(ticker: str, period: str):
    settings.history_period = period
    asset = get_asset(ticker, period=period)
    rec = _committee().analyze_asset(asset)
    return asset, rec


def _load_portfolio() -> Portfolio:
    if "portfolio" not in st.session_state:
        st.session_state["portfolio"] = Portfolio.load(PORTFOLIO_FILE)
    return st.session_state["portfolio"]


def _gauge(score_pct: int, color: str) -> go.Figure:
    """A speedometer that 'draws the situation' from -100 (sell) to +100 (buy)."""
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score_pct,
            number={"suffix": "%", "font": {"size": 44}},
            gauge={
                "axis": {"range": [-100, 100], "tickwidth": 1},
                "bar": {"color": color, "thickness": 0.3},
                "steps": [
                    {"range": [-100, -15], "color": "#f8d7da"},
                    {"range": [-15, 15], "color": "#fff3cd"},
                    {"range": [15, 100], "color": "#d4edda"},
                ],
                "threshold": {
                    "line": {"color": "black", "width": 4},
                    "thickness": 0.75,
                    "value": score_pct,
                },
            },
        )
    )
    fig.update_layout(height=280, margin=dict(l=20, r=20, t=10, b=10))
    return fig


# ---------------------------------------------------------------- header
st.title("📈 מערכת סוכני השקעות")
st.caption(
    "בודקת את השוק ומסבירה בפשטות אם כדאי להשקיע. "
    "למחקר ולמידה בלבד — אינו ייעוץ השקעות."
)

with st.sidebar:
    st.header("⚙️ הגדרות")
    period = st.selectbox("כמה היסטוריה לבדוק", ["6mo", "1y", "2y", "5y"], index=1)
    st.write("**סוכן AI:**", "פעיל ✅" if settings.llm_enabled else "כבוי ⛔")
    if not settings.llm_enabled:
        st.caption("אפשר להפעיל ע\"י הוספת OPENAI_API_KEY בקובץ .env")
    st.divider()
    pf = _load_portfolio()
    st.metric("💵 מזומן בתיק הדמה", f"${pf.cash:,.0f}")


tab_simple, tab_rank, tab_advanced, tab_backtest = st.tabs(
    ["😀 מצב פשוט", "🏆 השוואת נכסים", "🔬 ניתוח מתקדם", "⏳ בקטסט"]
)


# ================================================================ SIMPLE MODE
with tab_simple:
    st.subheader("1️⃣ בחר מה לבדוק")
    st.write("לחץ על נכס פופולרי, או הקלד סימבול משלך:")

    cols = st.columns(5)
    for i, (label, tk) in enumerate(POPULAR.items()):
        if cols[i % 5].button(label, use_container_width=True, key=f"pop_{tk}"):
            st.session_state["simple_ticker"] = tk

    typed = st.text_input(
        "או הקלד סימבול (למשל AAPL, BTC-USD, TEVA.TA)",
        value=st.session_state.get("simple_ticker", "AAPL"),
    )
    ticker = (typed or "AAPL").strip().upper()
    st.session_state["simple_ticker"] = ticker

    if st.button("🔍 בדוק עכשיו", type="primary", use_container_width=True):
        st.session_state["run_simple"] = True

    if st.session_state.get("run_simple"):
        with st.spinner(f"הסוכנים בודקים את {ticker}..."):
            try:
                asset, rec = _analyze(ticker, period)
            except Exception:
                asset, rec = None, None

        if asset is None or not asset.is_valid or rec is None:
            st.error("לא הצלחתי למצוא מספיק נתונים לנכס הזה. בדוק את הסימבול ונסה שוב.")
        else:
            info = explain_recommendation(rec)
            st.divider()
            st.subheader("2️⃣ תמונת המצב")

            left, right = st.columns([1, 1])
            with left:
                st.plotly_chart(_gauge(info["score_pct"], info["color"]), use_container_width=True)
            with right:
                st.markdown(
                    f"<div style='text-align:center'>"
                    f"<div style='font-size:64px'>{info['emoji']}</div>"
                    f"<div style='font-size:34px;font-weight:800;color:{info['color']}'>{info['verdict']}</div>"
                    f"<div style='font-size:18px;color:#555'>{info['subtitle']}</div>"
                    f"<div style='font-size:15px;color:#888;margin-top:8px'>{info['confidence_word']}"
                    f" · מחיר נוכחי: {rec.price:,.2f}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )

            st.info("📝 " + info["summary"])

            st.subheader("3️⃣ למה? (בשפה פשוטה)")
            for line in info["signal_lines"]:
                sc = int(line["score"] * 100)
                st.markdown(
                    f"{line['emoji']} **{line['role']}** — {line['mood']} "
                    f"<span style='color:#999'>({sc:+d}%)</span>",
                    unsafe_allow_html=True,
                )

            # price mini-chart
            close = asset.close
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=close.index, y=close, name="מחיר", line=dict(color=info["color"])))
            fig.update_layout(height=260, margin=dict(t=20, b=10), title="מחיר בתקופה האחרונה")
            st.plotly_chart(fig, use_container_width=True)

            # ---- one-click paper trading ----
            st.subheader("4️⃣ רוצה לתרגל? (כסף וירטואלי בלבד)")
            pf = _load_portfolio()
            c1, c2, c3 = st.columns([2, 1, 1])
            amount = c1.slider("סכום לקנייה ($)", 100, 5000, 1000, step=100)
            owns = ticker in pf.positions

            if c2.button("🟢 קנה", use_container_width=True):
                pf.buy(ticker, rec.price, float(amount))
                pf.save(PORTFOLIO_FILE)
                st.success(f"נקנו {ticker} בסך ${amount:,.0f} (וירטואלי).")

            if c3.button("🔴 מכור הכל", use_container_width=True, disabled=not owns):
                pf.sell(ticker, rec.price, 1.0)
                pf.save(PORTFOLIO_FILE)
                st.success(f"נמכרו כל המניות של {ticker} (וירטואלי).")

            # ---- portfolio snapshot ----
            pf = _load_portfolio()
            if pf.positions:
                st.subheader("💼 התיק הווירטואלי שלי")
                prices = {}
                rows = []
                for t, pos in pf.positions.items():
                    try:
                        p = get_asset(t, period="5d", with_info=False).last_price or pos.avg_price
                    except Exception:
                        p = pos.avg_price
                    prices[t] = p
                    value = pos.shares * p
                    pnl = (p / pos.avg_price - 1) * 100 if pos.avg_price else 0
                    rows.append(
                        {"נכס": t, "מחיר קנייה": round(pos.avg_price, 2),
                         "מחיר נוכחי": round(p, 2), "שווי ($)": round(value, 2),
                         "רווח/הפסד %": round(pnl, 1)}
                    )
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                equity = pf.market_value(prices)
                st.metric("💰 שווי כולל (מזומן + נכסים)", f"${equity:,.0f}")


# ================================================================ RANK
with tab_rank:
    st.write("השווה כמה נכסים ומצא איפה הכי כדאי:")
    default_list = ", ".join(list(POPULAR.values())[:6])
    tickers_raw = st.text_area("רשימת נכסים (מופרדים בפסיק)", value=default_list)
    tks = [t.strip().upper() for t in tickers_raw.split(",") if t.strip()]

    if st.button("דרג נכסים", type="primary", key="rank_btn"):
        with st.spinner("משווה..."):
            recs = _committee().rank(tks)
        best = recs[0]
        st.success(f"הכי כדאי כרגע: **{best.ticker}** — {explain_recommendation(best)['verdict']}")
        df = pd.DataFrame(
            [{"נכס": r.ticker,
              "המלצה": explain_recommendation(r)["verdict"],
              "ציון %": r.score_pct,
              "מחיר": round(r.price, 2) if r.price else None} for r in recs]
        )
        st.dataframe(df, use_container_width=True, hide_index=True)
        fig = go.Figure(go.Bar(
            x=[r.ticker for r in recs],
            y=[r.score_pct for r in recs],
            marker_color=[ACTION_COLOR.get(r.action, "#888") for r in recs],
            text=[f"{r.score_pct:+d}%" for r in recs],
        ))
        fig.update_layout(title="ציון לכל נכס", yaxis_title="ציון %", height=380)
        st.plotly_chart(fig, use_container_width=True)


# ================================================================ ADVANCED
with tab_advanced:
    adv_ticker = st.text_input("נכס לניתוח מעמיק", value="AAPL", key="adv").strip().upper()
    if st.button("נתח לעומק", key="adv_btn"):
        with st.spinner(f"מנתח {adv_ticker}..."):
            asset, rec = _analyze(adv_ticker, period)
        if not asset or not asset.is_valid:
            st.error("אין מספיק נתונים.")
        else:
            color = ACTION_COLOR.get(rec.action, "#888")
            st.markdown(f"### {adv_ticker} — <span style='color:{color}'>{rec.action.value}</span> ({rec.score_pct:+d}%)", unsafe_allow_html=True)
            close = asset.close
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=close.index, y=close, name="מחיר", line=dict(color="#2c3e50")))
            if len(close) >= 50:
                fig.add_trace(go.Scatter(x=close.index, y=ta.sma(close, 50), name="SMA50", line=dict(color="#3498db")))
            if len(close) >= 200:
                fig.add_trace(go.Scatter(x=close.index, y=ta.sma(close, 200), name="SMA200", line=dict(color="#e74c3c")))
            fig.update_layout(title=f"{adv_ticker} — מחיר וממוצעים נעים", height=420)
            st.plotly_chart(fig, use_container_width=True)
            st.subheader("דעות הסוכנים (פירוט טכני)")
            for s in rec.signals:
                with st.expander(f"{s.agent} — {int(s.score*100):+d}% (ביטחון {int(s.confidence*100)}%)"):
                    for r in s.reasons:
                        st.write(f"• {r}")


# ================================================================ BACKTEST
with tab_backtest:
    st.write("בדוק איך אסטרטגיה פשוטה הייתה מתפקדת בעבר:")
    bt_ticker = st.text_input("נכס", value="AAPL", key="bt").strip().upper()
    c1, c2 = st.columns(2)
    fast = c1.number_input("ממוצע מהיר (ימים)", 5, 100, 20)
    slow = c2.number_input("ממוצע איטי (ימים)", 10, 250, 50)
    if st.button("הרץ בקטסט", key="bt_btn"):
        try:
            with st.spinner("מריץ סימולציה היסטורית..."):
                res = backtest_sma_cross(bt_ticker, int(fast), int(slow))
            c1, c2, c3 = st.columns(3)
            c1.metric("תשואת האסטרטגיה", f"{res.total_return*100:+.1f}%")
            c2.metric("פשוט להחזיק (קנה-והחזק)", f"{res.buy_hold_return*100:+.1f}%")
            c3.metric("מספר עסקאות", res.n_trades)
            st.line_chart(res.equity_curve)
        except ValueError as e:
            st.error(str(e))
