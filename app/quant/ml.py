import numpy as np

def build_features(returns, lookback=5):
    r = np.asarray(returns, dtype=float)
    if len(r) <= lookback + 1:
        raise ValueError("not enough observations")
    X, y = [], []
    for i in range(lookback, len(r)-1):
        win = r[i-lookback:i]
        X.append([
            float(win.mean()),
            float(win.std(ddof=1) if len(win)>1 else 0.0),
            float(np.sum(win)),
            float(win[-1]),
            float(np.max(win)),
            float(np.min(win)),
        ])
        y.append(1 if r[i+1] > 0 else 0)
    return np.asarray(X), np.asarray(y)

def logistic_direction_model(returns, lookback=5, epochs=400, learning_rate=0.15):
    X, y = build_features(returns, lookback)
    if len(np.unique(y)) < 2:
        return {
            "accuracy": 1.0,
            "coefficients": [0.0] * X.shape[1],
            "intercept": 0.0,
            "latest_probability_up": float(y[0]),
            "samples": int(len(y)),
        }

    # standardize
    mean = X.mean(axis=0)
    std = X.std(axis=0)
    std[std == 0] = 1.0
    Z = (X - mean) / std

    split = max(2, int(len(Z)*0.75))
    split = min(split, len(Z)-1)
    Xtr, Xte = Z[:split], Z[split:]
    ytr, yte = y[:split], y[split:]

    w = np.zeros(Xtr.shape[1])
    b = 0.0
    for _ in range(epochs):
        z = np.clip(Xtr @ w + b, -30, 30)
        p = 1/(1+np.exp(-z))
        err = p-ytr
        w -= learning_rate * (Xtr.T @ err) / len(Xtr)
        b -= learning_rate * float(err.mean())

    pte = 1/(1+np.exp(-np.clip(Xte @ w + b,-30,30)))
    pred = (pte >= .5).astype(int)
    acc = float((pred == yte).mean()) if len(yte) else 0.0

    latest_raw = X[-1]
    latest = (latest_raw-mean)/std
    prob = float(1/(1+np.exp(-np.clip(latest @ w + b,-30,30))))

    return {
        "accuracy": acc,
        "coefficients": [float(x) for x in w],
        "intercept": float(b),
        "latest_probability_up": prob,
        "samples": int(len(y)),
    }
