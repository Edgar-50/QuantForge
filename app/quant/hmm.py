"""Diagonal-Gaussian Hidden Markov Model (EM / Baum-Welch in log space) + Viterbi decoding.
Used for market-regime detection on [return, realised-vol] observations."""
import numpy as np


def _logN(X, mu, var):  # (T,K)
    return -0.5 * (np.log(2 * np.pi * var).sum(1)[None] + (((X[:, None, :] - mu[None]) ** 2) / var[None]).sum(2))


def _lse(a, axis):
    m = a.max(axis=axis, keepdims=True)
    return (m + np.log(np.exp(a - m).sum(axis=axis, keepdims=True))).squeeze(axis)


def fit_hmm(X, K=3, iters=60, seed=0):
    X = np.asarray(X, float); T, D = X.shape
    rng = np.random.default_rng(seed)
    order = np.argsort(X[:, 1]); chunks = np.array_split(order, K)       # init by vol terciles
    mu = np.array([X[c].mean(0) for c in chunks]); var = np.array([X[c].var(0) + 1e-8 for c in chunks])
    A = np.full((K, K), .05 / (K - 1)); np.fill_diagonal(A, .95); pi = np.ones(K) / K
    prev = -np.inf
    for _ in range(iters):
        lb = _logN(X, mu, var); lA = np.log(A)
        la = np.empty((T, K)); la[0] = np.log(pi) + lb[0]
        for t in range(1, T): la[t] = lb[t] + _lse(la[t - 1][:, None] + lA, 0)
        lbeta = np.zeros((T, K))
        for t in range(T - 2, -1, -1): lbeta[t] = _lse(lA + (lb[t + 1] + lbeta[t + 1])[None], 1)
        ll = _lse(la[-1], 0)
        g = np.exp(la + lbeta - ll)
        xi = np.exp(la[:-1, :, None] + lA[None] + (lb[1:] + lbeta[1:])[:, None, :] - ll).sum(0)
        pi = (g[0] + 1e-6) / (g[0] + 1e-6).sum(); A = (xi + 1e-6) / (xi + 1e-6).sum(1, keepdims=True)
        w = g.sum(0) + 1e-9
        mu = (g.T @ X) / w[:, None]
        var = np.maximum((g.T @ (X ** 2)) / w[:, None] - mu ** 2, 1e-8)
        if abs(ll - prev) < 1e-4: break
        prev = ll
    # Viterbi
    lb = _logN(X, mu, var); lA = np.log(A + 1e-300)
    d = np.empty((T, K)); bp = np.zeros((T, K), int); d[0] = np.log(pi + 1e-300) + lb[0]
    for t in range(1, T):
        sc = d[t - 1][:, None] + lA; bp[t] = sc.argmax(0); d[t] = sc.max(0) + lb[t]
    path = np.empty(T, int); path[-1] = d[-1].argmax()
    for t in range(T - 2, -1, -1): path[t] = bp[t + 1, path[t + 1]]
    post = np.exp(la + lbeta - ll)
    return {"mu": mu, "var": var, "A": A, "pi": pi, "path": path, "posterior": post, "loglik": float(ll)}


def regime_analysis(returns, window=10):
    r = np.asarray(returns, float)
    if len(r) < 120: raise ValueError("need >=120 returns")
    rv = np.array([r[max(0, i - window + 1):i + 1].std() for i in range(len(r))]) * np.sqrt(252)
    X = np.column_stack([r * 100, rv * 100])[window:]
    m = fit_hmm(X, 3)
    order = np.argsort(m["mu"][:, 1])                 # low-vol, mid, high-vol
    names = ["Calm", "Neutral", "Stress"]
    rank = {int(s): i for i, s in enumerate(order)}
    path = np.array([rank[int(s)] for s in m["path"]])
    A = m["A"][np.ix_(order, order)]
    stats = []
    for i, s in enumerate(order):
        mask = path == i
        stats.append({"name": names[i], "mean_daily_return": float(m["mu"][s, 0] / 100), "ann_vol": float(m["mu"][s, 1] / 100),
                      "occupancy": float(mask.mean()), "expected_duration_days": float(1 / max(1 - A[i, i], 1e-6))})
    cur = int(path[-1])
    nxt = A[cur]
    return {"states": stats, "current": names[cur], "current_idx": cur, "transition": A.tolist(),
            "next_state_probs": {names[i]: float(nxt[i]) for i in range(3)},
            "path": path.tolist(), "offset": window, "loglik": m["loglik"]}
