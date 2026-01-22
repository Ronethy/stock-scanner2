def calculate_trend_score(s):
    score = 0

    if s.ema_fast > s.ema_mid > s.ema_slow:
        score += 40
    if s.rsi > 55:
        score += 20
    if s.market_state == "OPEN":
        score += 10

    return score

def trend_ampel(score):
    if score >= 60:
        return "BUY 🟢"
    elif score >= 40:
        return "NEUTRAL 🟡"
    return "AVOID 🔴"
