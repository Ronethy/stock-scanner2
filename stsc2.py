# ===============================
# IMPORTS
# ===============================
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import pytz

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


# ===============================
# CONFIG
# ===============================
st.set_page_config(
    page_title="Smart Momentum Trading Dashboard",
    layout="wide"
)

SYMBOLS = [
    "AAPL", "NVDA", "AMD", "TSLA", "META",
    "MSFT", "AMZN", "COIN", "PLTR", "NFLX"
]

TIMEFRAME = TimeFrame.Minute
LOOKBACK_MINUTES = 60
VOLUME_SPIKE_FACTOR = 1.5
PRICE_CHANGE_THRESHOLD = 0.3  # %


# ===============================
# AUTH / CLIENT
# ===============================
API_KEY = st.secrets.get("ALPACA_API_KEY")
SECRET_KEY = st.secrets.get("ALPACA_SECRET_KEY")

st.title("📊 Smart Momentum Trading Dashboard")
st.write("Keys geladen:", bool(API_KEY and SECRET_KEY))

if not API_KEY or not SECRET_KEY:
    st.error("❌ Alpaca API Keys fehlen")
    st.stop()

client = StockHistoricalDataClient(API_KEY, SECRET_KEY)


# ===============================
# TIME INFO
# ===============================
ny_tz = pytz.timezone("America/New_York")
now_ny = datetime.now(ny_tz)
st.caption(f"Aktuelle Uhrzeit (NYSE): {now_ny}")


# ===============================
# DATA FETCH
# ===============================
@st.cache_data(ttl=30)
def load_market_data(symbols):
    data = {}
    start = now_ny - timedelta(minutes=LOOKBACK_MINUTES)

    request = StockBarsRequest(
    symbol_or_symbols=symbols,
    timeframe=TIMEFRAME,
    start=start,
    end=now_ny,
    feed="iex"   # <<< DAS IST ENTSCHEIDEND

    )

    bars = client.get_stock_bars(request).df

    if bars.empty:
        return data

    for symbol in symbols:
        try:
            df = bars.loc[symbol].copy()
            df["return"] = df["close"].pct_change() * 100
            df["vol_avg"] = df["volume"].rolling(20).mean()
            data[symbol] = df.dropna()
        except Exception:
            continue

    return data


market_data = load_market_data(SYMBOLS)


# ===============================
# MOMENTUM SCANNER
# ===============================
st.subheader("🔥 Momentum Scanner")

candidates = []

for symbol, df in market_data.items():
    if df.empty:
        continue

    last = df.iloc[-1]

    price_move = last["return"]
    volume_spike = last["volume"] > last["vol_avg"] * VOLUME_SPIKE_FACTOR

    if abs(price_move) >= PRICE_CHANGE_THRESHOLD and volume_spike:
        candidates.append(symbol)

if candidates:
    st.success(f"Momentum erkannt: {', '.join(candidates)}")
else:
    st.info("Kein Momentum – zeige Watchlist")


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

if df.empty:
    st.warning("Keine Kerzendaten verfügbar")
    st.stop()

last = df.iloc[-1]

col1, col2, col3 = st.columns(3)

col1.metric("Letzter Preis", f"${last['close']:.2f}")
col2.metric("Return (1m)", f"{last['return']:.2f}%")
col3.metric("Volumen", f"{int(last['volume']):,}")

st.write("Letzte Kerze")
st.dataframe(
    df.tail(10)[["open", "high", "low", "close", "volume"]],
    use_container_width=True
)


# ===============================
# SIGNAL LOGIC (SIMPLE)
# ===============================
st.subheader("🧠 Trading-Einschätzung")

signal = "NEUTRAL"

if last["return"] > PRICE_CHANGE_THRESHOLD:
    signal = "📈 LONG / CALL möglich"
elif last["return"] < -PRICE_CHANGE_THRESHOLD:
    signal = "📉 SHORT / PUT möglich"

st.markdown(f"### Signal: **{signal}**")


# ===============================
# FOOTER
# ===============================
st.caption("⚠️ Keine Anlageberatung | Daten via Alpaca Markets")
