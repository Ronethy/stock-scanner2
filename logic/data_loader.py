import os
import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

def get_client():
    api_key = os.getenv("APCA_API_KEY_ID")
    secret_key = os.getenv("APCA_API_SECRET_KEY")

    if not api_key or not secret_key:
        raise ValueError("Alpaca API Keys fehlen")

    return StockHistoricalDataClient(
        api_key=api_key,
        secret_key=secret_key
    )

def load_daily_data(symbol, limit=300):
    try:
        client = get_client()

        req = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            limit=limit
        )

        bars = client.get_stock_bars(req).df

        if bars is None or bars.empty:
            return None

        if isinstance(bars.index, pd.MultiIndex):
            bars = bars.xs(symbol)

        return bars.sort_index()

    except Exception as e:
        return None
