import numpy as np

def portfolio_stress(weights, shocks, portfolio_value=100000.0):
    w = np.asarray(weights, dtype=float)
    s = np.asarray(shocks, dtype=float)
    if len(w) != len(s):
        raise ValueError("weights and shocks must have equal length")
    if abs(w.sum()) < 1e-12:
        raise ValueError("weights cannot sum to zero")
    normalized = w / w.sum()
    portfolio_return = float(normalized @ s)
    pnl = float(portfolio_value * portfolio_return)
    return {
        "portfolio_return": portfolio_return,
        "pnl": pnl,
        "stressed_value": float(portfolio_value + pnl),
    }

def scenario_matrix(weights, scenarios, portfolio_value=100000.0):
    return {
        name: portfolio_stress(weights, shocks, portfolio_value)
        for name, shocks in scenarios.items()
    }
