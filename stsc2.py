# ================================
# app.py – Smart Momentum Dashboard (STABIL)
# ================================

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import pytz

# ===== PROJECT IMPORTS =====
from data.sp500_symbols import SP500_SYMBOLS
from logic.indicators import ema, rsi, atr
from logic.trend_score import calculate_trend_score, trend_ampel
from logic.trade_plan import trade_plan
from logic.premarket_scanner import scan_early_movers
from logic.snapshot import MarketSnapshot
from logic.data_loader import load_daily_data

# ================================
# PAGE CONFIG
# ================================

st.set_page_config(
    page_title="Smart Momentum Trading Dashboard",
    layout="wide"
)

# ================================
# MARKET STATUS
# ================================

ny_tz = pytz.timezone("US/Eastern")
ny_time = datetime.now(ny_tz)

market_open = ny_time.replace(hour=9, minute=30, second=0)
market_close = ny_time.replace(hour=16, minute=0, second=0)

if market_open <= ny_time <= market_close:
    market_state = "OPEN"
    market_icon = "🟢"
else:
    market_state = "CLOSED"
    market_icon = "🔴"

# ================================
# HEADER
# ================================

st.title("📊 Smart Momentum Trading Dashboard")
st.markdown(
    f"""
**NYSE Zeit:** `{ny_time.strftime('%Y-%m-%d %H:%M:%S')}`  
**Marktstatus:** {market_icon} **{market_state}**
"""
)

# ================================
# TABS
# ================================

tab_market, tab_early, tab_sp500, tab_swing = st.tabs(
    ["📊 Marktübersicht", "🔥 Early Movers", "🧠 S&P 500 Scanner", "📈 Swing Trading"]
)

# ======================================================
# 📊 MARKTÜBERSICHT
# ======================================================

with tab_market:
    st.subheader("📊 Marktüberblick")
    st.info(
        "Objektives Momentum- & Trend-Dashboard "
        "(EMA-Struktur, RSI, Volatilität, Trend-Score)"
    )

# ======================================================
# 🔥 EARLY MOVERS
# ======================================================

with tab_early:
    st.subheader("🔥 Premarket Early Movers")

    movers = scan_early_movers()

    if not movers or len(movers) == 0:
        st.warning("Keine auffälligen Premarket-Gaps gefunden")
    else:
        st.dataframe(pd.DataFrame(movers), width="stretch")

# ======================================================
# 🧠 S&P 500 SCANNER (DAYTRADING)
# ======================================================

with tab_sp500:
    st.subheader("🧠 S&P 500 Momentum Scanner")

    symbol = st.selectbox("📌 Symbol auswählen", SP500_SYMBOLS)

    df = load_daily_data(symbol)

    if df is None or df.empty or len(df) < 60:
        st.warning("Nicht genügend Daten verfügbar")
        st.stop()

    df["ema9"] = ema(df["close"], 9)
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["rsi"] = rsi(df["close"])
    df["atr"] = atr(df)

    df.dropna(inplace=True)

    if df.empty or len(df) < 5:
        st.warning("Indikator-Daten unvollständig")
        st.stop()

    last = df.iloc[-1]

    snap = MarketSnapshot(
        symbol=symbol,
        price=float(last["close"]),
        rsi=float(last["rsi"]),
        ema_fast=float(last["ema9"]),
        ema_mid=float(last["ema20"]),
        ema_slow=float(last["ema50"]),
        atr=float(last["atr"]),
        volume_factor=1.0,
        market_state=market_state
    )

    score = calculate_trend_score(snap)
    ampel = trend_ampel(score)

    c1, c2, c3 = st.columns(3)
    c1.metric("📈 Trend-Score", score)
    c2.metric("🟢 Ampel", ampel)
    c3.metric("📊 RSI", f"{last['rsi']:.1f}")

    st.subheader("📦 Trade-Plan")
    st.json(trade_plan(snap))

    fig = go.Figure()
    fig.add_candlestick(
        x=df.index,
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="Price"
    )
    fig.add_trace(go.Scatter(x=df.index, y=df["ema20"], name="EMA 20"))
    fig.add_trace(go.Scatter(x=df.index, y=df["ema50"], name="EMA 50"))
    fig.update_layout(height=520, title=f"{symbol} – Daily Chart")

    st.plotly_chart(fig, width="stretch")

# ======================================================
# 📈 SWING TRADING (JETZT STABIL)
# ======================================================

with tab_swing:
    st.subheader("📈 Swing Trading (Multi-Day)")

    swing_symbol = st.selectbox(
        "📌 Swing-Symbol auswählen",
        SP500_SYMBOLS,
        key="swing_symbol"
    )

    df = load_daily_data(swing_symbol)

    if df is None or df.empty or len(df) < 120:
        st.warning("Zu wenig Historie für Swing-Trading")
        st.stop()

    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["ema200"] = ema(df["close"], 200)
    df["rsi"] = rsi(df["close"])
    df["atr"] = atr(df)

    df.dropna(inplace=True)

    if df.empty or len(df) < 10:
        st.warning("Swing-Indikatoren nicht vollständig")
        st.stop()

    last = df.iloc[-1]

    snap = MarketSnapshot(
        symbol=swing_symbol,
        price=float(last["close"]),
        rsi=float(last["rsi"]),
        ema_fast=float(last["ema20"]),
        ema_mid=float(last["ema50"]),
        ema_slow=float(last["ema200"]),
        atr=float(last["atr"]),
        volume_factor=1.0,
        market_state=market_state
    )

    score = calculate_trend_score(snap)
    ampel = trend_ampel(score)

    c1, c2, c3 = st.columns(3)
    c1.metric("📈 Trend-Score", score)
    c2.metric("🟢 Ampel", ampel)
    c3.metric("📊 RSI", f"{last['rsi']:.1f}")

    st.subheader("📦 Swing Trade-Plan")
    st.json(trade_plan(snap))

    fig = go.Figure()
    fig.add_candlestick(
        x=df.index,
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="Price"
    )
    fig.add_trace(go.Scatter(x=df.index, y=df["ema50"], name="EMA 50"))
    fig.add_trace(go.Scatter(x=df.index, y=df["ema200"], name="EMA 200"))
    fig.update_layout(height=540, title=f"{swing_symbol} – Swing Chart")

    st.plotly_chart(fig, width="stretch")
