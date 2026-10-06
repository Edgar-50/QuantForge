import math
from app.quant.pricing import black_scholes
from app.quant.risk import historical_var, max_drawdown, beta_alpha
from app.quant.portfolio import minimum_variance_portfolio, efficient_frontier
from app.quant.monte_carlo import monte_carlo_terminal_values
from app.quant.backtest import moving_average_backtest
from app.quant.volatility import ewma_volatility
from app.quant.regime import classify_regime

def test_black_scholes_call():
    r=black_scholes(100,100,1,.05,.2,"call")
    assert 10 < r["price"] < 11
    assert r["gamma"] > 0

def test_risk():
    r=[.01,-.02,.005,-.03,.015,.01,-.01]
    assert historical_var(r,.8) >= 0
    assert max_drawdown(r) <= 0

def test_beta():
    a=[.01,.02,-.01,.03,-.02,.01]
    m=[.008,.015,-.007,.02,-.012,.009]
    out=beta_alpha(a,m)
    assert "beta" in out and math.isfinite(out["beta"])

def test_portfolio():
    mu=[.08,.10]
    cov=[[.04,.01],[.01,.09]]
    r=minimum_variance_portfolio(mu,cov)
    assert math.isclose(sum(r["weights"]),1.0,abs_tol=1e-8)
    f=efficient_frontier(mu,cov,8)
    assert len(f["frontier"])==8

def test_monte_carlo_reproducible():
    a=monte_carlo_terminal_values(1000,.08,.2,simulations=1000,seed=7)
    b=monte_carlo_terminal_values(1000,.08,.2,simulations=1000,seed=7)
    assert a==b

def test_backtest():
    prices=[100+i*.3+(i%7)*.15 for i in range(80)]
    r=moving_average_backtest(prices,5,15,5)
    assert "equity_curve" in r

def test_ewma():
    r=ewma_volatility([.01,-.02,.012,.006,-.004])
    assert len(r["volatility_series"])==5

def test_regime():
    r=classify_regime([.001,.002,-.001,.003,.004,.001,.002,.003,-.001,.004,.003,.002])
    assert r["regime"] in {"risk_on","risk_off","sideways","high_volatility"}
