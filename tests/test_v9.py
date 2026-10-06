from app.quant.advanced_portfolio import inverse_volatility_weights, risk_parity_weights, shrink_covariance
from app.quant.factors import factor_exposures
from app.quant.stress import scenario_matrix
from app.quant.walkforward import parameter_grid_search, walk_forward_ma
from app.quant.ml import logistic_direction_model
from app.quant.data_adapter import parse_price_csv

def test_inverse_volatility_weights_sum():
    cov=[[.04,.01],[.01,.09]]
    out=inverse_volatility_weights(cov)
    assert abs(sum(out["weights"])-1)<1e-10

def test_risk_parity_weights_sum():
    cov=[[.04,.01],[.01,.09]]
    out=risk_parity_weights(cov)
    assert abs(sum(out["weights"])-1)<1e-10

def test_shrink_covariance():
    out=shrink_covariance([[.04,.02],[.02,.09]],.5)
    assert out["covariance"][0][1] == .01

def test_factor_exposures():
    f=[[.01,.002],[.02,.001],[-.01,.003],[.03,-.002],[-.02,.004],[.015,.001]]
    y=[.012,.018,-.009,.028,-.017,.014]
    out=factor_exposures(y,f)
    assert len(out["factor_betas"])==2

def test_stress_matrix():
    out=scenario_matrix([.5,.5],{"shock":[-.1,.02]},100000)
    assert "shock" in out
    assert out["shock"]["stressed_value"] < 100000

def test_grid_search():
    prices=[100+i*.2+(i%9)*.1 for i in range(150)]
    out=parameter_grid_search(prices)
    assert out["best"] is not None

def test_walk_forward():
    prices=[100+i*.15+(i%11)*.12 for i in range(260)]
    out=walk_forward_ma(prices,100,30)
    assert len(out["windows"]) >= 1

def test_ml_model():
    r=[((i%7)-3)*.002 + (0.001 if i%2==0 else -0.0005) for i in range(80)]
    out=logistic_direction_model(r,5)
    assert 0 <= out["accuracy"] <= 1
    assert 0 <= out["latest_probability_up"] <= 1

def test_csv_adapter():
    out=parse_price_csv("date,close\n2026-01-01,100\n2026-01-02,101\n")
    assert out["prices"] == [100.0,101.0]
