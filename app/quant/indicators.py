"""Vectorised technical indicators (pandas)."""
import numpy as np
import pandas as pd


def sma(s, n): return s.rolling(n).mean()
def ema(s, n): return s.ewm(span=n, adjust=False).mean()


def rsi(close, n=14):
    d = close.diff()
    up, dn = d.clip(lower=0), -d.clip(upper=0)
    rs = up.ewm(alpha=1 / n, adjust=False).mean() / dn.ewm(alpha=1 / n, adjust=False).mean().replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100.0).where(close.notna())


def macd(close, fast=12, slow=26, sig=9):
    line = ema(close, fast) - ema(close, slow)
    signal = ema(line, sig)
    return line, signal, line - signal


def bollinger(close, n=20, k=2.0):
    mid, sd = sma(close, n), close.rolling(n).std()
    return mid, mid + k * sd, mid - k * sd


def atr(df, n=14):
    pc = df["close"].shift()
    tr = pd.concat([df["high"] - df["low"], (df["high"] - pc).abs(), (df["low"] - pc).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False).mean()


def stochastic(df, n=14, d=3):
    lo, hi = df["low"].rolling(n).min(), df["high"].rolling(n).max()
    k = 100 * (df["close"] - lo) / (hi - lo).replace(0, np.nan)
    return k, k.rolling(d).mean()


def adx(df, n=14):
    up, dn = df["high"].diff(), -df["low"].diff()
    pdm = np.where((up > dn) & (up > 0), up, 0.0); mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    a = atr(df, n)
    pdi = 100 * pd.Series(pdm, df.index).ewm(alpha=1 / n, adjust=False).mean() / a
    mdi = 100 * pd.Series(mdm, df.index).ewm(alpha=1 / n, adjust=False).mean() / a
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=1 / n, adjust=False).mean()


def obv(df):
    return (np.sign(df["close"].diff().fillna(0)) * df["volume"]).cumsum()


def snapshot(df):
    """Latest indicator readings + human-readable bias for the terminal view."""
    c = df["close"]
    r = rsi(c).iloc[-1]; m, ms, mh = macd(c); mid, up, lo = bollinger(c)
    k, d = stochastic(df); a = atr(df).iloc[-1]; ad = adx(df).iloc[-1]
    pb = float((c.iloc[-1] - lo.iloc[-1]) / (up.iloc[-1] - lo.iloc[-1]))
    s20, s50 = sma(c, 20).iloc[-1], sma(c, 50).iloc[-1]
    s200 = sma(c, 200).iloc[-1] if len(c) >= 200 else np.nan
    votes = [
        ("RSI(14)", float(r), "bull" if r < 35 else "bear" if r > 70 else "neutral"),
        ("MACD hist", float(mh.iloc[-1]), "bull" if mh.iloc[-1] > 0 else "bear"),
        ("Bollinger %B", pb, "bull" if pb < 0.15 else "bear" if pb > 0.95 else "neutral"),
        ("Stoch %K", float(k.iloc[-1]), "bull" if k.iloc[-1] < 20 else "bear" if k.iloc[-1] > 80 else "neutral"),
        ("Price vs SMA50", float(c.iloc[-1] / s50 - 1), "bull" if c.iloc[-1] > s50 else "bear"),
        ("SMA20 vs SMA50", float(s20 / s50 - 1), "bull" if s20 > s50 else "bear"),
    ]
    if not np.isnan(s200):
        votes.append(("Price vs SMA200", float(c.iloc[-1] / s200 - 1), "bull" if c.iloc[-1] > s200 else "bear"))
    score = sum(1 if v[2] == "bull" else -1 if v[2] == "bear" else 0 for v in votes) / len(votes)
    return {
        "readings": [{"name": n, "value": v, "bias": b} for n, v, b in votes],
        "atr": float(a), "atr_pct": float(a / c.iloc[-1]), "adx": float(ad),
        "trend_strength": "strong" if ad > 25 else "weak",
        "technical_score": float(score),
        "bias": "bullish" if score > .2 else "bearish" if score < -.2 else "neutral",
    }


def chart_series(df):
    c = df["close"]
    m, ms, mh = macd(c); mid, up, lo = bollinger(c)
    f = lambda s: [None if not np.isfinite(x) else round(float(x), 6) for x in s]
    return {
        "sma20": f(sma(c, 20)), "sma50": f(sma(c, 50)), "sma200": f(sma(c, 200)),
        "bb_up": f(up), "bb_lo": f(lo), "rsi": f(rsi(c)),
        "macd": f(m), "macd_signal": f(ms), "macd_hist": f(mh),
    }
