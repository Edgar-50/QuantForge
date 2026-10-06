import json, math
import numpy as np, pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.quant import options_pro as O, portfolio_pro as P, risk_pro as RK, strategies as S, indicators as I
from app.quant.data_provider import get_ohlcv, returns_frame, simulate
from app.quant.garch import fit_garch
from app.quant.hmm import regime_analysis
from app.quant.ml_engine import run_forecast, build_features
from app.api.auth import make_token, read_token

@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:      # runs lifespan -> init_db
        yield c


def strict(resp):
    """Parse as strict JSON (rejects NaN/Infinity) -> the browser would choke on those."""
    assert resp.status_code == 200, resp.text[:300]
    return json.loads(resp.text, parse_constant=lambda c: (_ for _ in ()).throw(AssertionError(f"non-finite {c}")))


def synth(seed, planted, n=1000):
    rng = np.random.default_rng(seed); r = rng.normal(0, .012, n)
    if planted:
        tr = np.zeros(n)
        for i in range(1, n): tr[i] = .97 * tr[i - 1] + rng.normal(0, .0009)
        r = r + tr
    px = 100 * np.cumprod(1 + r); idx = pd.bdate_range(end="2026-10-06", periods=n)
    return pd.DataFrame({"open": np.r_[px[0], px[:-1]], "high": px * (1 + abs(rng.normal(0, .004, n))), "low": px * (1 - abs(rng.normal(0, .004, n))),
                         "close": px, "volume": rng.integers(1_000_000, 2_000_000, n).astype(float)}, index=idx)


# ---------- data + indicators ----------
def test_simulator_deterministic_and_correlated():
    a, b = simulate("AAPL", 300), simulate("AAPL", 300)
    assert a.equals(b) and (a.high >= a.low).all()
    R, _, _ = returns_frame(["SPY", "QQQ"], 400, "sim")
    assert R.corr().iloc[0, 1] > 0.5

def test_rsi_bounds_and_no_lookahead_features():
    df = simulate("MSFT", 400); r = I.rsi(df.close).dropna()
    assert ((r >= 0) & (r <= 100)).all()
    f1 = build_features(df); f2 = build_features(df.iloc[:-30])
    common = f2.dropna().index
    pd.testing.assert_frame_equal(f1.loc[common], f2.loc[common])      # features at t unchanged by future data


# ---------- models ----------
def test_garch_stationary():
    g = fit_garch(simulate("NVDA", 756).close.pct_change().dropna().values)
    assert 0 < g["persistence"] < 1 and g["long_run_vol_ann"] > 0 and len(g["forecast_vol_ann"]) == 21

def test_hmm_orders_states_by_vol():
    h = regime_analysis(simulate("SPY", 756).close.pct_change().dropna().values)
    v = [s["ann_vol"] for s in h["states"]]
    assert v == sorted(v) and abs(sum(s["occupancy"] for s in h["states"]) - 1) < 1e-9
    assert np.allclose(np.array(h["transition"]).sum(1), 1)

def test_ml_detects_planted_signal_and_rejects_noise():
    planted = [run_forecast(synth(s, True))["signal"]["verdict"] for s in (100, 101, 103)]
    noise = [run_forecast(synth(s + 50, False))["signal"]["verdict"] for s in range(3)]
    assert sum(v != "NO_EDGE" for v in planted) >= 2            # power
    assert all(v != "EDGE_DETECTED" for v in noise)             # no strong false positives

def test_ml_purge_prevents_leakage():
    r = run_forecast(synth(1, False), horizon=5)
    assert 0.35 < r["validation"]["auc"] < 0.65                 # pure noise must not score high
    assert len(r["validation"]["folds"]) == 5 and 0 <= r["signal"]["prob_up"] <= 1


# ---------- portfolio / risk / options ----------
@pytest.mark.parametrize("m", ["max_sharpe", "min_vol", "risk_parity", "hrp", "equal"])
def test_portfolio_methods_valid(m):
    R, _, _ = returns_frame(["AAPL", "MSFT", "TLT", "GLD", "XOM"], 400, "sim")
    o = P.optimize(R, m, cap=0.5)
    w = np.array(o["weights"])
    assert abs(w.sum() - 1) < 1e-6 and (w >= -1e-9).all() and (w <= 0.5 + 1e-6).all() or m in ("hrp", "equal")
    assert abs(sum(o["risk_contribution"]) - 1) < 1e-6

def test_risk_backtest_and_ordering():
    R, _, _ = returns_frame(["SPY"], 756, "sim"); a = RK.analyze(R["SPY"])
    assert a["cvar"]["historical"] >= a["var"]["historical"] > 0 and a["ratios"]["max_drawdown"] <= 0
    assert 0 <= a["var_backtest"]["kupiec_p"] <= 1

def test_option_parity_iv_roundtrip_american():
    S0, K, T, r, s = 100, 100, 1, .05, .3
    c, p = O.bs_price(S0, K, T, r, s, "call"), O.bs_price(S0, K, T, r, s, "put")
    assert abs((c - p) - (S0 - K * math.exp(-r * T))) < 1e-9
    assert abs(O.implied_vol(c, S0, K, T, r, "call") - s) < 1e-6
    assert O.crr(S0, K, T, r, s, "put", True) >= O.crr(S0, K, T, r, s, "put", False)
    assert abs(O.crr(S0, K, T, r, s, "call", False, 500) - c) < 0.02

def test_strategies_no_lookahead_and_costs():
    df = simulate("AAPL", 500)
    _, pos, m0 = S.run(df, "ma_cross", 0.0); _, _, m1 = S.run(df, "ma_cross", 50.0)
    assert m1["total_return"] <= m0["total_return"]
    assert pos.iloc[0] == 0                                     # first bar can never hold a position


# ---------- API (strict JSON, every endpoint) ----------
def test_api_market_analysis_forecast(client):
    m = strict(client.get("/api/v2/market/AAPL?days=200&source=sim")); assert m["source"] == "SIM" and len(m["close"]) == 200
    a = strict(client.get("/api/v2/analysis/NVDA?source=sim")); assert a["regime"]["current"] in ("Calm", "Neutral", "Stress")
    f = strict(client.get("/api/v2/forecast/MSFT?horizon=5&source=sim"))
    assert f["signal"]["verdict"] in ("NO_EDGE", "WEAK_EDGE", "EDGE_DETECTED") and len(f["cone"]["median"]) == 30

def test_api_other_endpoints(client):
    assert len(strict(client.get("/api/v2/screener?source=sim"))) == 15
    c = strict(client.post("/api/v2/strategies/compare", json={"ticker": "SPY", "strategies": ["ma_cross", "bollinger"], "source": "sim"}))
    assert "buy_hold" in c["series"]
    assert strict(client.post("/api/v2/strategies/surface", json={"ticker": "SPY", "source": "sim"}))["in_sample"]
    o = strict(client.post("/api/v2/portfolio/optimize", json={"tickers": ["AAPL", "SPY", "TLT"], "method": "hrp", "source": "sim"}))
    assert len(o["holdout"]["optimised"]) > 50
    assert strict(client.post("/api/v2/risk/analyze", json={"tickers": ["AAPL", "TLT"], "source": "sim"}))["var"]
    assert strict(client.post("/api/v2/simulate", json={"tickers": ["SPY"], "source": "sim", "sims": 300}))["bands"]["50"]
    assert strict(client.post("/api/v2/stress", json={"tickers": ["AAPL", "TLT"], "source": "sim"}))["scenarios"]["2008 GFC"]
    op = strict(client.post("/api/v2/options/analyze", json={"spot": 100, "strike": 100, "time_to_maturity": .5, "volatility": .25, "market_price": 7, "preset": "iron_condor"}))
    assert op["implied_vol"] > 0

def test_api_validation_errors(client):
    assert client.post("/api/v2/strategies/compare", json={"ticker": "SPY", "strategies": ["nope"]}).status_code == 422
    assert client.post("/api/v2/portfolio/optimize", json={"tickers": ["AAPL"]}).status_code == 422
    assert client.post("/api/v2/options/analyze", json={"spot": 100, "strike": 100, "time_to_maturity": 1, "volatility": .2, "option_type": "x"}).status_code == 422

def test_legacy_sortino_no_inf_crash(client):
    r = client.post("/api/risk", json={"returns": [.01, .02, .005, .01, .03, .02]})
    assert r.status_code == 200 and r.json()["sortino"] is None

def test_token_roundtrip_and_tamper():
    t = make_token("alice"); assert read_token(t) == "alice"
    assert read_token(t[:-2] + "00") is None and read_token(make_token("a", ttl=-5)) is None
