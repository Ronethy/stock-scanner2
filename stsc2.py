# ===============================
# IMPORTS
# ===============================
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
import pytz

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


# ===============================
# CONFIG
# ===============================
st.set_page_config("Smart Momentum Trading Dashboard", layout="wide")

SYMBOLS = ["AAPL","NVDA","AMD","TSLA","META","MSFT","AMZN","COIN","PLTR","NFLX"]
TIMEFRAME = TimeFrame.Minute
LOOKBACK_MINUTES = 60

# ===============================
# AUTH
# ===============================
API_KEY = st.secrets.get("ALPACA_API_KEY")
SECRET_KEY = st.secrets.get("ALPACA_SECRET_KEY")

st.title("📊 Smart Momentum Trading Dashboard")
st.write("Keys geladen:", bool(API_KEY and SECRET_KEY))

if not API_KEY or not SECRET_KEY:
    st.stop()

client = StockHistoricalDataClient(API_KEY, SECRET_KEY)

# ===============================
# TIME
# ===============================
ny = pytz.timezone("America/New_York")
now = datetime.now(ny)
market_open = time(9, 30)
market_close = time(16, 0)

is_premarket = now.time() < market_open
is_market_open = market_open <= now.time() <= market_close

st.caption(f"Aktuelle Uhrzeit (NYSE): {now}")
st.caption(f"Marktstatus: {'🟡 Pre-Market' if is_premarket else '🟢 Market Open' if is_market_open else '🔴 Closed'}")

# ===============================
# DATA LOADER
# ===============================
@st.cache_data(ttl=60)
def load_data(symbols):
    start = now - timedelta(minutes=LOOKBACK_MINUTES)
    req = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TIMEFRAME,
        start=start,
        end=now,
        feed="iex"
    )
    bars = client.get_stock_bars(req).df
    data = {}

    if bars.empty:
        return data

    for s in symbols:
        try:
            df = bars.loc[s].copy()
            df["return"] = df["close"].pct_change() * 100
            data[s] = df.dropna()
        except:
            continue
    return data


market_data = load_data(SYMBOLS)

# ===============================
# PRE-MARKET SCANNER
# ===============================
st.subheader("🔥 Scanner")

candidates = []

if is_premarket:
    st.info("Pre-Market Scanner aktiv")
    for s, df in market_data.items():
        if not df.empty and abs(df.iloc[-1]["return"]) > 0.5:
            candidates.append(s)
else:
    for s, df in market_data.items():
        if not df.empty and abs(df.iloc[-1]["return"]) > 0.3:
            candidates.append(s)

st.write("Watchlist:", candidates if candidates else SYMBOLS)

# ===============================
# DETAIL VIEW
# ===============================
st.subheader("📈 Detailansicht")

selected = st.selectbox("Aktie auswählen", candidates if candidates else SYMBOLS)

if selected not in market_data or market_data[selected].empty:
    st.warning("Keine Intraday-Daten verfügbar (Pre-Market normal)")
    st.stop()

df = market_data[selected]
last = df.iloc[-1]

# ===============================
# METRICS
# ===============================
c1, c2, c3 = st.columns(3)
c1.metric("Preis", f"${last['close']:.2f}")
c2.metric("Return", f"{last['return']:.2f}%")
c3.metric("Volumen", int(last["volume"]))

# ===============================
# CANDLESTICK CHART
# ===============================
st.subheader("📊 Candlestick Chart")

st.line_chart(df[["open","high","low","close"]])

# ===============================
# SIGNAL
# ===============================
st.subheader("🧠 Einschätzung")

if last["return"] > 0.3:
    st.success("📈 LONG / CALL Setup")
elif last["return"] < -0.3:
    st.error("📉 SHORT / PUT Setup")
else:
    st.info("⚪ Neutral")
