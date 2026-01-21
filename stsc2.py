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
        limit=3,
        feed="iex"
    )
    bars = client.get_stock_bars(req).df
    data = {}

    if bars.empty:
        return data

    for s in symbols:
        try:
            data[s] = bars.loc[s].copy()
        except:
            continue
    return data


@st.cache_data(ttl=60)
def load_intraday(symbols):
    start = now - timedelta(minutes=120)
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
            df["ema9"] = df["close"].ewm(span=9).mean()
            df["ema20"] = df["close"].ewm(span=20).mean()
            df["vwap"] = (df["volume"] * df["close"]).cumsum() / df["volume"].cumsum()
            df["vol_avg"] = df["volume"].rolling(20).mean()
            data[s] = df.dropna()
        except:
            continue
    return data


# ===============================
# SCANNER
# ===============================
st.subheader("🔥 Scanner")

candidates = []

if is_premarket:
    st.info("Pre-Market Gap-Scanner")

    daily = load_daily(SYMBOLS)

    for s, df in daily.items():
        if len(df) >= 2:
            prev_close = df.iloc[-2]["close"]
            last_close = df.iloc[-1]["close"]
            gap = (last_close - prev_close) / prev_close * 100

            if abs(gap) >= 2:
                candidates.append((s, gap))

    if candidates:
        st.dataframe(
            pd.DataFrame(candidates, columns=["Symbol", "Gap %"])
            .sort_values("Gap %", ascending=False),
            use_container_width=True
        )

else:
    intraday = load_intraday(SYMBOLS)

    for s, df in intraday.items():
        if abs(df.iloc[-1]["return"]) > 0.3:
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

    if selected not in intraday:
        st.stop()

    df = intraday[selected]
    last = df.iloc[-1]

    # ===============================
    # SCORE SYSTEM
    # ===============================
    score = 0

    if last["close"] > last["vwap"]:
        score += 30
    if last["ema9"] > last["ema20"]:
        score += 20
    if abs(last["return"]) > 0.5:
        score += 30
    if last["volume"] > last["vol_avg"]:
        score += 20

    # ===============================
    # METRICS
    # ===============================
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Preis", f"${last['close']:.2f}")
    c2.metric("Return 1m", f"{last['return']:.2f}%")
    c3.metric("VWAP", f"${last['vwap']:.2f}")
    c4.metric("Score", f"{score}/100")

    # ===============================
    # CANDLESTICK CHART
    # ===============================
    fig = go.Figure()

    fig.add_candlestick(
        x=df.index,
        open=df["open"],
        high=df["high"],
        low=df["low"],
        close=df["close"],
        name="Price"
    )

    fig.add_scatter(x=df.index, y=df["ema9"], line=dict(color="blue"), name="EMA 9")
    fig.add_scatter(x=df.index, y=df["ema20"], line=dict(color="orange"), name="EMA 20")
    fig.add_scatter(x=df.index, y=df["vwap"], line=dict(color="purple"), name="VWAP")

    fig.update_layout(
        height=550,
        xaxis_rangeslider_visible=False,
        margin=dict(l=20, r=20, t=30, b=20)
    )

    st.plotly_chart(fig, use_container_width=True)

    # ===============================
    # SCORE INTERPRETATION
    # ===============================
    st.subheader("🧠 Einschätzung")

    if score >= 80:
        st.success("🔥 Starkes Setup")
    elif score >= 60:
        st.info("👍 Solides Setup")
    else:
        st.warning("⚠️ Schwaches Setup")
