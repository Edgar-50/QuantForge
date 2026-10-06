"""Long-only portfolio construction on real return panels (Ledoit-Wolf covariance, shrunk means)."""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.cluster.hierarchy import linkage, leaves_list
from sklearn.covariance import LedoitWolf

TD = 252

def estimates(R: pd.DataFrame):
    cov = LedoitWolf().fit(R.values).covariance_ * TD
    mu_s = R.mean().values * TD
    mu = 0.5 * mu_s + 0.5 * mu_s.mean()          # shrink toward grand mean: raw sample means are mostly noise
    return mu, cov

def _bounds(n, cap): return [(0.0, cap)] * n
def _cons(): return [{"type": "eq", "fun": lambda w: w.sum() - 1}]

def _solve(fun, n, cap):
    cap = max(cap, 1.0 / n + 1e-6); w0 = np.ones(n) / n
    r = minimize(fun, w0, method="SLSQP", bounds=_bounds(n, cap), constraints=_cons(), options={"maxiter": 500, "ftol": 1e-10})
    w = np.clip(r.x, 0, None); return w / w.sum()

def max_sharpe(mu, cov, rf, cap): return _solve(lambda w: -(w @ mu - rf) / np.sqrt(w @ cov @ w + 1e-12), len(mu), cap)
def min_vol(mu, cov, cap): return _solve(lambda w: w @ cov @ w, len(mu), cap)
def risk_parity(cov, cap):
    n = len(cov)
    def f(w):
        rc = w * (cov @ w); return float(((rc - rc.mean()) ** 2).sum() * 1e4)
    return _solve(f, n, cap)

def hrp(cov, corr):
    n = len(cov); dist = np.sqrt(np.clip((1 - corr) / 2, 0, 1))
    iu = np.triu_indices(n, 1); order = list(leaves_list(linkage(dist[iu], "single")))
    w = pd.Series(1.0, index=order)
    def cvar(items):
        sub = cov[np.ix_(items, items)]; iv = 1 / np.diag(sub); iv /= iv.sum(); return float(iv @ sub @ iv)
    clusters = [order]
    while clusters:
        clusters = [c[j:k] for c in clusters for j, k in ((0, len(c) // 2), (len(c) // 2, len(c))) if len(c) > 1]
        for i in range(0, len(clusters), 2):
            a, b = clusters[i], clusters[i + 1]; va, vb = cvar(a), cvar(b); alpha = 1 - va / (va + vb)
            w[a] *= alpha; w[b] *= 1 - alpha
    out = np.zeros(n); out[w.index.values] = w.values; return out / out.sum()

def _stats(w, mu, cov, rf):
    r, v = float(w @ mu), float(np.sqrt(w @ cov @ w)); return {"ret": r, "vol": v, "sharpe": (r - rf) / v if v else 0.0}

def optimize(R: pd.DataFrame, method="max_sharpe", rf=0.03, cap=0.6, holdout=0.4, n_random=1200, frontier_pts=18):
    n = R.shape[1]; names = list(R.columns)
    if n < 2: raise ValueError("select at least 2 assets")
    mu, cov = estimates(R); sd = np.sqrt(np.diag(cov)); corr = cov / np.outer(sd, sd)
    ws = {"max_sharpe": lambda c_: max_sharpe(mu, cov, rf, cap), "min_vol": lambda c_: min_vol(mu, cov, cap),
          "risk_parity": lambda c_: risk_parity(cov, cap), "hrp": lambda c_: hrp(cov, corr), "equal": lambda c_: np.ones(n) / n}
    if method not in ws: raise ValueError("unknown method")
    w = ws[method](None)
    rc = w * (cov @ w); rc = rc / rc.sum()
    # frontier (long-only, capped) + random portfolios
    cap_ = max(cap, 1.0 / n + 1e-6); front = []
    wmax, left = np.zeros(n), 1.0                      # max-return portfolio under the weight cap (greedy fill)
    for i in np.argsort(-mu):
        take = min(cap_, left); wmax[i] = take; left -= take
        if left <= 1e-12: break
    hi_r = float(wmax @ mu) - 1e-4
    for t in np.linspace(float(min_vol(mu, cov, cap) @ mu), hi_r, frontier_pts):
        r = minimize(lambda x: x @ cov @ x, np.ones(n) / n, method="SLSQP", bounds=_bounds(n, cap_),
                     constraints=_cons() + [{"type": "eq", "fun": lambda x, t=t: x @ mu - t}], options={"maxiter": 300})
        if r.success: front.append({"ret": float(r.x @ mu), "vol": float(np.sqrt(r.x @ cov @ r.x))})
    rng = np.random.default_rng(1); W = rng.dirichlet(np.ones(n), n_random); W = W[W.max(1) <= cap_ + 1e-9]
    rnd = [{"ret": float(x @ mu), "vol": float(np.sqrt(x @ cov @ x))} for x in W[:900]]
    # honest out-of-sample test: fit on first (1-holdout), evaluate on the rest vs equal weight
    cut = int(len(R) * (1 - holdout)); Rtr, Rte = R.iloc[:cut], R.iloc[cut:]
    mu_t, cov_t = estimates(Rtr); sdt = np.sqrt(np.diag(cov_t)); ct = cov_t / np.outer(sdt, sdt)
    wt = {"max_sharpe": max_sharpe(mu_t, cov_t, rf, cap), "min_vol": min_vol(mu_t, cov_t, cap), "risk_parity": risk_parity(cov_t, cap),
          "hrp": hrp(cov_t, ct), "equal": np.ones(n) / n}[method]
    eq = lambda ww: ((1 + Rte.values @ ww).cumprod()).tolist()
    pr = lambda ww: (lambda x: {"total_return": float((1 + x).prod() - 1), "sharpe": float(x.mean() / x.std() * np.sqrt(TD)) if x.std() else 0.0,
                                "ann_vol": float(x.std() * np.sqrt(TD))})(Rte.values @ ww)
    return {"assets": names, "weights": w.tolist(), "stats": _stats(w, mu, cov, rf), "risk_contribution": rc.tolist(),
            "diversification_ratio": float((w @ sd) / np.sqrt(w @ cov @ w)),
            "effective_n": float(1 / (w ** 2).sum()), "mu": mu.tolist(), "vol": sd.tolist(), "corr": corr.tolist(),
            "frontier": front, "random": rnd,
            "single": [{"asset": a, "ret": float(mu[i]), "vol": float(sd[i])} for i, a in enumerate(names)],
            "holdout": {"dates": [str(x.date()) for x in Rte.index], "optimised": eq(wt), "equal_weight": eq(np.ones(n) / n),
                        "optimised_perf": pr(wt), "equal_perf": pr(np.ones(n) / n), "weights_fit_on_train": wt.tolist(),
                        "train_end": str(Rtr.index[-1].date())}}
