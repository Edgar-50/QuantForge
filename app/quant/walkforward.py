import numpy as np

def _run_signal(prices, short_window, long_window, transaction_cost_bps=5.0):
    p = np.asarray(prices, dtype=float)
    if len(p) <= long_window + 1:
        raise ValueError("price series too short")
    short_ma = np.convolve(p, np.ones(short_window)/short_window, mode="valid")
    long_ma = np.convolve(p, np.ones(long_window)/long_window, mode="valid")
    offset = long_window - short_window
    sig = (short_ma[offset:] > long_ma).astype(float)
    aligned = p[long_window-1:]
    rets = np.diff(aligned) / aligned[:-1]
    trades = np.abs(np.diff(sig))
    sr = rets * sig[:-1]
    sr -= trades[:len(sr)] * (transaction_cost_bps/10000.0)
    equity = np.cumprod(1+sr)
    return float(equity[-1]-1.0) if len(equity) else 0.0

def parameter_grid_search(prices, short_candidates=(5,8,10), long_candidates=(20,30,40), transaction_cost_bps=5.0):
    results = []
    for s in short_candidates:
        for l in long_candidates:
            if s >= l:
                continue
            try:
                r = _run_signal(prices, s, l, transaction_cost_bps)
                results.append({"short_window": int(s), "long_window": int(l), "return": float(r)})
            except ValueError:
                pass
    results.sort(key=lambda x: x["return"], reverse=True)
    return {"results": results, "best": results[0] if results else None}

def walk_forward_ma(prices, train_size=100, test_size=30, transaction_cost_bps=5.0):
    p = np.asarray(prices, dtype=float)
    if len(p) < train_size + test_size:
        raise ValueError("not enough prices for requested train/test windows")

    windows = []
    start = 0
    stitched = []
    while start + train_size + test_size <= len(p):
        train = p[start:start+train_size]
        test = p[start+train_size-1:start+train_size+test_size]
        grid = parameter_grid_search(train, transaction_cost_bps=transaction_cost_bps)
        if not grid["best"]:
            break
        best = grid["best"]
        test_return = _run_signal(
            test,
            best["short_window"],
            best["long_window"],
            transaction_cost_bps
        )
        windows.append({
            "train_start": int(start),
            "train_end": int(start+train_size-1),
            "test_end": int(start+train_size+test_size-1),
            "short_window": best["short_window"],
            "long_window": best["long_window"],
            "train_return": best["return"],
            "test_return": float(test_return),
        })
        stitched.append(test_return)
        start += test_size

    compounded = float(np.prod([1+x for x in stitched]) - 1) if stitched else 0.0
    return {"windows": windows, "compounded_out_of_sample_return": compounded}
