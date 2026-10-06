"""v10 'pro' API: market data, analytics, AI forecasting, strategy lab, portfolio, risk, options, simulation."""
import json, math
from typing import List, Optional
import numpy as np
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.quant import indicators as I, strategies as S, portfolio_pro as P, risk_pro as RK, options_pro as O, screener as SC
from app.quant.data_provider import get_ohlcv, returns_frame, universe_meta
from app.quant.garch import fit_garch
from app.quant.hmm import regime_analysis
from app.quant.ml_engine import cached_forecast
from app.db import SessionLocal
from app.models import ResearchRun

router = APIRouter()


def clean(o):
    """Recursively make a payload strict-JSON safe (NaN/inf -> null, numpy -> python)."""
    if isinstance(o, dict): return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)): return float(o) if math.isfinite(o) else None
    if isinstance(o, np.integer): return int(o)
    if isinstance(o, np.bool_): return bool(o)
    if isinstance(o, np.ndarray): return clean(o.tolist())
    return o


def _log(kind, payload, result):
    try:
        with SessionLocal() as db:
            db.add(ResearchRun(kind=kind, payload_json=json.dumps(payload), result_json=json.dumps(clean(result))[:200_000])); db.commit()
    except Exception:
        pass


def _df(ticker, days, source):
    try:
        return get_ohlcv(ticker, days, source)
    except Exception as e:
        raise HTTPException(502, f"data error: {e}")


@router.get("/universe")
def universe(): return universe_meta()


@router.get("/market/{ticker}")
def market(ticker: str, days: int = Query(252, ge=30, le=1500), source: str = "auto"):
    df, lab = _df(ticker, max(days, 260), source)
    ch = I.chart_series(df); df_v = df.tail(days); n = len(df_v)
    last, prev = float(df.close.iloc[-1]), float(df.close.iloc[-2])
    return clean({"ticker": ticker.upper(), "source": lab, "last": last, "change": last / prev - 1, "asof": str(df.index[-1].date()),
                  "dates": [str(x.date()) for x in df_v.index], "open": df_v.open.tolist(), "high": df_v.high.tolist(), "low": df_v.low.tolist(),
                  "close": df_v.close.tolist(), "volume": df_v.volume.tolist(),
                  "indicators": {k: v[-n:] for k, v in ch.items()},
                  "hi_52w": float(df.close.tail(252).max()), "lo_52w": float(df.close.tail(252).min())})


@router.get("/analysis/{ticker}")
def analysis(ticker: str, source: str = "auto"):
    df, lab = _df(ticker, 756, source)
    r = df["close"].pct_change().dropna().values
    out = {"ticker": ticker.upper(), "source": lab, "technical": I.snapshot(df)}
    try: out["garch"] = fit_garch(r, 30)
    except Exception as e: out["garch_error"] = str(e)
    try: out["regime"] = regime_analysis(r)
    except Exception as e: out["regime_error"] = str(e)
    out["dates"] = [str(x.date()) for x in df.index]
    return clean(out)


@router.get("/forecast/{ticker}")
def forecast(ticker: str, horizon: int = Query(5, ge=1, le=21), days: int = Query(900, ge=450, le=1800), mode: str = "long_flat",
             threshold: float = Query(0.02, ge=0, le=0.2), cost_bps: float = Query(5.0, ge=0, le=100), source: str = "auto"):
    df, lab = _df(ticker, days, source)
    try:
        res = cached_forecast((ticker.upper(), lab, days, horizon, mode, threshold, cost_bps), df, horizon=horizon, threshold=threshold, mode=mode, cost_bps=cost_bps)
    except ValueError as e:
        raise HTTPException(422, str(e))
    res = {**res, "ticker": ticker.upper(), "source": lab}
    try:
        g = fit_garch(df["close"].pct_change().dropna().values, 30); last = float(df.close.iloc[-1])
        drift = res["signal"]["expected_return_q50"] / horizon * 0.5     # shrink the ML drift by 50%
        k = np.arange(1, 31); sd = np.sqrt(np.cumsum(np.array(g["daily_vol_forecast"])[:30] ** 2))
        res["cone"] = {"days": k.tolist(), "median": (last * np.exp(drift * k)).tolist(),
                       "p05": (last * np.exp(drift * k - 1.645 * sd)).tolist(), "p25": (last * np.exp(drift * k - .674 * sd)).tolist(),
                       "p75": (last * np.exp(drift * k + .674 * sd)).tolist(), "p95": (last * np.exp(drift * k + 1.645 * sd)).tolist(),
                       "hist_dates": [str(x.date()) for x in df.index[-120:]], "hist": df.close.tail(120).tolist(),
                       "garch_vol_ann": g["forecast_vol_ann"]}
    except Exception:
        pass
    _log("forecast", {"ticker": ticker, "horizon": horizon}, {"signal": res["signal"], "validation": {k: v for k, v in res["validation"].items() if k != "folds"}})
    return clean(res)


class CompareReq(BaseModel):
    ticker: str = "SPY"; strategies: List[str] = ["ma_cross", "momentum", "donchian"]; cost_bps: float = Field(5.0, ge=0, le=100)
    days: int = Field(756, ge=200, le=1800); source: str = "auto"; params: dict = {}


@router.post("/strategies/compare")
def strat_compare(req: CompareReq):
    bad = [s for s in req.strategies if s not in S.STRATS]
    if bad: raise HTTPException(422, f"unknown strategies: {bad}")
    df, lab = _df(req.ticker, req.days, req.source)
    out = S.compare(df, req.strategies, req.cost_bps, req.params); out.update(ticker=req.ticker.upper(), source=lab)
    return clean(out)


@router.post("/strategies/surface")
def strat_surface(req: CompareReq):
    df, lab = _df(req.ticker, max(req.days, 500), req.source)
    return clean({**S.ma_surface(df, cost_bps=req.cost_bps), "ticker": req.ticker.upper(), "source": lab})


class OptReq(BaseModel):
    tickers: List[str] = Field(..., min_length=2, max_length=20); method: str = "max_sharpe"; rf: float = 0.03; cap: float = Field(0.6, gt=0, le=1)
    days: int = Field(504, ge=150, le=1500); holdout: float = Field(0.4, ge=0.1, le=0.6); source: str = "auto"


@router.post("/portfolio/optimize")
def pf_opt(req: OptReq):
    try:
        R, _, labs = returns_frame([t.upper() for t in req.tickers], req.days, req.source)
        out = P.optimize(R, req.method, req.rf, req.cap, req.holdout)
    except ValueError as e:
        raise HTTPException(422, str(e))
    out["sources"] = labs; _log("portfolio", req.model_dump(), {"weights": out["weights"], "stats": out["stats"]})
    return clean(out)


class RiskReq(BaseModel):
    tickers: List[str] = ["SPY"]; weights: Optional[List[float]] = None; confidence: float = Field(0.95, gt=0.8, lt=0.999)
    days: int = Field(756, ge=100, le=1800); rf: float = 0.03; source: str = "auto"


def _series(req):
    R, _, labs = returns_frame([t.upper() for t in req.tickers], req.days, req.source)
    w = np.array(req.weights if req.weights else np.ones(R.shape[1]) / R.shape[1], float)
    if len(w) != R.shape[1]: raise HTTPException(422, "weights length must match tickers")
    w = w / w.sum(); return R @ w, labs


@router.post("/risk/analyze")
def risk_analyze(req: RiskReq):
    r, labs = _series(req)
    try: out = RK.analyze(r, req.confidence, req.rf)
    except ValueError as e: raise HTTPException(422, str(e))
    out["sources"] = labs; return clean(out)


class SimReq(RiskReq):
    start: float = Field(100000, gt=0); years: float = Field(1.0, gt=0.1, le=10); sims: int = Field(3000, ge=200, le=10000)
    method: str = "bootstrap"; drift: Optional[float] = None


@router.post("/simulate")
def simulate(req: SimReq):
    r, labs = _series(req)
    return clean(RK.simulate_paths(r, req.start, req.years, req.sims, req.method, drift=req.drift))


class StressReq(BaseModel):
    tickers: List[str]; weights: Optional[List[float]] = None; value: float = 100000; source: str = "auto"; days: int = 504


# historical-style shocks by factor: market beta scaled; rates; commodities
SCENARIOS = {"2008 GFC": (-0.40, 0.18, -0.30), "2020 COVID crash": (-0.34, 0.12, -0.20), "2022 rate shock": (-0.19, -0.30, 0.10),
             "Tech unwind": (-0.25, 0.03, 0.0), "Stagflation": (-0.12, -0.15, 0.25), "Soft landing rally": (0.18, 0.08, 0.02)}


@router.post("/stress")
def stress_beta(req: StressReq):
    """Beta-mapped scenario stress: each asset's shock = beta_mkt*mkt_shock + beta_rate*TLT_shock + beta_cmd*GLD_shock, estimated by OLS on real returns."""
    names = [t.upper() for t in req.tickers]; extra = [x for x in ("SPY", "TLT", "GLD") if x not in names]
    R, _, _ = returns_frame(names + extra, req.days, req.source)
    F = R[["SPY", "TLT", "GLD"]].values; X = np.column_stack([np.ones(len(F)), F])
    B = np.linalg.lstsq(X, R[names].values, rcond=None)[0][1:].T            # (assets, 3)
    w = np.array(req.weights if req.weights else np.ones(len(names)) / len(names)); w = w / w.sum()
    out = {}
    for k, shock in SCENARIOS.items():
        a = B @ np.array(shock); out[k] = {"portfolio_return": float(w @ a), "pnl": float(req.value * (w @ a)), "assets": {n: float(a[i]) for i, n in enumerate(names)}}
    return clean({"scenarios": out, "betas": {n: {"SPY": float(B[i, 0]), "TLT": float(B[i, 1]), "GLD": float(B[i, 2])} for i, n in enumerate(names)}})


class OptionsReq(BaseModel):
    spot: float = Field(..., gt=0); strike: float = Field(..., gt=0); time_to_maturity: float = Field(..., gt=0.003, le=5)
    risk_free_rate: float = 0.04; volatility: float = Field(..., gt=0.01, le=5); option_type: str = "call"; dividend_yield: float = 0.0
    market_price: Optional[float] = None; preset: str = "long_call"


@router.post("/options/analyze")
def options_analyze(req: OptionsReq):
    if req.option_type not in ("call", "put"): raise HTTPException(422, "option_type must be call or put")
    try:
        return clean(O.analyze(req.spot, req.strike, req.time_to_maturity, req.risk_free_rate, req.volatility, req.option_type,
                               req.dividend_yield, req.market_price, req.preset))
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.get("/screener")
def screener(source: str = "auto"): return clean(SC.scan(source=source))


@router.get("/strategies/list")
def strat_list(): return [{"id": k, "name": v[0]} for k, v in S.STRATS.items()]
