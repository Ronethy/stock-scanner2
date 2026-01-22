import streamlit as st
import pandas as pd
import pytz
from datetime import datetime

import plotly.graph_objects as go
from plotly.subplots import make_subplots

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# Logic imports
from logic.indicators import ema, rsi
from logic.trend_score import calculate_trend_score, traffic_light
from logic.trade_plan import trade_plan
from logic.premarket_scanner import scan_early_movers
from data.sp500_symbols import SP500_SYMBOLS

# =====================================================
# CONFIG
# =====================================================
st.set_page_config("Smart Momentum Trading Dashboard", layout="wide")

# Alpaca Client
client = StockHistoricalDataClient(
    api_key=st.secrets["ALPACA_API_KEY"],
    secret_key=st.secrets["ALPACA_SECRET_KEY"]
)

# Session State für ausgewählte Aktie
if "symbol" not in st.session_state:
    st.session_state.symbol = "AAPL"

# =====================================================
# HEADER
# =====================================================
st.title("📊 Smart Momentum Trading Dashboard")

ny = pytz.timezone("US/Eastern")
now = datetime.now(ny)

# Marktstatus bestimmen
if now.hour < 9 or (now.hour == 9 and now.minute < 30):
    market_state = "PRE-MARKET"
    color = "🟡"
elif now.hour < 16:
    market_state = "OPEN"
    color = "🟢"
else:
    market_state = "CLOSED"
    color = "🔴"

st.write(f"Aktuelle Uhrzeit (NYSE): {now.strftime('%Y-%m-%d %H:%M:%S')} - Marktstatus: {color} {market_state}")
st.divider()

# =====================================================
# TABS
# =====================================================
tab_early, tab_day, tab_swing = st.tabs([
    "🔥 Early Movers",
    "⚡ Daytrade",
    "📆 Swingtrade"
])

# =====================================================
# TAB 1 - EARLY MOVERS
# =====================================================
with tab_early:
    df = scan_early_movers(SP500_SYMBOLS, client)
    if df.empty:
        st.info("Keine Early Movers gefunden")
    else:
        st.dataframe(df, width="stretch")

        for _, r in df.iterrows():
            if st.button(r["Symbol"]):
                st.session_state.symbol = r["Symbol"]

# =====================================================
# CHART-RENDER FUNCTION
# =====================================================
def render_chart(symbol, timeframe, title):
    req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=timeframe, limit=300)
    bars = client.get_stock_bars(req).df
    if bars is None or bars.empty:
        st.warning("Keine Daten verfügbar")
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

    # Letzte Kerze für Score / Ampel / Trade-Plan
    last = df.iloc[-1]
    score = calculate_trend_score(last)
    label, color = traffic_light(score)
    plan = trade_plan(last["close"], df["close"].rolling(14).std().iloc[-1])

    # --------------------------
    # Plotly Chart mit Subplots
    # --------------------------
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                        row_heights=[0.6,0.2,0.2], vertical_spacing=0.03)

    # Candles + EMA
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["open"], high=df["high"],
        low=df["low"], close=df["close"], name="Candles"
    ), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["ema20"], line=dict(color="blue", width=1), name="EMA20"), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df["ema50"], line=dict(color="orange", width=1), name="EMA50"), row=1, col=1)

    # Volume
    fig.add_trace(go.Bar(x=df.index, y=df["volume"], name="Volume"), row=2, col=1)

    # RSI
    fig.add_trace(go.Scatter(x=df.index, y=df["rsi"], name="RSI", line=dict(color="purple", width=1)), row=3, col=1)

    # Ampel-Annotation
    fig.add_annotation(
        x=0.01, y=0.95, xref="paper", yref="paper",
        text=f"{label} ({score})",
        bgcolor=color, showarrow=False
    )

    fig.update_layout(height=700, title_text=f"{title}: {symbol}", showlegend=True)
    st.plotly_chart(fig, width="stretch")

    # --------------------------
    # Trade-Plan Box
    # --------------------------
    st.markdown("### 📝 Trade-Plan")
    st.write(plan)

# =====================================================
# TAB 2 - DAYTRADE
# =====================================================
with tab_day:
    render_chart(st.session_state.symbol, TimeFrame.Minute, "Daytrade")

# =====================================================
# TAB 3 - SWINGTRADE
# =====================================================
with tab_swing:
    render_chart(st.session_state.symbol, TimeFrame.Day, "Swingtrade")
