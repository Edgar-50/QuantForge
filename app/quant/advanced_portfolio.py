import numpy as np

def _cov(covariance):
    c = np.asarray(covariance, dtype=float)
    if c.ndim != 2 or c.shape[0] != c.shape[1]:
        raise ValueError("covariance must be square")
    return c

def inverse_volatility_weights(covariance):
    cov = _cov(covariance)
    vols = np.sqrt(np.clip(np.diag(cov), 1e-16, None))
    raw = 1.0 / vols
    w = raw / raw.sum()
    return {"weights": [float(x) for x in w]}

def risk_parity_weights(covariance, iterations=5000, tolerance=1e-10):
    cov = _cov(covariance)
    n = cov.shape[0]
    w = np.ones(n) / n

    for _ in range(iterations):
        port_var = float(w @ cov @ w)
        if port_var <= 0:
            break
        marginal = cov @ w
        rc = w * marginal
        target = port_var / n
        prev = w.copy()
        # multiplicative risk-budgeting update
        ratio = np.where(rc > 1e-18, target / rc, 1.0)
        w *= np.sqrt(np.clip(ratio, 0.2, 5.0))
        w = np.clip(w, 1e-10, None)
        w /= w.sum()
        if np.max(np.abs(w - prev)) < tolerance:
            break

    port_var = float(w @ cov @ w)
    rc = w * (cov @ w)
    shares = rc / port_var if port_var else np.zeros(n)

    return {
        "weights": [float(x) for x in w],
        "risk_contribution_shares": [float(x) for x in shares],
    }

def shrink_covariance(sample_covariance, shrinkage=0.25):
    cov = _cov(sample_covariance)
    if not 0 <= shrinkage <= 1:
        raise ValueError("shrinkage must be between 0 and 1")
    diag_target = np.diag(np.diag(cov))
    shrunk = (1 - shrinkage) * cov + shrinkage * diag_target
    return {"covariance": shrunk.tolist(), "shrinkage": float(shrinkage)}
