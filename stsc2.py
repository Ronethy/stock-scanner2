import streamlit as st
import os
import pandas as pd
import pandas_ta as ta
import plotly.graph_objects as go

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# ===============================
# STREAMLIT CONFIG
# ===============================
st.set_page_config(
    page_title="Trading Dashboard",
    layout="wide",
)

st.title("📊 Smart Momentum Trading Dashboard")

# ===============================
# SETTINGS
# ===============================
SYMBOLS = [
    "AAPL", "NVDA", "AMD", "TSLA", "META",
    "MSFT", "AMZN", "COIN", "PLTR", "NFLX"
]

MIN_CHANGE_5M = 0.5   # %
MIN_VOLUME_SPIKE = 1.2

# ===============================
# ALPACA CLIENT
# ===============================
client = StockHistoricalDataClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY")
)
st.write("Keys geladen:", "ALPACA_API_KEY" in st.secrets)
st.write("Aktuelle Uhrzeit:", pd.Timestamp.now(tz="US/Eastern"))
st.write("Letzte Kerze:", df.iloc[-1][["open", "close", "volume"]])
df = load_data("AAPL")
st.write(df.tail(5))

# ===============================
# DATA LOADER
# ===============================
@st.cache_data(ttl=60)
def load_data(symbol):
    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Minute,
        limit=120
    )
    bars = client.get_stock_bars(req).df.reset_index()
    return bars[bars["symbol"] == symbol]

# ===============================
# ANALYSIS
# ===============================
def analyze(df):
    df["ema9"] = ta.ema(df["close"], length=9)
    df["ema20"] = ta.ema(df["close"], length=20)
    df["vwap"] = ta.vwap(
        df["high"], df["low"], df["close"], df["volume"]
    )
    df["rsi"] = ta.rsi(df["close"], length=14)

    last = df.iloc[-1]

    score = 0
    score += last.close > last.ema9
    score += last.ema9 > last.ema20
    score += last.close > last.vwap
    score += last.rsi > 55
    score = score / 4

    if score >= 0.75:
        action = "📈 CALL / LONG"
    elif score <= 0.25:
        action = "📉 PUT / SHORT"
    else:
        action = "⏸ WAIT"

    return score, action

# ===============================
# MARKET SCAN
# ===============================
st.sidebar.header("🔥 Momentum Scanner")

candidates = []
market_data = {}

for symbol in SYMBOLS:
    try:
        df = load_data(symbol)
        if len(df) < 30:
            continue

        last = df.iloc[-1]
        prev = df.iloc[-6]

        change_5m = (last.close - prev.close) / prev.close * 100
        avg_vol = df.volume.rolling(20).mean().iloc[-1]
        vol_spike = last.volume > avg_vol * MIN_VOLUME_SPIKE

        if change_5m > MIN_CHANGE_5M and vol_spike:
            candidates.append(symbol)

        market_data[symbol] = df

    except Exception:
        pass

if not candidates:
    st.sidebar.warning("Kein Momentum – zeige Watchlist")
    candidates = SYMBOLS

selected = st.sidebar.radio("Aktie auswählen", candidates)

# ===============================
# DETAIL VIEW
# ===============================
df = market_data[selected]
score, action = analyze(df)

col1, col2 = st.columns([4, 1])

with col1:
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df.open,
        high=df.high,
        low=df.low,
        close=df.close,
        name="Price"
    ))
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["ema9"],
        line=dict(width=1),
        name="EMA 9"
    ))
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["ema20"],
        line=dict(width=1),
        name="EMA 20"
    ))
    fig.add_trace(go.Scatter(
        x=df.index,
        y=df["vwap"],
        line=dict(width=1),
        name="VWAP"
    ))

    fig.update_layout(height=550)
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader(f"🧠 {selected}")
    st.metric("Score", round(score, 2))

    if "CALL" in action:
        st.success(action)
    elif "PUT" in action:
        st.error(action)
    else:
        st.warning(action)

    st.divider()
    st.write("**Indikatoren**")
    st.write(f"RSI: {round(df.rsi.iloc[-1], 1)}")
