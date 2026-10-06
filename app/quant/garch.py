"""GARCH(1,1) via Gaussian QMLE (scipy) with variance-targeting start and a multi-step vol forecast."""
import numpy as np
from scipy.optimize import minimize


def _filter(params, r):
    omega, alpha, beta = params
    h = np.empty_like(r); h[0] = r.var()
    for t in range(1, len(r)):
        h[t] = omega + alpha * r[t - 1] ** 2 + beta * h[t - 1]
    return h


def fit_garch(returns, horizon=21):
    r = np.asarray(returns, float); r = r - r.mean()
    if len(r) < 120:
        raise ValueError("need >=120 returns for GARCH")
    scale = 100.0; x = r * scale          # work in % for conditioning
    def nll(p):
        if p[0] <= 0 or p[1] < 0 or p[2] < 0 or p[1] + p[2] >= 0.9999:
            return 1e12
        h = np.maximum(_filter(p, x), 1e-10)
        return 0.5 * np.sum(np.log(h) + x ** 2 / h)
    v = x.var()
    best = None
    for a0, b0 in ((.08, .90), (.05, .93), (.12, .80)):
        res = minimize(nll, [v * (1 - a0 - b0), a0, b0], method="Nelder-Mead", options={"maxiter": 1500, "xatol": 1e-6, "fatol": 1e-6})
        if best is None or res.fun < best.fun:
            best = res
    omega, alpha, beta = best.x
    h = _filter(best.x, x)
    persistence = alpha + beta
    long_var = omega / max(1 - persistence, 1e-6)
    h_next = omega + alpha * x[-1] ** 2 + beta * h[-1]
    path = []
    for k in range(horizon):
        path.append(long_var + persistence ** k * (h_next - long_var))
    daily = np.sqrt(np.array(path)) / scale
    return {
        "omega": float(omega / scale ** 2), "alpha": float(alpha), "beta": float(beta),
        "persistence": float(persistence),
        "half_life_days": float(np.log(.5) / np.log(persistence)) if 0 < persistence < 1 else None,
        "long_run_vol_ann": float(np.sqrt(long_var) / scale * np.sqrt(252)),
        "current_vol_ann": float(np.sqrt(h[-1]) / scale * np.sqrt(252)),
        "forecast_vol_ann": [float(v * np.sqrt(252)) for v in daily],
        "daily_vol_forecast": [float(v) for v in daily],
        "cond_vol_series_ann": [float(np.sqrt(v) / scale * np.sqrt(252)) for v in h],
        "log_likelihood": float(-best.fun),
    }
