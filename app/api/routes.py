import json
from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Dict

from app.quant.risk import historical_var, conditional_var, max_drawdown, sharpe_ratio, sortino_ratio, beta_alpha
from app.quant.pricing import black_scholes
from app.quant.portfolio import minimum_variance_portfolio, efficient_frontier
from app.quant.advanced_portfolio import inverse_volatility_weights, risk_parity_weights, shrink_covariance
from app.quant.backtest import moving_average_backtest, momentum_backtest
from app.quant.monte_carlo import monte_carlo_terminal_values
from app.quant.regime import classify_regime
from app.quant.volatility import ewma_volatility
from app.quant.factors import factor_exposures
from app.quant.stress import scenario_matrix
from app.quant.walkforward import parameter_grid_search, walk_forward_ma
from app.quant.ml import logistic_direction_model
from app.quant.data_adapter import parse_price_csv
from app.db import SessionLocal
from app.models import SavedPortfolio, ResearchRun

router = APIRouter()

class ReturnsRequest(BaseModel):
    returns: List[float]
    confidence: float = Field(0.95, gt=0.5, lt=1.0)
    risk_free_rate: float = 0.0

class BetaRequest(BaseModel):
    asset_returns: List[float]
    market_returns: List[float]
    risk_free_rate: float = 0.0

class OptionRequest(BaseModel):
    spot: float = Field(..., gt=0)
    strike: float = Field(..., gt=0)
    time_to_maturity: float = Field(..., gt=0)
    risk_free_rate: float
    volatility: float = Field(..., gt=0)
    option_type: str = "call"

class PortfolioRequest(BaseModel):
    expected_returns: List[float]
    covariance: List[List[float]]
    points: int = Field(25, ge=5, le=100)

class CovarianceRequest(BaseModel):
    covariance: List[List[float]]
    shrinkage: float = Field(0.25, ge=0, le=1)

class BacktestRequest(BaseModel):
    prices: List[float]
    short_window: int = Field(5, ge=2)
    long_window: int = Field(20, ge=3)
    transaction_cost_bps: float = Field(5.0, ge=0)

class MomentumRequest(BaseModel):
    prices: List[float]
    lookback: int = Field(10, ge=2)
    transaction_cost_bps: float = Field(5.0, ge=0)

class MonteCarloRequest(BaseModel):
    initial_value: float = Field(100000, gt=0)
    annual_return: float
    annual_volatility: float = Field(..., ge=0)
    years: float = Field(1.0, gt=0)
    simulations: int = Field(5000, ge=100, le=100000)
    seed: int = 42

class SavePortfolioRequest(BaseModel):
    name: str
    weights: List[float]
    expected_return: float
    volatility: float

class VolatilityRequest(BaseModel):
    returns: List[float]
    lambda_: float = Field(0.94, gt=0, lt=1)

class FactorRequest(BaseModel):
    asset_returns: List[float]
    factors: List[List[float]]

class StressRequest(BaseModel):
    weights: List[float]
    scenarios: Dict[str, List[float]]
    portfolio_value: float = Field(100000, gt=0)

class WalkForwardRequest(BaseModel):
    prices: List[float]
    train_size: int = Field(100, ge=40)
    test_size: int = Field(30, ge=10)
    transaction_cost_bps: float = Field(5.0, ge=0)

class MLRequest(BaseModel):
    returns: List[float]
    lookback: int = Field(5, ge=3, le=30)

class CSVRequest(BaseModel):
    csv_text: str
    price_column: str = "close"

def store_run(kind, payload, result):
    with SessionLocal() as db:
        row = ResearchRun(kind=kind, payload_json=json.dumps(payload), result_json=json.dumps(result))
        db.add(row)
        db.commit()

@router.post("/risk")
def risk(req: ReturnsRequest):
    result = {
        "var": historical_var(req.returns, req.confidence),
        "cvar": conditional_var(req.returns, req.confidence),
        "max_drawdown": max_drawdown(req.returns),
        "sharpe": sharpe_ratio(req.returns, req.risk_free_rate),
        "sortino": sortino_ratio(req.returns, req.risk_free_rate),
    }
    store_run("risk", req.model_dump(), result)
    return result

@router.post("/capm")
def capm(req: BetaRequest):
    return beta_alpha(req.asset_returns, req.market_returns, req.risk_free_rate)

@router.post("/black-scholes")
def option_price(req: OptionRequest):
    result = black_scholes(req.spot, req.strike, req.time_to_maturity, req.risk_free_rate, req.volatility, req.option_type)
    store_run("black_scholes", req.model_dump(), result)
    return result

@router.post("/portfolio/min-variance")
def min_variance(req: PortfolioRequest):
    return minimum_variance_portfolio(req.expected_returns, req.covariance)

@router.post("/portfolio/frontier")
def frontier(req: PortfolioRequest):
    return efficient_frontier(req.expected_returns, req.covariance, req.points)

@router.post("/portfolio/inverse-volatility")
def inverse_vol(req: CovarianceRequest):
    return inverse_volatility_weights(req.covariance)

@router.post("/portfolio/risk-parity")
def risk_parity(req: CovarianceRequest):
    return risk_parity_weights(req.covariance)

@router.post("/portfolio/shrink-covariance")
def shrink(req: CovarianceRequest):
    return shrink_covariance(req.covariance, req.shrinkage)

@router.post("/backtest/ma")
def backtest(req: BacktestRequest):
    return moving_average_backtest(req.prices, req.short_window, req.long_window, req.transaction_cost_bps)

@router.post("/backtest/momentum")
def momentum(req: MomentumRequest):
    return momentum_backtest(req.prices, req.lookback, req.transaction_cost_bps)

@router.post("/walk-forward")
def walk_forward(req: WalkForwardRequest):
    return walk_forward_ma(req.prices, req.train_size, req.test_size, req.transaction_cost_bps)

@router.post("/grid-search")
def grid_search(req: BacktestRequest):
    return parameter_grid_search(req.prices, transaction_cost_bps=req.transaction_cost_bps)

@router.post("/monte-carlo")
def monte_carlo(req: MonteCarloRequest):
    result = monte_carlo_terminal_values(**req.model_dump())
    store_run("monte_carlo", req.model_dump(), result)
    return result

@router.post("/regime")
def regime(req: ReturnsRequest):
    return classify_regime(req.returns)

@router.post("/volatility/ewma")
def volatility(req: VolatilityRequest):
    return ewma_volatility(req.returns, req.lambda_)

@router.post("/factors")
def factors(req: FactorRequest):
    return factor_exposures(req.asset_returns, req.factors)

@router.post("/stress")
def stress(req: StressRequest):
    return scenario_matrix(req.weights, req.scenarios, req.portfolio_value)

@router.post("/ml/direction")
def ml_direction(req: MLRequest):
    return logistic_direction_model(req.returns, req.lookback)

@router.post("/data/csv")
def data_csv(req: CSVRequest):
    return parse_price_csv(req.csv_text, req.price_column)

@router.post("/portfolios")
def save_portfolio(req: SavePortfolioRequest):
    with SessionLocal() as db:
        row = SavedPortfolio(
            name=req.name,
            weights_json=json.dumps(req.weights),
            expected_return=req.expected_return,
            volatility=req.volatility
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return {"id": row.id, "name": row.name}

@router.get("/portfolios")
def list_portfolios():
    with SessionLocal() as db:
        rows = db.query(SavedPortfolio).order_by(SavedPortfolio.created_at.desc()).all()
        return [{
            "id": r.id,
            "name": r.name,
            "weights": json.loads(r.weights_json),
            "expected_return": r.expected_return,
            "volatility": r.volatility,
            "created_at": r.created_at.isoformat()
        } for r in rows]

@router.get("/research-runs")
def research_runs():
    with SessionLocal() as db:
        rows = db.query(ResearchRun).order_by(ResearchRun.created_at.desc()).limit(50).all()
        return [{"id": r.id, "kind": r.kind, "created_at": r.created_at.isoformat()} for r in rows]
