import streamlit as st
import pandas as pd
import pytz
from datetime import datetime

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from data.sp500_symbols import SP500_SYMBOLS
from logic.indicators import ema, rsi, atr
from logic.snapshot import MarketSnapshot
from logic.trend_score import calculate_trend_score
from logic.trade_plan import trade_plan
from logic.premarket_scanner import scan_early_movers

# =====================================================
# CONFIG
# =====================================================
st.set_page_config("Smart Momentum Trading Dashboard", layout="wide")

if "selected_symbol" not in st.session_state:
    st.session_state.selected_symbol = "AAPL"

# =====================================================
# ALPACA
# =====================================================
client = StockHistoricalDataClient(
    api_key=st.secrets["ALPACA_API_KEY"],
    secret_key=st.secrets["ALPACA_SECRET_KEY"]
)

# =====================================================
# HEADER
# =====================================================
st.title("📊 Smart Momentum Trading Dashboard")

ny_time = datetime.now(pytz.timezone("US/Eastern"))
st.write("Aktuelle Uhrzeit (NYSE):", ny_time)

if ny_time.hour < 9 or (ny_time.hour == 9 and ny_time.minute < 30):
    market_state = "PRE"
    st.write("Marktstatus: 🟡 Pre-Market")
elif ny_time.hour < 16:
    market_state = "OPEN"
    st.write("Marktstatus: 🟢 Open")
else:
    market_state = "CLOSED"
    st.write("Marktstatus: 🔴 Closed")

st.divider()

# =====================================================
# HELPERS
# =====================================================
def traffic_light(score):
    if score >= 70:
        return "BUY", "green"
    elif score >= 45:
        return "NEUTRAL", "gold"
    else:
        return "AVOID", "red"


def render_chart(df, symbol, title, score, score_history, plan):
    label, color = traffic_light(score)

    fig = make_subplots(
        rows=4,
        cols=1,
        shared_xaxes=True,
        row_heights=[0.55, 0.15, 0.15, 0.15],
        vertical_spacing=0.03,
        subplot_titles=[
            f"{symbol} – {title}",
            "Volumen",
            "RSI",
            "Trend-Score Verlauf"
        ]
    )

    # ---------------- PRICE
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="Price"
    ), row=1, col=1)

    for e in ["ema9", "ema20", "ema50"]:
        fig.add_trace(go.Scatter(x=df.index, y=df[e], name=e.upper()), row=1, col=1)

    if plan:
        fig.add_hline(y=plan["Entry"], line_color="green", line_dash="dot", row=1, col=1)
        fig.add_hline(y=plan["Stop"], line_color="red", line_dash="dot", row=1, col=1)
        fig.add_hline(y=plan["Target"], line_color="blue", line_dash="dot", row=1, col=1)

    # ---------------- VOLUME
    fig.add_trace(go.Bar(x=df.index, y=df["volume"], name="Volume"), row=2, col=1)

    # ---------------- RSI
    fig.add_trace(go.Scatter(x=df.index, y=df["rsi"], name="RSI"), row=3, col=1)
    fig.add_hline(y=70, line_dash="dot", row=3, col=1)
    fig.add_hline(y=30, line_dash="dot", row=3, col=1)

    # ---------------- SCORE HISTORY
    fig.add_trace(go.Scatter(y=score_history, name="Trend Score"), row=4, col=1)

    # ---------------- AMPEL BADGE
    fig.add_annotation(
        x=0.01,
        y=0.98,
        xref="paper",
        yref="paper",
        text=f"<b>{label}</b><br>Score: {int(score)}",
        showarrow=False,
        align="center",
        bgcolor=color,
        font=dict(color="black", size=14),
        bordercolor="black",
        borderwidth=1
    )

    fig.update_layout(height=900, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, width="stretch")

# =====================================================
# TABS
# =====================================================
tab_early, tab_sp500, tab_day = st.tabs([
    "🔥 Early Movers",
    "🧠 S&P 500 Scanner",
    "⚡ Daytrade"
])

# =====================================================
# EARLY MOVERS
# =====================================================
with tab_early:
    early = scan_early_movers(SP500_SYMBOLS, client, 20)
    if early.empty:
        st.info("Keine Early Movers gefunden")
    else:
        for _, r in early.iterrows():
            if st.button(f"{r['Symbol']} | Gap {r['Gap %']:.2f}%"):
                st.session_state.selected_symbol = r["Symbol"]

# =====================================================
# S&P 500 SCANNER
# =====================================================
with tab_sp500:
    rows = []

    for symbol in SP500_SYMBOLS:
        try:
            req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Day, limit=120)
            bars = client.get_stock_bars(req).df
            if bars is None or bars.empty:
                continue

            df = bars.xs(symbol) if isinstance(bars.index, pd.MultiIndex) else bars.copy()
            df["ema9"] = ema(df["close"], 9)
            df["ema20"] = ema(df["close"], 20)
            df["ema50"] = ema(df["close"], 50)
            df["rsi"] = rsi(df["close"])
            df["atr"] = atr(df)
            df.dropna(inplace=True)

            last = df.iloc[-1]
            snap = MarketSnapshot(
                symbol, last["close"], last["rsi"],
                last["ema9"], last["ema20"], last["ema50"],
                last["atr"], 1.0, market_state
            )

            score = calculate_trend_score(snap)
            rows.append({"Symbol": symbol, "Score": score})

        except Exception:
            continue

    if rows:
        table = pd.DataFrame(rows).sort_values("Score", ascending=False).head(20)
        for _, r in table.iterrows():
            if st.button(f"{r['Symbol']} | Score {int(r['Score'])}"):
                st.session_state.selected_symbol = r["Symbol"]
    else:
        st.warning("Keine Scanner-Daten verfügbar")

# =====================================================
# DAYTRADE VIEW
# =====================================================
with tab_day:
    symbol = st.session_state.selected_symbol

    req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=TimeFrame.Minute, limit=300)
    bars = client.get_stock_bars(req).df

    if bars is None or bars.empty:
        st.warning("Keine Intraday-Daten verfügbar")
    else:
        df = bars.xs(symbol) if isinstance(bars.index, pd.MultiIndex) else bars.copy()

        df["ema9"] = ema(df["close"], 9)
        df["ema20"] = ema(df["close"], 20)
        df["ema50"] = ema(df["close"], 50)
        df["rsi"] = rsi(df["close"])
        df["atr"] = atr(df)
        df.dropna(inplace=True)

        snap = MarketSnapshot(
            symbol, df.iloc[-1]["close"], df.iloc[-1]["rsi"],
            df.iloc[-1]["ema9"], df.iloc[-1]["ema20"], df.iloc[-1]["ema50"],
            df.iloc[-1]["atr"], 1.0, market_state
        )

        score = calculate_trend_score(snap)
        plan = trade_plan(snap, score)

        history = [
            calculate_trend_score(
                MarketSnapshot(
                    symbol,
                    df.iloc[i]["close"],
                    df.iloc[i]["rsi"],
                    df.iloc[i]["ema9"],
                    df.iloc[i]["ema20"],
                    df.iloc[i]["ema50"],
                    df.iloc[i]["atr"],
                    1.0,
                    market_state
                )
            )
            for i in range(30, len(df))
        ]

        render_chart(df, symbol, "Daytrade", score, history, plan)
