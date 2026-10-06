import numpy as np
import pandas as pd
from . import indicators as I
from .data_provider import get_ohlcv, UNIVERSE

def scan(tickers=None, source="auto"):
    rows = []
    for t in (tickers or list(UNIVERSE)):
        df, lab = get_ohlcv(t, 300, source); c = df["close"]; r = c.pct_change()
        snap = I.snapshot(df); vol = float(r.tail(21).std() * np.sqrt(252))
        m126 = float(c.iloc[-1] / c.iloc[-127] - 1) if len(c) > 127 else 0.0
        trend = 1.0 if c.iloc[-1] > I.sma(c, 200).iloc[-1] else -1.0
        rows.append({"ticker": t, "name": UNIVERSE.get(t, (t,))[0], "sector": UNIVERSE.get(t, (t, "Other"))[1], "source": lab,
                     "price": float(c.iloc[-1]), "chg_1d": float(r.iloc[-1]), "chg_21d": float(c.iloc[-1] / c.iloc[-22] - 1), "chg_126d": m126,
                     "rsi": float(I.rsi(c).iloc[-1]), "vol_21d": vol, "atr_pct": snap["atr_pct"], "tech_score": snap["technical_score"],
                     "adx": snap["adx"], "above_200": trend > 0, "mom_sharpe": float(m126 / max(vol * np.sqrt(0.5), 1e-6)),
                     "spark": [float(x) for x in (c.tail(60) / c.tail(60).iloc[0]).values]})
    f = pd.DataFrame(rows)
    z = lambda s: (s - s.mean()) / (s.std() + 1e-9)
    f["composite"] = (0.4 * z(f["tech_score"]) + 0.4 * z(f["mom_sharpe"]) + 0.2 * z(f["above_200"].astype(float))).round(3)
    f["rank"] = f["composite"].rank(ascending=False).astype(int)
    return f.sort_values("rank").to_dict("records")
