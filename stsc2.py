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
market_data = {}
candidates = []

for symbol in SYMBOLS:
    try:
        df = load_data(symbol)

        if df.empty:
            continue

        market_data[symbol] = df  # IMMER speichern

        if len(df) < 30:
            continue

        last = df.iloc[-1]
        prev = df.iloc[-6]

        change_5m = (last.close - prev.close) / prev.close * 100
        avg_vol = df.volume.rolling(20).mean().iloc[-1]
        vol_spike = last.volume > avg_vol * MIN_VOLUME_SPIKE

        if change_5m > MIN_CHANGE_5M and vol_spike:
            candidates.append(symbol)

    except Exception:
        pass

# ===============================
# DETAIL VIEW
# ===============================

st.subheader("📈 Detailansicht")

selected = st.selectbox(
    "Aktie auswählen",
    candidates if candidates else SYMBOLS
)

if selected not in market_data:
    st.error(f"Keine Daten für {selected}")
    st.stop()

df = market_data[selected]

st.write("Letzte Kerze:", df.iloc[-1][["open", "close", "volume"]])


    st.divider()
    st.write("**Indikatoren**")
    st.write(f"RSI: {round(df.rsi.iloc[-1], 1)}")

st.write("Keys geladen:", "ALPACA_API_KEY" in st.secrets)
st.write("Aktuelle Uhrzeit:", pd.Timestamp.now(tz="US/Eastern"))
st.write("Letzte Kerze:", df.iloc[-1][["open", "close", "volume"]])
df = load_data("AAPL")
st.write(df.tail(5))
