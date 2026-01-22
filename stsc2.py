import streamlit as st
from datetime import datetime
import pytz
import pandas as pd
import plotly.graph_objects as go

from data.sp500_symbols import SP500_SYMBOLS
from logic.data_loader import load_daily_data
from logic.indicators import ema, rsi, atr
from logic.snapshot import MarketSnapshot
from logic.trend_score import calculate_trend_score, trend_ampel
from logic.trade_plan import trade_plan
from logic.premarket_scanner import scan_early_movers

st.set_page_config(layout="wide")
st.title("📊 Smart Momentum Trading Dashboard")

ny = pytz.timezone("US/Eastern")
now = datetime.now(ny)
market_open = now.replace(hour=9, minute=30, second=0)
market_close = now.replace(hour=16, minute=0, second=0)

market_state = "OPEN" if market_open <= now <= market_close else "CLOSED"
st.caption(f"NYSE Zeit: {now.strftime('%H:%M:%S')} | Markt: {market_state}")

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Übersicht",
    "🔥 Early Movers",
    "🧠 Daytrading",
    "📈 Swing Trading"
])

# ================= Übersicht =================
with tab1:
    st.info("Objektives Momentum- & Trend-Dashboard")

# ================= Early Movers =================
with tab2:
    movers = scan_early_movers()
    if not movers:
        st.warning("Keine Early Movers gefunden")
    else:
        st.dataframe(pd.DataFrame(movers))

# ================= Daytrading =================
with tab3:
    symbol = st.selectbox("Symbol auswählen", SP500_SYMBOLS, key="day")

    df = load_daily_data(symbol)
    if df is None or len(df) < 60:
        st.warning("Nicht genügend Daten")
        st.stop()

    df["ema9"] = ema(df["close"], 9)
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["rsi"] = rsi(df["close"])
    df["atr"] = atr(df)
    df.dropna(inplace=True)

    if df.empty:
        st.warning("Indikatoren nicht berechenbar")
        st.stop()

    last = df.iloc[-1]
    snap = MarketSnapshot(
        symbol, last.close, last.rsi,
        last.ema9, last.ema20, last.ema50,
        last.atr, 1.0, market_state
    )

    st.metric("Trend Score", calculate_trend_score(snap))
    st.metric("Ampel", trend_ampel(calculate_trend_score(snap)))
    st.json(trade_plan(snap))

# ================= Swing Trading =================
with tab4:
    symbol = st.selectbox("Swing Symbol auswählen", SP500_SYMBOLS, key="swing")

    df = load_daily_data(symbol)
    if df is None or len(df) < 150:
        st.warning("Zu wenig Historie für Swing Trading")
        st.stop()

    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["ema200"] = ema(df["close"], 200)
    df["rsi"] = rsi(df["close"])
    df["atr"] = atr(df)
    df.dropna(inplace=True)

    if df.empty:
        st.warning("Swing Daten nicht nutzbar")
        st.stop()

    last = df.iloc[-1]
    snap = MarketSnapshot(
        symbol, last.close, last.rsi,
        last.ema20, last.ema50, last.ema200,
        last.atr, 1.0, market_state
    )

    st.metric("Trend Score", calculate_trend_score(snap))
    st.metric("Ampel", trend_ampel(calculate_trend_score(snap)))
    st.json(trade_plan(snap))
