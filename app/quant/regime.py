import numpy as np

def classify_regime(returns):
    r = np.asarray(returns, dtype=float)
    if r.size < 10:
        raise ValueError("at least 10 returns are required")

    short = r[-5:].mean()
    medium = r[-20:].mean() if r.size >= 20 else r.mean()
    vol = r.std(ddof=1) * np.sqrt(252)

    score = 0.0
    score += 1.0 if short > 0 else -1.0
    score += 1.0 if medium > 0 else -1.0
    score -= min(vol / 0.35, 1.5)

    if score >= 1.0:
        label = "risk_on"
    elif score <= -1.0:
        label = "risk_off"
    elif vol >= 0.30:
        label = "high_volatility"
    else:
        label = "sideways"

    return {
        "regime": label,
        "score": float(score),
        "short_mean": float(short),
        "medium_mean": float(medium),
        "annualized_volatility": float(vol),
        "confidence": float(min(0.99, 0.55 + abs(score) * 0.15))
    }
