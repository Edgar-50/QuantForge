# QuantForge v10 — Quant Research Terminal

A FastAPI + vanilla-JS research terminal: market analytics, **walk-forward machine-learning forecasting**, regime and volatility models, portfolio construction, risk, options and a strategy lab, in a dense, dark, keyboard-driven UI.

Research and education only. It does not give investment advice and does not execute trades.

## What's new in v10

**AI Forecast engine** (`app/quant/ml_engine.py`)
- 3-model ensemble (L2-logistic, shallow random forest, regularised gradient boosting) predicting P(H-day return > 0), plus quantile regressors for a P10/P50/P90 return cone.
- 25 scale-free features: multi-horizon momentum, realised vol, RSI, MACD, Bollinger %B, ATR, ADX, stochastic, volume z-score, skew/kurtosis, gap, drawdown from high.
- **Validation designed not to flatter itself:** expanding-window walk-forward refit per fold, purge/embargo gap equal to the horizon, pooled out-of-sample metrics against naive baselines, a rank-IC significance test using an *effective* sample size (H-day labels overlap), and an OOS trading simulation net of costs.
- Verdict: `EDGE_DETECTED` / `WEAK_EDGE` / `NO_EDGE`. On real markets the honest answer is usually `NO_EDGE`, and the UI says so rather than showing a confident-looking number.
- Explanations: feature importance, per-prediction logit contributions, calibration curve, model disagreement.

Measured behaviour of the detector (synthetic series, 1000 bars, 5-day horizon): it flagged an edge in 5 of 6 series with planted predictability (4 strong, 1 weak) and produced 1 weak and 0 strong false positives across 14 pure-noise series. These are small-sample checks, not guarantees; `tests/test_v10.py` re-runs a version of them.

**Market analytics:** candlesticks with SMA / Bollinger / volume / RSI / MACD, technical consensus, **GARCH(1,1)** (QMLE) volatility term structure, **3-state Gaussian HMM** regime detection (EM + Viterbi, in numpy), ticker tape, watchlist, universe **screener** with composite ranking.

**Strategy Lab:** six strategies (MA cross, momentum, RSI reversion, Bollinger, Donchian, vol-targeted trend), signal at close and trade next bar, with costs; an **in-sample vs out-of-sample Sharpe heatmap** that exposes parameter overfitting.

**Portfolio Lab:** max-Sharpe, min-vol, risk parity, **hierarchical risk parity**, equal weight; long-only with weight caps; Ledoit-Wolf covariance and shrunk expected returns; frontier and random-portfolio cloud; correlation heatmap; risk contributions; **out-of-sample holdout vs equal weight**; saved portfolios.

**Risk Center:** historical / Normal / Cornish-Fisher / Student-t VaR, CVaR, drawdown episodes, rolling vol and Sharpe, **Kupiec VaR backtest**, beta-mapped macro stress (equity / rates / commodity factors), bootstrap and GBM Monte Carlo fan charts.

**Options Lab:** Black-Scholes-Merton with dividend yield, Greeks curves, **implied-vol solver**, **American pricing (CRR binomial)** with early-exercise premium, time-decay curves, premium surface, nine multi-leg payoff presets with breakevens.

**UX:** Ctrl/Cmd-K command palette (any ticker, any view), `1`-`7` view hotkeys, `/` to search, persistent settings, loading skeletons, responsive layout.

**Fixes to v9:** `sortino_ratio` returned `inf` (invalid JSON, so a 500 error); auth issued no token (now signed, expiring HMAC tokens plus `/api/auth/me`); deprecated `on_event` / `utcnow` replaced.

## Data

Provider chain: `yfinance` (if installed) → Stooq CSV → **built-in simulator**. The simulator is deterministic, vol-clustered, regime-switching and cross-correlated, so everything works offline with no keys. The header pill always shows `SIMULATED DATA` or `LIVE · <provider>`. **Do not mistake simulated results for market evidence.**

The live providers were not reachable from the environment this was built in, so that path is implemented but untested there. Try it with the `DATA` toggle on `AUTO`.

## Run

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-live.txt                  # optional: live data (yfinance)
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 (API docs at `/docs`). The UI loads Plotly and fonts from CDNs, so the browser needs internet access.

```bash
pytest -q            # 36 tests (~25 s): numerics, no look-ahead, leakage, detector power, strict-JSON API
docker compose up --build
```

## API (v10, under `/api/v2`)

| Route | Purpose |
|---|---|
| `GET /market/{t}` · `GET /analysis/{t}` | OHLCV + indicators · technicals, GARCH, HMM regime |
| `GET /forecast/{t}?horizon=5&mode=long_flat` | Walk-forward ML forecast, validation, cone |
| `GET /screener` · `GET /universe` | Ranked universe · symbol list |
| `POST /strategies/compare` · `/strategies/surface` | Backtests · IS/OOS parameter surface |
| `POST /portfolio/optimize` | Optimizers, frontier, holdout test |
| `POST /risk/analyze` · `/stress` · `/simulate` | VaR suite · scenarios · Monte Carlo |
| `POST /options/analyze` | Pricing, Greeks, IV, American, payoffs |

All v9 routes under `/api` remain.

## Limits: read before trusting anything

- Daily bars, long-only research. No intraday data, borrow costs, slippage model, corporate-action handling or survivorship-bias control.
- A passing out-of-sample test on one asset is weak evidence. Scan 15 tickers and about one will look good by chance.
- Auth is minimal (signed tokens) and no endpoints are gated. Add authorization before exposing this publicly.
- Production use would need licensed data, exchange calendars, monitoring and independent model validation.
