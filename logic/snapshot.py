from dataclasses import dataclass

@dataclass
class MarketSnapshot:
    symbol: str
    price: float
    rsi: float
    ema_fast: float
    ema_mid: float
    ema_slow: float
    atr: float
    volume_factor: float
    market_state: str
