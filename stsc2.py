import streamlit as st
import pandas as pd
import pytz
import plotly.graph_objects as go
from datetime import datetime

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from data.sp500_symbols import SP500_SYMBOLS
from logic.indicators import ema, rsi, atr
from logic.snapshot import MarketSnapshot
from logic.trend_score import calculate_trend_score
from logic.option_bias import option_bias
from logic.trade_plan import trade_plan
from logic.premarket_scanner import scan_early_movers

# =====================================================
# CONFIG
# =====================================================
st.set_page_config(
    page_title="Smart Momentum Trading Dashboard",
    layout="wide"
)

# =====================================================
# ALPACA
# =====================================================
client = StockHistoricalDataClient(
    api_key=st.secrets["ALPACA_API_KEY"],
    secret_key=st.secrets["ALPACA_SECRET_KEY"]
)

# =====================================================
# HEADER
# =====================================================
st.title("📊 Smart Momentum Trading Dashboard")

ny_time = datetime.now(pytz.timezone("US/Eastern"))
st.write("Aktuelle Uhrzeit (NYSE):", ny_time)

if ny_time.hour < 9 or (ny_time.hour == 9 and ny_time.minute < 30):
    market_state = "PRE"
    st.write("Marktstatus: 🟡 Pre-Market")
elif ny_time.hour < 16:
    market_state = "OPEN"
    st.write("Marktstatus: 🟢 Open")
else:
    market_state = "CLOSED"
    st.write("Marktstatus: 🔴 Closed")

st.divider()

# =====================================================
# TABS
# =====================================================
tab_early, tab_sp500, tab_day, tab_swing = st.tabs([
    "🔥 Early Movers",
    "🧠 S&P 500 Scanner",
    "⚡ Daytrade",
    "🧭 Swing"
])

# =====================================================
# 🔥 EARLY MOVERS
# =====================================================
with tab_early:
    st.subheader("🔥 Early Movers (Pre-Market Gaps)")

    df = scan_early_movers(
        symbols=SP500_SYMBOLS,
        client=client,
        max_results=20
    )

    if df.empty:
        st.info("Keine Early Movers gefunden – Markt ruhig")
    else:
        st.dataframe(df, use_container_width=True, hide_index=True)

# =====================================================
# 🧠 S&P 500 SCANNER
# =====================================================
with tab_sp500:
    st.subheader("🧠 S&P 500 Trend-Scanner (Daily)")

    results = []

    for symbol in SP500_SYMBOLS:
        try:
            req = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                limit=60
            )
            df = client.get_stock_bars(req).df
            if df is None or df.empty:
                continue

            df["ema9"] = ema(df["close"], 9)
            df["ema20"] = ema(df["close"], 20)
            df["ema50"] = ema(df["close"], 50)
            df["rsi"] = rsi(df["close"])
            df["atr"] = atr(df)
            df.dropna(inplace=True)

            last = df.iloc[-1]

            snap = MarketSnapshot(
                symbol=symbol,
                price=float(last["close"]),
                rsi=float(last["rsi"]),
                ema9=float(last["ema9"]),
                ema20=float(last["ema20"]),
                ema50=float(last["ema50"]),
                atr=float(last["atr"]),
                volume_ratio=float(last["volume"] / df["volume"].mean()),
                market_state=market_state
            )

            score = calculate_trend_score(snap)

            results.append({
                "Symbol": symbol,
                "Trend-Score": score,
                "Bias": option_bias(snap, score)
            })

        except Exception:
            continue

    if results:
        res = pd.DataFrame(results).sort_values("Trend-Score", ascending=False).head(20)
        st.dataframe(res, use_container_width=True, hide_index=True)
    else:
        st.info("Keine verwertbaren Daten")

# =====================================================
# ⚡ DAYTRADE (CANDLESTICK)
# =====================================================
with tab_day:
    st.subheader("⚡ Daytrade – Intraday Chart")

    symbol = st.selectbox("Aktie auswählen", SP500_SYMBOLS, key="day")

    try:
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            limit=200
        )
        df = client.get_stock_bars(req).df

        if df is None or df.empty:
            st.warning("Keine Intraday-Daten")
        else:
            df["ema9"] = ema(df["close"], 9)
            df["ema20"] = ema(df["close"], 20)
            df["ema50"] = ema(df["close"], 50)
            df["atr"] = atr(df)
            df.dropna(inplace=True)

            last = df.iloc[-1]

            snap = MarketSnapshot(
                symbol=symbol,
                price=float(last["close"]),
                rsi=rsi(df["close"]).iloc[-1],
                ema9=last["ema9"],
                ema20=last["ema20"],
                ema50=last["ema50"],
                atr=last["atr"],
                volume_ratio=float(last["volume"] / df["volume"].mean()),
                market_state=market_state
            )

            plan = trade_plan(snap, calculate_trend_score(snap))

            fig = go.Figure()

            fig.add_candlestick(
                x=df.index,
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"],
                name="Preis"
            )

            fig.add_scatter(x=df.index, y=df["ema9"], name="EMA 9")
            fig.add_scatter(x=df.index, y=df["ema20"], name="EMA 20")
            fig.add_scatter(x=df.index, y=df["ema50"], name="EMA 50")

            if plan:
                fig.add_hline(y=plan["Entry"], line_dash="dot", annotation_text="Entry")
                fig.add_hline(y=plan["Stop"], line_dash="dash", annotation_text="Stop")
                fig.add_hline(y=plan["Target"], line_dash="dash", annotation_text="Target")

            fig.update_layout(height=600, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

    except Exception:
        st.error("Fehler beim Laden der Daytrade-Daten")

# =====================================================
# 🧭 SWING (CANDLESTICK)
# =====================================================
with tab_swing:
    st.subheader("🧭 Swing – Daily Chart")

    symbol = st.selectbox("Aktie auswählen", SP500_SYMBOLS, key="swing")

    try:
        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            limit=150
        )
        df = client.get_stock_bars(req).df

        if df is None or df.empty:
            st.warning("Keine Daily-Daten")
        else:
            df["ema9"] = ema(df["close"], 9)
            df["ema20"] = ema(df["close"], 20)
            df["ema50"] = ema(df["close"], 50)
            df["atr"] = atr(df)
            df.dropna(inplace=True)

            last = df.iloc[-1]

            snap = MarketSnapshot(
                symbol=symbol,
                price=float(last["close"]),
                rsi=rsi(df["close"]).iloc[-1],
                ema9=last["ema9"],
                ema20=last["ema20"],
                ema50=last["ema50"],
                atr=last["atr"],
                volume_ratio=float(last["volume"] / df["volume"].mean()),
                market_state=market_state
            )

            plan = trade_plan(snap, calculate_trend_score(snap))

            fig = go.Figure()

            fig.add_candlestick(
                x=df.index,
                open=df["open"],
                high=df["high"],
                low=df["low"],
                close=df["close"]
            )

            fig.add_scatter(x=df.index, y=df["ema9"], name="EMA 9")
            fig.add_scatter(x=df.index, y=df["ema20"], name="EMA 20")
            fig.add_scatter(x=df.index, y=df["ema50"], name="EMA 50")

            if plan:
                fig.add_hline(y=plan["Entry"], annotation_text="Entry")
                fig.add_hline(y=plan["Stop"], annotation_text="Stop")
                fig.add_hline(y=plan["Target"], annotation_text="Target")

            fig.update_layout(height=600, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

    except Exception:
        st.error("Fehler beim Laden der Swing-Daten")
