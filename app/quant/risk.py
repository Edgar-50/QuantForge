import numpy as np

TRADING_DAYS = 252

def _arr(values):
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        raise ValueError("series cannot be empty")
    return arr

def historical_var(returns, confidence=0.95):
    r = _arr(returns)
    percentile = np.quantile(r, 1 - confidence)
    return float(max(0.0, -percentile))

def conditional_var(returns, confidence=0.95):
    r = _arr(returns)
    threshold = np.quantile(r, 1 - confidence)
    tail = r[r <= threshold]
    return float(max(0.0, -tail.mean())) if tail.size else 0.0

def max_drawdown(returns):
    r = _arr(returns)
    wealth = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(wealth)
    return float((wealth / peak - 1.0).min())

def sharpe_ratio(returns, risk_free_rate=0.0):
    r = _arr(returns)
    rf_daily = (1 + risk_free_rate) ** (1 / TRADING_DAYS) - 1
    excess = r - rf_daily
    sd = excess.std(ddof=1)
    if sd == 0 or np.isnan(sd):
        return 0.0
    return float(np.sqrt(TRADING_DAYS) * excess.mean() / sd)

def sortino_ratio(returns, risk_free_rate=0.0):
    r = _arr(returns)
    rf_daily = (1 + risk_free_rate) ** (1 / TRADING_DAYS) - 1
    excess = r - rf_daily
    downside = excess[excess < 0]
    if downside.size == 0:
        return None  # no downside observations: undefined (inf is not valid JSON)
    downside_dev = np.sqrt(np.mean(downside ** 2))
    return float(np.sqrt(TRADING_DAYS) * excess.mean() / downside_dev) if downside_dev else 0.0

def beta_alpha(asset_returns, market_returns, risk_free_rate=0.0):
    a = _arr(asset_returns)
    m = _arr(market_returns)
    if len(a) != len(m):
        raise ValueError("asset_returns and market_returns must have equal length")
    if len(a) < 3:
        raise ValueError("at least 3 observations are required")
    cov = np.cov(a, m, ddof=1)
    market_var = cov[1,1]
    beta = cov[0,1] / market_var if market_var else 0.0
    rf_daily = (1 + risk_free_rate) ** (1/TRADING_DAYS) - 1
    alpha_daily = a.mean() - (rf_daily + beta * (m.mean() - rf_daily))
    return {"beta": float(beta), "alpha_annualized": float(alpha_daily * TRADING_DAYS)}
