import numpy as np, pandas as pd
from scipy import stats

def _cf_var(r, conf):
    z = stats.norm.ppf(1 - conf); s, k = stats.skew(r), stats.kurtosis(r)
    zc = z + (z ** 2 - 1) * s / 6 + (z ** 3 - 3 * z) * k / 24 - (2 * z ** 3 - 5 * z) * s ** 2 / 36
    return float(max(0.0, -(r.mean() + zc * r.std(ddof=1))))

def kupiec(exceptions, n, p):
    """Kupiec proportion-of-failures test for VaR calibration."""
    x = exceptions
    if x == 0: lr = -2 * n * np.log(1 - p)
    else:
        ph = x / n; lr = -2 * ((n - x) * np.log(1 - p) + x * np.log(p) - (n - x) * np.log(1 - ph) - x * np.log(ph))
    return float(stats.chi2.sf(lr, 1))

def analyze(r: pd.Series, conf=0.95, rf=0.03, sims=20000, seed=11):
    x = r.dropna().values; n = len(x)
    if n < 60: raise ValueError("need >= 60 observations")
    a = 1 - conf; rng = np.random.default_rng(seed)
    hist = float(max(0, -np.quantile(x, a))); tail = x[x <= np.quantile(x, a)]
    df_t, loc_t, sc_t = stats.t.fit(x); mc = stats.t.rvs(df_t, loc_t, sc_t, sims, random_state=seed)
    eq = np.cumprod(1 + x); peak = np.maximum.accumulate(eq); dd = eq / peak - 1
    # drawdown episodes
    eps, i = [], 0
    while i < n:
        if dd[i] < 0:
            j = i
            while j < n and dd[j] < 0: j += 1
            k = i + int(np.argmin(dd[i:j])); eps.append({"start": int(i), "trough": k, "end": j if j < n else None, "depth": float(dd[k]), "days": int(j - i)}); i = j
        else: i += 1
    eps = sorted(eps, key=lambda e: e["depth"])[:5]
    idx = r.dropna().index
    for e in eps: e.update(start=str(idx[e["start"]].date()), trough=str(idx[e["trough"]].date()), end=str(idx[e["end"]].date()) if e["end"] is not None else "ongoing")
    # rolling VaR backtest (250d window, 1-day horizon)
    W = min(250, n // 2); exc = 0; tot = 0; hits = []
    for t in range(W, n):
        v = -np.quantile(x[t - W:t], a); tot += 1; ex = x[t] < -v; exc += int(ex)
        if ex: hits.append(t)
    ann = float(x.mean() * 252); vol = float(x.std(ddof=1) * np.sqrt(252)); dn = x[x < 0]
    jb = stats.jarque_bera(x)
    rv = pd.Series(x).rolling(21).std() * np.sqrt(252); rs = pd.Series(x).rolling(63).apply(lambda z: z.mean() / z.std() * np.sqrt(252) if z.std() else 0)
    h_counts, h_edges = np.histogram(x, bins=40)
    return {
        "n": n, "confidence": conf,
        "var": {"historical": hist, "parametric_normal": float(max(0, -(x.mean() + stats.norm.ppf(a) * x.std(ddof=1)))),
                "cornish_fisher": _cf_var(x, conf), "student_t_mc": float(max(0, -np.quantile(mc, a)))},
        "cvar": {"historical": float(-tail.mean()) if len(tail) else 0.0, "student_t_mc": float(-mc[mc <= np.quantile(mc, a)].mean())},
        "moments": {"mean_ann": ann, "vol_ann": vol, "skew": float(stats.skew(x)), "excess_kurtosis": float(stats.kurtosis(x)),
                    "jarque_bera_p": float(jb.pvalue), "student_t_df": float(df_t), "best_day": float(x.max()), "worst_day": float(x.min())},
        "ratios": {"sharpe": float((ann - rf) / vol) if vol else 0, "sortino": float((ann - rf) / (np.sqrt((dn ** 2).mean()) * np.sqrt(252))) if len(dn) else None,
                   "calmar": float(ann / abs(dd.min())) if dd.min() < 0 else None, "max_drawdown": float(dd.min()),
                   "omega_0": float(x[x > 0].sum() / abs(x[x < 0].sum())) if (x < 0).any() else None,
                   "tail_ratio": float(abs(np.quantile(x, .95) / np.quantile(x, .05)))},
        "var_backtest": {"window": W, "observations": tot, "exceptions": exc, "expected": float(tot * a), "kupiec_p": kupiec(exc, tot, a),
                         "verdict": "calibrated" if kupiec(exc, tot, a) > 0.05 else "miscalibrated"},
        "drawdown": [float(v) for v in dd], "dd_episodes": eps,
        "rolling_vol": [None if not np.isfinite(v) else float(v) for v in rv], "rolling_sharpe": [None if not np.isfinite(v) else float(v) for v in rs],
        "dates": [str(d.date()) for d in idx],
        "hist": {"counts": h_counts.tolist(), "edges": h_edges.tolist()},
    }

def simulate_paths(r: pd.Series, start=100000.0, years=1.0, sims=3000, method="bootstrap", seed=5, drift=None):
    x = r.dropna().values; steps = int(252 * years); rng = np.random.default_rng(seed)
    if method == "bootstrap":
        R = rng.choice(x, size=(sims, steps), replace=True)
        if drift is not None: R = R - x.mean() + drift / 252
    else:
        mu = (drift if drift is not None else x.mean() * 252) / 252; s = x.std(ddof=1)
        R = rng.normal(mu - 0.5 * s ** 2, s, (sims, steps)); R = np.expm1(R)
    P = start * np.cumprod(1 + R, axis=1); P = np.hstack([np.full((sims, 1), start), P])
    q = {k: np.percentile(P, k, axis=0).tolist() for k in (5, 25, 50, 75, 95)}
    term = P[:, -1]; mdd = (P / np.maximum.accumulate(P, axis=1) - 1).min(axis=1)
    return {"steps": steps, "bands": q, "sample_paths": P[:25].tolist(), "start": start, "method": method,
            "terminal": {"mean": float(term.mean()), "median": float(np.median(term)), "p05": float(np.percentile(term, 5)), "p95": float(np.percentile(term, 95)),
                         "prob_loss": float((term < start).mean()), "prob_gain_20": float((term > start * 1.2).mean()),
                         "prob_dd_20": float((mdd < -0.2).mean()), "median_max_dd": float(np.median(mdd))}}
