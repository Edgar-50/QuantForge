import numpy as np

def factor_exposures(asset_returns, factors):
    y = np.asarray(asset_returns, dtype=float)
    X = np.asarray(factors, dtype=float)
    if X.ndim == 1:
        X = X.reshape(-1, 1)
    if len(y) != len(X):
        raise ValueError("asset_returns and factors must have equal observations")
    if len(y) < X.shape[1] + 2:
        raise ValueError("not enough observations for factor regression")

    Xd = np.column_stack([np.ones(len(X)), X])
    beta = np.linalg.pinv(Xd.T @ Xd) @ Xd.T @ y
    fitted = Xd @ beta
    resid = y - fitted
    ss_res = float(np.sum(resid ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot else 0.0
    return {
        "alpha": float(beta[0]),
        "factor_betas": [float(x) for x in beta[1:]],
        "r_squared": float(r2),
        "residual_volatility": float(np.std(resid, ddof=1) if len(resid) > 1 else 0.0),
    }
