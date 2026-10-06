"""Vectorised strategy lab. Signals are computed on bar t and executed on bar t+1 (no look-ahead)."""
import numpy as np
import pandas as pd
from . import indicators as I

def sig_ma(c, s=20, l=50, **_): return (I.sma(c, s) > I.sma(c, l)).astype(float)
def sig_mom(c, n=63, **_): return (c.pct_change(n) > 0).astype(float)
def sig_rsi(c, n=14, lo=30, hi=55, **_):
    r = I.rsi(c, n); pos, out = 0.0, []
    for x in r.values:
        if x < lo: pos = 1.0
        elif x > hi: pos = 0.0
        out.append(pos)
    return pd.Series(out, c.index)
def sig_boll(c, n=20, k=2.0, **_):
    mid, up, lo = I.bollinger(c, n, k); pos, out = 0.0, []
    for x, m, l in zip(c.values, mid.values, lo.values):
        if x < l: pos = 1.0
        elif x > m: pos = 0.0
        out.append(pos)
    return pd.Series(out, c.index)
def sig_donchian(c, n=55, **_):
    hi, lo = c.rolling(n).max().shift(), c.rolling(n // 2).min().shift(); pos, out = 0.0, []
    for x, h, l in zip(c.values, hi.values, lo.values):
        if x > h: pos = 1.0
        elif x < l: pos = 0.0
        out.append(pos)
    return pd.Series(out, c.index)
def sig_voltarget(c, n=126, target=0.15, **_):
    r = c.pct_change(); vol = r.rolling(21).std() * np.sqrt(252)
    return ((c.pct_change(n) > 0) * (target / vol).clip(0, 1.5)).fillna(0.0)

STRATS = {
    "ma_cross": ("MA Crossover", sig_ma), "momentum": ("Time-series Momentum", sig_mom),
    "rsi_reversion": ("RSI Mean-Reversion", sig_rsi), "bollinger": ("Bollinger Reversion", sig_boll),
    "donchian": ("Donchian Breakout", sig_donchian), "vol_target": ("Vol-Targeted Trend", sig_voltarget),
}

def metrics(r):
    r = pd.Series(r).dropna()
    if len(r) < 3 or r.std() == 0:
        return dict(total_return=0, cagr=0, ann_vol=0, sharpe=0, sortino=0, max_drawdown=0, calmar=0, win_rate=0)
    eq = (1 + r).cumprod(); dd = (eq / eq.cummax() - 1).min(); yrs = len(r) / 252
    cagr = eq.iloc[-1] ** (1 / yrs) - 1; dn = r[r < 0]
    return dict(total_return=float(eq.iloc[-1] - 1), cagr=float(cagr), ann_vol=float(r.std() * np.sqrt(252)),
                sharpe=float(r.mean() / r.std() * np.sqrt(252)),
                sortino=float(r.mean() / np.sqrt((dn ** 2).mean()) * np.sqrt(252)) if len(dn) else None,
                max_drawdown=float(dd), calmar=float(cagr / abs(dd)) if dd < 0 else None,
                win_rate=float((r[r != 0] > 0).mean()) if (r != 0).any() else 0.0)

def run(df, name, cost_bps=5.0, **params):
    c = df["close"]; sig = STRATS[name][1](c, **params).fillna(0.0)
    pos = sig.shift(1).fillna(0.0)
    r = c.pct_change().fillna(0.0)
    turn = pos.diff().abs().fillna(0.0)
    sr = pos * r - turn * cost_bps / 1e4
    m = metrics(sr.iloc[1:]); m["exposure"] = float((pos > 0).mean()); m["trades"] = int((turn > 0.5).sum())
    m["turnover_per_year"] = float(turn.sum() / (len(turn) / 252))
    return sr, pos, m

def compare(df, names, cost_bps=5.0, params=None):
    params = params or {}
    c = df["close"]; out = {"dates": [str(x.date()) for x in df.index], "series": {}, "metrics": {}, "positions": {}}
    bh = c.pct_change().fillna(0.0)
    out["series"]["buy_hold"] = ((1 + bh).cumprod()).tolist(); out["metrics"]["buy_hold"] = metrics(bh.iloc[1:])
    out["metrics"]["buy_hold"].update(exposure=1.0, trades=0, turnover_per_year=0.0)
    for n in names:
        sr, pos, m = run(df, n, cost_bps, **params.get(n, {}))
        out["series"][n] = (1 + sr).cumprod().tolist(); out["metrics"][n] = m; out["positions"][n] = pos.tolist()
    out["labels"] = {k: v[0] for k, v in STRATS.items()}; out["labels"]["buy_hold"] = "Buy & Hold"
    return out

def ma_surface(df, shorts=(5, 8, 10, 15, 20, 30), longs=(30, 50, 75, 100, 150, 200), cost_bps=5.0, split=0.6):
    """Sharpe surface on in-sample vs out-of-sample halves -> exposes parameter overfitting."""
    c = df["close"]; cut = int(len(c) * split); ins, oos = df.iloc[:cut], df.iloc[cut:]
    def grid(d):
        Z = []
        for s in shorts:
            row = []
            for l in longs:
                row.append(None if s >= l or len(d) < l + 30 else round(run(d, "ma_cross", cost_bps, s=s, l=l)[2]["sharpe"], 3))
            Z.append(row)
        return Z
    zi, zo = grid(ins), grid(oos)
    best = max(((zi[i][j], i, j) for i in range(len(shorts)) for j in range(len(longs)) if zi[i][j] is not None), default=None)
    sel = None
    if best and zo[best[1]][best[2]] is not None:
        sel = {"short": shorts[best[1]], "long": longs[best[2]], "in_sample_sharpe": best[0], "out_of_sample_sharpe": zo[best[1]][best[2]]}
    return {"shorts": list(shorts), "longs": list(longs), "in_sample": zi, "out_of_sample": zo, "best_in_sample": sel,
            "split_date": str(df.index[cut].date())}
