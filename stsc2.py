import streamlit as st
import pandas as pd
import pytz
from datetime import datetime

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from logic.indicators import ema, rsi
from logic.trend_score import calculate_trend_score, traffic_light
from logic.trade_plan import trade_plan
from logic.premarket_scanner import scan_early_movers
from data.sp500_symbols import SP500_SYMBOLS

# --------------------------------------------------
st.set_page_config("Smart Momentum Trading Dashboard", layout="wide")

client = StockHistoricalDataClient(
    api_key=st.secrets["ALPACA_API_KEY"],
    secret_key=st.secrets["ALPACA_SECRET_KEY"]
)

if "symbol" not in st.session_state:
    st.session_state.symbol = "AAPL"

# --------------------------------------------------
st.title("📊 Smart Momentum Trading Dashboard")

ny = pytz.timezone("US/Eastern")
now = datetime.now(ny)

if now.hour < 9 or (now.hour == 9 and now.minute < 30):
    market_state = "PRE"
elif now.hour < 16:
    market_state = "OPEN"
else:
    market_state = "CLOSED"

st.write(f"Marktstatus: {market_state}")
st.divider()

# --------------------------------------------------
tab_early, tab_day, tab_swing = st.tabs([
    "🔥 Early Movers",
    "⚡ Daytrade",
    "📆 Swingtrade"
])

# --------------------------------------------------
with tab_early:
    df = scan_early_movers(SP500_SYMBOLS, client)
    if df.empty:
        st.info("Keine Early Movers")
    else:
        st.dataframe(df, width="stretch")
        for _, r in df.iterrows():
            if st.button(r["Symbol"]):
                st.session_state.symbol = r["Symbol"]

# --------------------------------------------------
def render_chart(symbol, timeframe, title):
    req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=timeframe, limit=300)
    bars = client.get_stock_bars(req).df
    if bars is None or bars.empty:
        st.warning("Keine Daten")
        return

    df = bars.xs(symbol)
    df["ema20"] = ema(df["close"], 20)
    df["ema50"] = ema(df["close"], 50)
    df["rsi"] = rsi(df["close"])
    df["vol_ma"] = df["volume"].rolling(20).mean()
    df.dropna(inplace=True)

    if len(df) < 30:
        st.warning("Zu wenig Daten")
        return

    score = calculate_trend_score(df.iloc[-1])
    label, color = traffic_light(score)
    plan = trade_plan(df.iloc[-1]["close"], df["close"].rolling(14).std().iloc[-1])

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True)

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"]
    ), row=1, col=1)

    fig.add_trace(go.Bar(x=df.index, y=df["volume"]), row=2, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["rsi"]), row=3, col=1)

    fig.add_annotation(
        x=0.01, y=0.95, xref="paper", yref="paper",
        text=f"{label} ({score})",
        bgcolor=color, showarrow=False
    )

    st.plotly_chart(fig, width="stretch")

# --------------------------------------------------
with tab_day:
    render_chart(st.session_state.symbol, TimeFrame.Minute, "Daytrade")

with tab_swing:
    render_chart(st.session_state.symbol, TimeFrame.Day, "Swingtrade")
