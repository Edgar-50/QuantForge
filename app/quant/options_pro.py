import math
import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm
from .pricing import black_scholes

def bs_price(S, K, T, r, sig, kind="call", q=0.0):
    if T <= 0: return max(S - K, 0.0) if kind == "call" else max(K - S, 0.0)
    d1 = (math.log(S / K) + (r - q + .5 * sig ** 2) * T) / (sig * math.sqrt(T)); d2 = d1 - sig * math.sqrt(T)
    if kind == "call": return S * math.exp(-q * T) * norm.cdf(d1) - K * math.exp(-r * T) * norm.cdf(d2)
    return K * math.exp(-r * T) * norm.cdf(-d2) - S * math.exp(-q * T) * norm.cdf(-d1)

def implied_vol(price, S, K, T, r, kind="call"):
    intrinsic = max(S - K * math.exp(-r * T), 0) if kind == "call" else max(K * math.exp(-r * T) - S, 0)
    if price <= intrinsic + 1e-10: raise ValueError("price at/below intrinsic value: no implied vol")
    return float(brentq(lambda s: bs_price(S, K, T, r, s, kind) - price, 1e-4, 8.0, xtol=1e-10))

def crr(S, K, T, r, sig, kind="call", american=True, steps=300, q=0.0):
    dt = T / steps; u = math.exp(sig * math.sqrt(dt)); d = 1 / u; p = (math.exp((r - q) * dt) - d) / (u - d); disc = math.exp(-r * dt)
    j = np.arange(steps + 1); ST = S * u ** (steps - j) * d ** j
    V = np.maximum(ST - K, 0) if kind == "call" else np.maximum(K - ST, 0)
    for i in range(steps - 1, -1, -1):
        V = disc * (p * V[:-1] + (1 - p) * V[1:])
        if american:
            jj = np.arange(i + 1); Si = S * u ** (i - jj) * d ** jj
            V = np.maximum(V, (Si - K) if kind == "call" else (K - Si))
    return float(V[0])

PRESETS = {
    "long_call": [("call", 1, 1.0)], "long_put": [("put", 1, 1.0)], "covered_call": [("stock", 1, 0), ("call", -1, 1.05)],
    "bull_call_spread": [("call", 1, 1.0), ("call", -1, 1.10)], "bear_put_spread": [("put", 1, 1.0), ("put", -1, 0.90)],
    "long_straddle": [("call", 1, 1.0), ("put", 1, 1.0)], "long_strangle": [("call", 1, 1.05), ("put", 1, 0.95)],
    "iron_condor": [("put", 1, 0.88), ("put", -1, 0.94), ("call", -1, 1.06), ("call", 1, 1.12)],
    "butterfly": [("call", 1, 0.95), ("call", -2, 1.0), ("call", 1, 1.05)],
}

def analyze(S, K, T, r, sig, kind="call", q=0.0, market_price=None, preset="long_call"):
    base = black_scholes(S, K, T, r, sig, kind)
    amer = crr(S, K, T, r, sig, kind, True, q=q); eur = crr(S, K, T, r, sig, kind, False, q=q)
    spots = np.linspace(S * 0.6, S * 1.4, 81)
    curves = {"spots": spots.tolist(), "delta": [], "gamma": [], "vega": [], "theta": [], "price": [], "intrinsic": []}
    for s in spots:
        g = black_scholes(float(s), K, T, r, sig, kind)
        curves["delta"].append(g["delta"]); curves["gamma"].append(g["gamma"]); curves["vega"].append(g["vega_per_1pct"])
        curves["theta"].append(g["theta_per_day"]); curves["price"].append(g["price"]); curves["intrinsic"].append(max(s - K, 0) if kind == "call" else max(K - s, 0))
    Ts = [max(T * f, 1 / 365) for f in (1.0, .66, .33, .1)]
    decay = {f"{t * 365:.0f}d": [bs_price(float(s), K, t, r, sig, kind) for s in spots] for t in Ts}
    sig_axis = np.linspace(max(sig * .4, .05), sig * 1.8, 15); k_axis = np.linspace(S * .7, S * 1.3, 15)
    surf = [[bs_price(S, float(k), T, r, float(v), kind) for k in k_axis] for v in sig_axis]
    out = {"bs": base, "american_crr": amer, "european_crr": eur, "early_exercise_premium": amer - eur,
           "curves": curves, "decay": decay, "surface": {"vol": sig_axis.tolist(), "strike": k_axis.tolist(), "price": surf}}
    if market_price:
        try: iv = implied_vol(market_price, S, K, T, r, kind); out["implied_vol"] = iv; out["iv_vs_input"] = iv - sig
        except ValueError as e: out["implied_vol_error"] = str(e)
    legs = PRESETS.get(preset, PRESETS["long_call"]); pay = np.zeros_like(spots); now = np.zeros_like(spots); cost = 0.0; rows = []
    for typ, qty, mny in legs:
        k = S * mny
        if typ == "stock":
            pay += qty * (spots - S); now += qty * (spots - S); rows.append({"leg": "Stock", "qty": qty, "strike": None, "premium": 0.0}); continue
        prem = bs_price(S, k, T, r, sig, typ); cost += qty * prem
        pay += qty * (np.maximum(spots - k, 0) if typ == "call" else np.maximum(k - spots, 0))
        now += qty * np.array([bs_price(float(s), k, T, r, sig, typ) for s in spots]); rows.append({"leg": typ, "qty": qty, "strike": k, "premium": prem})
    pnl = pay - cost; pnl_now = now - cost
    be = [float(spots[i - 1] + (0 - pnl[i - 1]) * (spots[i] - spots[i - 1]) / (pnl[i] - pnl[i - 1])) for i in range(1, len(spots)) if pnl[i - 1] * pnl[i] < 0]
    out["strategy"] = {"preset": preset, "legs": rows, "net_debit": float(cost), "spots": spots.tolist(), "pnl_expiry": pnl.tolist(), "pnl_today": pnl_now.tolist(),
                       "max_profit": float(pnl.max()), "max_loss": float(pnl.min()), "breakevens": be}
    return out
