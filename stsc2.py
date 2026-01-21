# ===============================
# IMPORTS
# ===============================
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta, time
import pytz
import plotly.graph_objects as go

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame


# ===============================
# CONFIG
# ===============================
st.set_page_config("Smart Momentum Trading Dashboard", layout="wide")

SYMBOLS = ["AAPL","NVDA","AMD","TSLA","META","MSFT","AMZN","COIN","PLTR","NFLX"]


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
# TIME / MARKET STATUS
# ===============================
ny = pytz.timezone("America/New_York")
now = datetime.now(ny)

market_open = time(9, 30)
market_close = time(16, 0)

is_premarket = now.time() < market_open
is_market_open = market_open <= now.time() <= market_close

st.caption(f"Aktuelle Uhrzeit (NYSE): {now}")
st.caption(
    "Marktstatus: "
    + ("🟡 Pre-Market" if is_premarket else "🟢 Market Open" if is_market_open else "🔴 After Hours")
)


# ===============================
# DATA LOADERS
# ===============================
@st.cache_data(ttl=300)
def load_daily(symbols):
    req = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Day,
        limit=2,
        feed="iex"
    )
    bars = client.get_stock_bars(req).df
    data = {}

    if bars.empty:
        return data

    for s in symbols:
        try:
            df = bars.loc[s].copy()
            data[s] = df
        except:
            continue

    return data


@st.cache_data(ttl=60)
def load_intraday(symbols):
    start = now - timedelta(minutes=90)
    req = StockBarsRequest(
        symbol_or_symbols=symbols,
        timeframe=TimeFrame.Minute,
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


# ===============================
# SCANNERS
# ===============================
st.subheader("🔥 Scanner")

candidates = []

if is_premarket:
    st.info("Pre-Market Gap-Scanner aktiv")

    daily = load_daily(SYMBOLS)

    for s, df in daily.items():
        if len(df) >= 2:
            prev_close = df.iloc[-2]["close"]
            last_close = df.iloc[-1]["close"]
            gap = (last_close - prev_close) / prev_close * 100

            if abs(gap) >= 2:
                candidates.append((s, gap))

    if candidates:
        st.success("Gapper gefunden")
        st.dataframe(
            pd.DataFrame(candidates, columns=["Symbol", "Gap %"]).sort_values(
                "Gap %", ascending=False
            ),
            use_container_width=True
        )
    else:
        st.info("Keine relevanten Gaps")

else:
    st.info("Intraday Momentum Scanner aktiv")

    intraday = load_intraday(SYMBOLS)

    for s, df in intraday.items():
        if not df.empty and abs(df.iloc[-1]["return"]) > 0.3:
            candidates.append(s)

    st.write("Momentum Kandidaten:", candidates if candidates else SYMBOLS)


# ===============================
# DETAIL VIEW
# ===============================
st.subheader("📈 Detailansicht")

available = (
    [c[0] for c in candidates] if is_premarket and candidates
    else candidates if candidates
    else SYMBOLS
)

selected = st.selectbox("Aktie auswählen", available)


# ===============================
# DETAIL LOGIC
# ===============================
if is_premarket:
    daily = load_daily([selected])

    if selected not in daily:
        st.warning("Keine Daily-Daten")
        st.stop()

    df = daily[selected]
    prev = df.iloc[-2]
    last = df.iloc[-1]

    gap = (last["close"] - prev["close"]) / prev["close"] * 100

    st.metric("Vortages-Close", f"${prev['close']:.2f}")
    st.metric("Letzter Close", f"${last['close']:.2f}")
    st.metric("Gap %", f"{gap:.2f}%")

else:
    intraday = load_intraday([selected])

    if selected not in intraday or intraday[selected].empty:
        st.warning("Keine Intraday-Daten")
        st.stop()

    df = intraday[selected]
    last = df.iloc[-1]

    c1, c2, c3 = st.columns(3)
    c1.metric("Preis", f"${last['close']:.2f}")
    c2.metric("Return 1m", f"{last['return']:.2f}%")
    c3.metric("Volumen", int(last["volume"]))

    # ===============================
    # CANDLESTICK
    # ===============================
    fig = go.Figure(data=[
        go.Candlestick(
            x=df.index,
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"]
        )
    ])

    fig.update_layout(
        height=500,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis_rangeslider_visible=False
    )

    st.plotly_chart(fig, use_container_width=True)
