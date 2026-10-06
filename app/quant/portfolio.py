import numpy as np

def _validate(expected_returns, covariance):
    mu = np.asarray(expected_returns, dtype=float)
    cov = np.asarray(covariance, dtype=float)
    if cov.shape != (len(mu), len(mu)):
        raise ValueError("covariance matrix dimensions must match expected_returns")
    return mu, cov

def minimum_variance_portfolio(expected_returns, covariance):
    mu, cov = _validate(expected_returns, covariance)
    inv = np.linalg.pinv(cov)
    ones = np.ones(len(mu))
    raw = inv @ ones
    denom = float(ones @ raw)
    if abs(denom) < 1e-12:
        raise ValueError("unable to compute stable portfolio weights")
    weights = raw / denom
    expected = float(weights @ mu)
    variance = float(weights @ cov @ weights)
    return {
        "weights": [float(w) for w in weights],
        "expected_return": expected,
        "volatility": float(np.sqrt(max(variance, 0.0))),
    }

def efficient_frontier(expected_returns, covariance, points=25):
    mu, cov = _validate(expected_returns, covariance)
    n = len(mu)
    inv = np.linalg.pinv(cov)
    ones = np.ones(n)

    A = float(ones @ inv @ ones)
    B = float(ones @ inv @ mu)
    C = float(mu @ inv @ mu)
    D = A * C - B * B
    if abs(D) < 1e-12:
        raise ValueError("frontier is numerically unstable for this covariance matrix")

    targets = np.linspace(float(mu.min()), float(mu.max()), points)
    result = []
    for target in targets:
        lam = (C - B * target) / D
        gam = (A * target - B) / D
        w = inv @ (lam * ones + gam * mu)
        var = float(w @ cov @ w)
        result.append({
            "target_return": float(target),
            "volatility": float(np.sqrt(max(var, 0.0))),
            "weights": [float(x) for x in w]
        })
    return {"frontier": result}
