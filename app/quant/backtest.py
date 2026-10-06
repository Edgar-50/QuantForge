import numpy as np

def _metrics(strategy_returns, equity):
    if len(strategy_returns) == 0:
        return {"total_return": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}
    mean = float(np.mean(strategy_returns))
    sd = float(np.std(strategy_returns, ddof=1)) if len(strategy_returns) > 1 else 0.0
    sharpe = float(np.sqrt(252) * mean / sd) if sd else 0.0
    peak = np.maximum.accumulate(equity)
    mdd = float(np.min(equity / peak - 1.0)) if len(equity) else 0.0
    return {"total_return": float(equity[-1] - 1.0), "sharpe": sharpe, "max_drawdown": mdd}

def moving_average_backtest(prices, short_window=5, long_window=20, transaction_cost_bps=5.0):
    p = np.asarray(prices, dtype=float)
    if len(p) <= long_window:
        raise ValueError("price series must be longer than long_window")
    if short_window >= long_window:
        raise ValueError("short_window must be smaller than long_window")

    short_ma = np.convolve(p, np.ones(short_window)/short_window, mode="valid")
    long_ma = np.convolve(p, np.ones(long_window)/long_window, mode="valid")
    offset = long_window - short_window
    signal = (short_ma[offset:] > long_ma).astype(float)
    aligned_prices = p[long_window-1:]
    returns = np.diff(aligned_prices) / aligned_prices[:-1]
    trades = np.abs(np.diff(signal))
    costs = trades[:-1] * (transaction_cost_bps / 10000.0) if len(trades) > 1 else np.array([])
    sr = returns * signal[:-1]
    if len(costs):
        sr[:len(costs)] -= costs
    equity = np.cumprod(1.0 + sr)
    metrics = _metrics(sr, equity)
    metrics.update({
        "buy_and_hold_return": float(aligned_prices[-1] / aligned_prices[0] - 1.0),
        "signal_changes": int(np.abs(np.diff(signal)).sum()),
        "equity_curve": [float(x) for x in equity],
        "signal": [int(x) for x in signal]
    })
    return metrics

def momentum_backtest(prices, lookback=10, transaction_cost_bps=5.0):
    p = np.asarray(prices, dtype=float)
    if len(p) <= lookback + 1:
        raise ValueError("price series too short for selected lookback")
    momentum = p[lookback:] / p[:-lookback] - 1.0
    signal = (momentum > 0).astype(float)
    aligned = p[lookback:]
    returns = np.diff(aligned) / aligned[:-1]
    trades = np.abs(np.diff(signal))
    sr = returns * signal[:-1]
    if len(trades):
        sr -= trades[:len(sr)] * (transaction_cost_bps / 10000.0)
    equity = np.cumprod(1.0 + sr)
    metrics = _metrics(sr, equity)
    metrics.update({
        "signal_changes": int(np.abs(np.diff(signal)).sum()),
        "equity_curve": [float(x) for x in equity],
        "signal": [int(x) for x in signal]
    })
    return metrics
