"""AI forecasting engine.

Ensemble (L2-logistic + shallow random forest + regularised gradient boosting) predicting the
probability that the H-day forward return is positive, plus quantile regressors for a return cone.

Validation is deliberately unforgiving:
  * expanding-window walk-forward, refit on every fold
  * purge/embargo gap = horizon so overlapping labels never leak across the train/test boundary
  * metrics are pooled strictly out-of-sample and compared against an always-up baseline
  * significance test uses an effective sample size (n / H) because H-day labels overlap
  * the OOS trading simulation is net of transaction costs
The engine reports "no reliable edge" when the evidence does not support one.
"""
from __future__ import annotations
import time, warnings
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from . import indicators as I

warnings.filterwarnings("ignore")
_CACHE: dict = {}


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    c, r = df["close"], df["close"].pct_change()
    F = pd.DataFrame(index=df.index)
    for n in (1, 2, 5, 10, 21, 63):
        F[f"ret_{n}d"] = c.pct_change(n)
    for n in (10, 21, 63):
        F[f"vol_{n}d"] = r.rolling(n).std()
    F["vol_ratio"] = F["vol_10d"] / F["vol_63d"]
    F["rsi_14"] = I.rsi(c, 14) / 100
    F["rsi_2"] = I.rsi(c, 2) / 100
    F["macd_hist"] = I.macd(c)[2] / c
    mid, up, lo = I.bollinger(c)
    F["bb_pctb"] = (c - lo) / (up - lo)
    F["atr_pct"] = I.atr(df) / c
    F["stoch_k"] = I.stochastic(df)[0] / 100
    F["adx"] = I.adx(df) / 100
    F["z_sma20"] = (c / I.sma(c, 20) - 1) / F["vol_21d"]
    F["z_sma50"] = (c / I.sma(c, 50) - 1) / F["vol_63d"]
    F["volu_z"] = np.log(df["volume"].replace(0, np.nan) / df["volume"].rolling(21).mean())
    F["skew_21d"] = r.rolling(21).skew()
    F["kurt_21d"] = r.rolling(21).kurt()
    F["range_5d"] = ((df["high"] - df["low"]) / c).rolling(5).mean()
    F["gap"] = df["open"] / c.shift() - 1
    F["dd_252d"] = c / c.rolling(252, min_periods=60).max() - 1
    return F.replace([np.inf, -np.inf], np.nan)


def _clf_models(seed=7):
    return {
        "logit": make_pipeline(StandardScaler(), LogisticRegression(C=0.05, max_iter=500)),
        "forest": RandomForestClassifier(n_estimators=140, max_depth=4, min_samples_leaf=25, max_features="sqrt", n_jobs=1, random_state=seed),
        "boost": HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=100, l2_regularization=2.0, min_samples_leaf=30, random_state=seed),
    }


def _fit_predict(Xtr, ytr, Xte):
    out, models = {}, _clf_models()
    for k, m in models.items():
        m.fit(Xtr, ytr); out[k] = m.predict_proba(Xte)[:, 1]
    return out, models


def _perf(r: np.ndarray):
    r = np.asarray(r, float)
    if len(r) < 2 or r.std(ddof=1) == 0:
        return {"total_return": 0.0, "cagr": 0.0, "ann_vol": 0.0, "sharpe": 0.0, "max_drawdown": 0.0}
    eq = np.cumprod(1 + r); dd = (eq / np.maximum.accumulate(eq) - 1).min()
    yrs = len(r) / 252
    return {"total_return": float(eq[-1] - 1), "cagr": float(eq[-1] ** (1 / yrs) - 1) if yrs > 0 else 0.0,
            "ann_vol": float(r.std(ddof=1) * np.sqrt(252)), "sharpe": float(r.mean() / r.std(ddof=1) * np.sqrt(252)),
            "max_drawdown": float(dd)}


def run_forecast(df: pd.DataFrame, horizon: int = 5, folds: int = 5, threshold: float = 0.02,
                 mode: str = "long_flat", cost_bps: float = 5.0) -> dict:
    t0 = time.time()
    F = build_features(df)
    c = df["close"]
    y_ret = c.shift(-horizon) / c - 1
    r1 = c.shift(-1) / c - 1
    feat_ok = F.notna().all(axis=1)
    X_all = F[feat_ok]
    idx = X_all.index
    lab_ok = y_ret.loc[idx].notna()
    n_lab = int(lab_ok.sum())
    if n_lab < 300:
        raise ValueError(f"need at least ~{300 + 70} daily bars (got {len(df)}); use a longer history")
    pos_lab = np.where(lab_ok.values)[0]               # positions (within idx) that have labels
    Xv = X_all.values
    yv = (y_ret.loc[idx].values > 0).astype(int)
    yr = y_ret.loc[idx].values
    n_idx = len(idx)

    min_train = max(180, int(0.45 * n_lab))
    last_lab = pos_lab[-1]
    edges = np.linspace(min_train, last_lab + 1, folds + 1).astype(int)
    oos_pos, oos_p, per_model, fold_rows = [], [], {k: [] for k in _clf_models()}, []
    for a, b in zip(edges[:-1], edges[1:]):
        tr = np.arange(0, a - horizon)                   # purge gap
        te = np.arange(a, b)
        preds, _ = _fit_predict(Xv[tr], yv[tr], Xv[te])
        p = np.mean(list(preds.values()), axis=0)
        for k in preds: per_model[k].append(preds[k])
        oos_pos.append(te); oos_p.append(p)
        yt = yv[te]
        fold_rows.append({"start": str(idx[a].date()), "end": str(idx[b - 1].date()), "n_train": int(len(tr)), "n_test": int(len(te)),
                          "accuracy": float(((p > .5) == yt).mean()),
                          "auc": float(roc_auc_score(yt, p)) if len(np.unique(yt)) > 1 else None,
                          "base_rate": float(yt.mean())})
    pos = np.concatenate(oos_pos); p = np.concatenate(oos_p)
    y = yv[pos]; yret_oos = yr[pos]
    base = float(max(y.mean(), 1 - y.mean()))
    acc = float(((p > .5) == y).mean())
    auc = float(roc_auc_score(y, p)) if len(np.unique(y)) > 1 else 0.5
    n_eff = max(int(len(y) / horizon), 10)
    pval = float(stats.binomtest(int(round(acc * n_eff)), n_eff, base, alternative="greater").pvalue)
    ic, _ = stats.spearmanr(p, yret_oos)
    ic = float(ic) if np.isfinite(ic) else 0.0
    # one-sided t-test on rank-IC with effective sample size (H-day labels overlap -> n/H independent obs)
    t_ic = ic * np.sqrt((n_eff - 2) / max(1 - ic ** 2, 1e-9))
    ic_p = float(stats.t.sf(t_ic, n_eff - 2))
    brier = float(brier_score_loss(y, p)); brier_base = float(brier_score_loss(y, np.full_like(p, y.mean())))
    conf = np.abs(p - .5) >= 0.05
    model_auc = {k: float(roc_auc_score(y, np.concatenate(v))) for k, v in per_model.items()}

    # --- OOS trading simulation (signal at close t -> next-day return) ---
    d = idx[pos]
    nxt = r1.loc[d].values
    ok = np.isfinite(nxt)
    d, p_, nxt = d[ok], p[ok], nxt[ok]
    sig = np.where(p_ > .5 + threshold, 1.0, 0.0)
    if mode == "long_short":
        sig = np.where(p_ < .5 - threshold, -1.0, sig)
    turn = np.abs(np.diff(np.r_[0.0, sig]))
    strat = sig * nxt - turn * cost_bps / 1e4
    bh = nxt
    eq_s, eq_b = np.cumprod(1 + strat), np.cumprod(1 + bh)
    perf_s, perf_b = _perf(strat), _perf(bh)
    perf_s["exposure"] = float((sig != 0).mean()); perf_s["turnover_per_year"] = float(turn.sum() / (len(sig) / 252))
    perf_s["hit_rate"] = float((strat[sig != 0] > 0).mean()) if (sig != 0).any() else 0.0

    # --- calibration ---
    q = pd.qcut(pd.Series(p), 5, duplicates="drop")
    cal = [{"pred": float(p[(q == k).values].mean()), "obs": float(y[(q == k).values].mean()), "n": int((q == k).sum())} for k in q.cat.categories]

    # --- final fit on every labelled row, predict latest bar ---
    tr = np.arange(0, last_lab + 1 - horizon + 0)       # strict purge before the live bar
    tr = tr[tr < n_idx]
    preds, models = _fit_predict(Xv[tr], yv[tr], Xv[-1:])
    p_live = float(np.mean([v[0] for v in preds.values()]))
    spread = float(np.std([v[0] for v in preds.values()]))
    # explanations: logistic contributions (coef * z) + forest importance blend
    lg = models["logit"]; sc, lr = lg.named_steps["standardscaler"], lg.named_steps["logisticregression"]
    z = sc.transform(Xv[-1:])[0]; contrib = lr.coef_[0] * z
    rf_imp = models["forest"].feature_importances_
    lg_imp = np.abs(lr.coef_[0]) / (np.abs(lr.coef_[0]).sum() + 1e-12)
    imp = 0.5 * rf_imp / rf_imp.sum() + 0.5 * lg_imp
    cols = list(X_all.columns)
    importance = sorted([{"feature": cols[i], "importance": float(imp[i]), "sign": int(np.sign(lr.coef_[0][i]))} for i in range(len(cols))],
                        key=lambda d_: -d_["importance"])[:12]
    drivers = sorted([{"feature": cols[i], "contribution": float(contrib[i]), "value": float(Xv[-1][i])} for i in range(len(cols))],
                     key=lambda d_: -abs(d_["contribution"]))[:6]
    # quantile cone
    qs = {}
    for qq in (0.1, 0.5, 0.9):
        m = HistGradientBoostingRegressor(loss="quantile", quantile=qq, max_depth=3, learning_rate=0.05, max_iter=100,
                                          min_samples_leaf=30, l2_regularization=2.0, random_state=7)
        qs[qq] = float(m.fit(Xv[tr], yr[tr]).predict(Xv[-1:])[0])
    lo, md, hi = sorted([qs[.1], qs[.5], qs[.9]])
    last = float(c.iloc[-1])

    edge = (ic_p < 0.10) and (auc > 0.53) and (ic > 0.04)
    strong = edge and ic_p < 0.03 and auc > 0.56
    verdict = ("EDGE_DETECTED" if strong else "WEAK_EDGE" if edge else "NO_EDGE")
    msg = {"EDGE_DETECTED": "Out-of-sample evidence supports a statistically detectable edge. Still size conservatively.",
           "WEAK_EDGE": "Marginal out-of-sample evidence. Treat as a tilt, not a signal.",
           "NO_EDGE": "No reliable out-of-sample edge on this asset/horizon. The probability below is close to noise — do not trade it alone."}[verdict]
    direction = "LONG" if p_live > .5 + threshold else ("SHORT" if (mode == "long_short" and p_live < .5 - threshold) else "FLAT")

    dates = [str(x.date()) for x in d]
    return {
        "ticker_last_price": last, "asof": str(df.index[-1].date()), "horizon": horizon,
        "signal": {"prob_up": p_live, "direction": direction, "model_disagreement": spread,
                   "by_model": {k: float(v[0]) for k, v in preds.items()},
                   "expected_return_q10": lo, "expected_return_q50": md, "expected_return_q90": hi,
                   "price_q10": last * (1 + lo), "price_q50": last * (1 + md), "price_q90": last * (1 + hi),
                   "verdict": verdict, "verdict_text": msg},
        "validation": {"n_oos": int(len(y)), "n_effective": n_eff, "accuracy": acc, "baseline_accuracy": base, "auc": auc,
                       "p_value": ic_p, "accuracy_p_value": pval, "information_coefficient": ic,
                       "brier": brier, "brier_baseline": brier_base,
                       "high_conf_accuracy": float(((p[conf] > .5) == y[conf]).mean()) if conf.any() else None,
                       "high_conf_share": float(conf.mean()), "model_auc": model_auc, "folds": fold_rows},
        "oos_strategy": {"dates": dates, "equity": [float(x) for x in eq_s], "buy_hold": [float(x) for x in eq_b],
                         "position": [float(x) for x in sig], "prob": [float(x) for x in p_],
                         "strategy": perf_s, "buy_hold_perf": perf_b, "mode": mode, "cost_bps": cost_bps},
        "calibration": cal, "importance": importance, "drivers": drivers,
        "meta": {"features": len(cols), "train_rows": int(len(tr)), "seconds": round(time.time() - t0, 2),
                 "models": list(_clf_models())},
    }


def cached_forecast(key, df, **kw):
    hit = _CACHE.get(key)
    if hit and time.time() - hit[0] < 900:
        return hit[1]
    res = run_forecast(df, **kw)
    _CACHE[key] = (time.time(), res)
    return res
