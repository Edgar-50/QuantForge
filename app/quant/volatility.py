import numpy as np

def ewma_volatility(returns, lambda_=0.94):
    r = np.asarray(returns, dtype=float)
    if r.size < 2:
        raise ValueError("at least two returns are required")
    var = r[0] ** 2
    series = [var]
    for x in r[1:]:
        var = lambda_ * var + (1 - lambda_) * x ** 2
        series.append(var)
    vol = np.sqrt(np.asarray(series)) * np.sqrt(252)
    return {
        "latest_annualized_volatility": float(vol[-1]),
        "volatility_series": [float(x) for x in vol]
    }
