def trade_plan(s):
    return {
        "Entry": round(s.price, 2),
        "Stop": round(s.price - s.atr * 1.5, 2),
        "Target": round(s.price + s.atr * 3, 2),
        "Risk/Reward": "1 : 2"
    }
