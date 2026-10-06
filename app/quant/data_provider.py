"""Market data layer.

Provider chain: yfinance (if installed) -> Stooq CSV -> deterministic simulator.
The simulator produces correlated, vol-clustered, regime-switching OHLCV so every
feature works offline. Every payload carries a `source` field so the UI can never
silently present simulated data as real.
"""
from __future__ import annotations
import hashlib, io, time, urllib.request
import numpy as np
import pandas as pd

UNIVERSE = {
    "AAPL": ("Apple", "Tech", 190, 0.28), "MSFT": ("Microsoft", "Tech", 410, 0.25),
    "NVDA": ("NVIDIA", "Semis", 880, 0.50), "GOOGL": ("Alphabet", "Tech", 165, 0.29),
    "AMZN": ("Amazon", "Consumer", 185, 0.32), "META": ("Meta", "Tech", 500, 0.38),
    "TSLA": ("Tesla", "Auto", 240, 0.58), "JPM": ("JPMorgan", "Financials", 195, 0.22),
    "XOM": ("Exxon", "Energy", 115, 0.24), "JNJ": ("J&J", "Health", 155, 0.15),
    "SPY": ("S&P 500 ETF", "Index", 520, 0.15), "QQQ": ("Nasdaq 100 ETF", "Index", 440, 0.20),
    "GLD": ("Gold ETF", "Commodity", 215, 0.14), "TLT": ("20Y Treasury ETF", "Rates", 92, 0.16),
    "BTC-USD": ("Bitcoin", "Crypto", 64000, 0.55),
}
MARKET_BETA = {"SPY": 1.0, "QQQ": 1.15, "GLD": 0.05, "TLT": -0.25, "BTC-USD": 0.6, "XOM": 0.7, "JNJ": 0.45}
_SIM_LEN = 1800
_CACHE: dict = {}
_FAIL: dict = {}
TTL = 900


def _seed(key: str) -> int:
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16)


def _regime_vol_path(rng, n, base_vol):
    """Markov-switching vol multiplier (calm / normal / stressed) + GARCH-like clustering."""
    P = np.array([[.985, .014, .001], [.02, .968, .012], [.02, .08, .90]])
    mult = np.array([.7, 1.0, 2.1])
    s, states = 1, np.empty(n, int)
    for i in range(n):
        s = rng.choice(3, p=P[s]); states[i] = s
    return base_vol / np.sqrt(252) * mult[states], states


def simulate(ticker: str, days: int = 756) -> pd.DataFrame:
    t = ticker.upper()
    meta = UNIVERSE.get(t, (t, "Other", 100 + _seed(t) % 400, 0.20 + (_seed(t + "v") % 30) / 100))
    base_px, ann_vol = float(meta[2]), float(meta[3])
    # shared market factor (same seed for all tickers -> realistic correlation)
    mrng = np.random.default_rng(20240607)
    mvol, mstates = _regime_vol_path(mrng, _SIM_LEN, 0.16)
    mkt = mrng.standard_t(6, _SIM_LEN) / np.sqrt(1.5) * mvol + 0.09 / 252
    rng = np.random.default_rng(_seed(t))
    beta = MARKET_BETA.get(t, 0.7 + (_seed(t + "b") % 60) / 100)
    idio_vol = max(ann_vol ** 2 - (beta * 0.16) ** 2, 0.01) ** 0.5
    ivol, _ = _regime_vol_path(rng, _SIM_LEN, idio_vol)
    idio = rng.standard_t(5, _SIM_LEN) / np.sqrt(5 / 3) * ivol
    r = beta * mkt + idio + (0.04 + (_seed(t + "d") % 20) / 100) / 252
    # weak, realistic serial structure: short-term momentum + mean reversion at 1d
    for i in range(2, _SIM_LEN):
        r[i] += 0.04 * r[i - 1] * (1 if i % 400 < 250 else -1) + 0.02 * r[i - 2]
    px = base_px * np.exp(np.cumsum(r - r.mean() * 0.0))
    px = px / px[-1] * base_px
    gap = rng.normal(0, ann_vol / np.sqrt(252) * 0.25, _SIM_LEN)
    op = np.r_[px[0], px[:-1]] * (1 + gap)
    rng_hl = np.abs(rng.normal(0, ann_vol / np.sqrt(252) * 0.55, _SIM_LEN))
    hi = np.maximum(op, px) * (1 + rng_hl); lo = np.minimum(op, px) * (1 - rng_hl)
    vol = np.exp(rng.normal(np.log(2e7 if base_px < 1000 else 3e4), 0.25, _SIM_LEN)) * (1 + 18 * np.abs(r))
    idx = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=_SIM_LEN)
    df = pd.DataFrame({"open": op, "high": hi, "low": lo, "close": px, "volume": vol.astype(np.int64)}, index=idx)
    return df.iloc[-days:]


def _yf(ticker, days):
    import yfinance as yf  # optional dependency
    df = yf.download(ticker, period=f"{max(int(days / 252 * 365) + 30, 60)}d", progress=False, auto_adjust=True)
    if df is None or df.empty:
        raise ValueError("empty")
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]].dropna()
    return df.tail(days)


def _stooq(ticker, days):
    sym = ticker.lower() + (".us" if "-" not in ticker and "." not in ticker else "")
    with urllib.request.urlopen(f"https://stooq.com/q/d/l/?s={sym}&i=d", timeout=4) as r:
        txt = r.read().decode()
    df = pd.read_csv(io.StringIO(txt), parse_dates=["Date"], index_col="Date").rename(columns=str.lower)
    if df.empty or "close" not in df:
        raise ValueError("empty")
    return df[["open", "high", "low", "close", "volume"]].dropna().tail(days)


def get_ohlcv(ticker: str, days: int = 756, source: str = "auto"):
    """Return (DataFrame, source_label). source in {auto, live, sim}."""
    t = ticker.upper().strip()
    key = (t, days, source)
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < TTL:
        return hit[1], hit[2]
    df, label = None, "SIM"
    if source != "sim":
        now = time.time()
        for name, fn in (("YFINANCE", _yf), ("STOOQ", _stooq)):
            if now - _FAIL.get(name, 0) < 600 or now - _FAIL.get((name, t), 0) < 600:
                continue
            try:
                df, label = fn(t, days), name
                if len(df) < 60:
                    raise ValueError("too short")
                break
            except (ImportError, OSError):          # provider unavailable / offline -> block provider
                _FAIL[name] = now; df = None
            except Exception:                        # bad symbol etc -> block only this ticker
                _FAIL[(name, t)] = now; df = None
    if df is None:
        df, label = simulate(t, days), "SIM"
    df = df[~df.index.duplicated()].astype(float)
    _CACHE[key] = (time.time(), df, label)
    return df, label


def returns_frame(tickers, days=504, source="auto"):
    cols, labels = {}, {}
    for t in tickers:
        df, lab = get_ohlcv(t, days + 5, source)
        cols[t] = df["close"]; labels[t] = lab
    px = pd.DataFrame(cols).dropna()
    return px.pct_change().dropna().tail(days), px.tail(days + 1), labels


def universe_meta():
    return [{"ticker": k, "name": v[0], "sector": v[1]} for k, v in UNIVERSE.items()]
